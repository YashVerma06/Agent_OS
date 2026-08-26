'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MeetingAudio, MicrophonePermissionError, audioSupported } from '../lib/audio';
import { meetingApi, meetingSocketUrl } from '../lib/meeting-api';
import type {
  ConnectionState,
  MeetingView,
  ServerFrame,
  SpecificationHandoff,
  Utterance,
} from '../lib/meeting-types';
import { Icon } from './icon';
import { MeetingTranscript } from './meeting-transcript';
import { SpecificationReview } from './specification-review';
import './meeting-room.css';

const TOPIC_LABELS: Record<string, string> = {
  users_and_roles: 'Users and roles',
  workflows: 'Workflows',
  fields_and_data: 'Fields and data',
  states_and_transitions: 'States and transitions',
  validation_rules: 'Validation rules',
  integrations: 'Integrations',
  security_and_permissions: 'Security and permissions',
  acceptance_criteria: 'Acceptance criteria',
  exclusions: 'Exclusions',
};

/** Provisional coverage hints. Replaced by generated evidence after finalize. */
const TOPIC_HINTS: Record<string, string[]> = {
  users_and_roles: ['user', 'role', 'staff', 'tenant', 'manager', 'admin', 'who'],
  workflows: ['workflow', 'process', 'step', 'flow', 'journey'],
  fields_and_data: ['field', 'data', 'form', 'record', 'attribute'],
  states_and_transitions: ['status', 'state', 'stage', 'transition', 'resolved'],
  validation_rules: ['valid', 'require', 'mandatory', 'rule', 'reject'],
  integrations: ['integrat', 'api', 'export', 'sync', 'third party', 'email'],
  security_and_permissions: ['permission', 'security', 'access', 'auth', 'privac'],
  acceptance_criteria: ['success', 'accept', 'done', 'criteria', 'measure'],
  exclusions: ['not', 'exclude', 'out of scope', 'later', 'phase two'],
};

const MAX_RECONNECTS = 5;

function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function MeetingRoom({
  workflowId,
  projectName,
  clientName,
  approverEmail,
  onExit,
}: {
  workflowId: string;
  projectName?: string;
  clientName?: string;
  approverEmail?: string;
  onExit?: () => void;
}) {
  const [view, setView] = useState<MeetingView | null>(null);
  const [phase, setPhase] = useState<'loading' | 'consent' | 'meeting' | 'complete'>('loading');
  const [connection, setConnection] = useState<ConnectionState>('idle');
  const [utterances, setUtterances] = useState<Utterance[]>([]);
  const [handoff, setHandoff] = useState<SpecificationHandoff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [participant, setParticipant] = useState('');
  const [ackAi, setAckAi] = useState(false);
  const [ackRecording, setAckRecording] = useState(false);

  const [muted, setMuted] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [draft, setDraft] = useState('');
  // Authoritative count, reported by the backend on each `ready` frame.
  const [reconnectCount, setReconnectCount] = useState(0);

  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<MeetingAudio | null>(null);
  const reconnectsRef = useRef(0);
  const closingRef = useRef(false);
  // `connect` reschedules itself on an unexpected drop. Going through a ref
  // keeps that self-reference legal and always points at the latest closure.
  const connectRef = useRef<(meetingId: string) => void>(() => {});

  const capability = view?.capability ?? null;
  const liveVoice = capability?.live_voice_available ?? false;

  // ---------------------------------------------------------------- boot -- //

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const opened = await meetingApi.open(workflowId, 'Client representative');
        if (cancelled) return;
        setView(opened);
        setPhase('consent');
      } catch (caught) {
        if (cancelled) return;
        setError(
          caught instanceof Error
            ? caught.message
            : 'The Agent OS control plane is unavailable.',
        );
        setPhase('consent');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  // Elapsed timer runs only while the meeting is actually open.
  useEffect(() => {
    if (phase !== 'meeting') return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  // ------------------------------------------------------------- socket -- //

  const handleFrame = useCallback((frame: ServerFrame) => {
    switch (frame.type) {
      case 'ready':
        setConnection('connected');
        reconnectsRef.current = 0;
        setReconnectCount(frame.reconnect_count);
        if (frame.reconnect_count > 0) {
          setNotice(`Reconnected (attempt ${frame.reconnect_count}). Transcript preserved.`);
        }
        break;
      case 'utterance':
        setUtterances((current) =>
          current.some((item) => item.utterance_id === frame.utterance.utterance_id)
            ? current
            : [...current, frame.utterance].sort(
                (a, b) => a.sequence_number - b.sequence_number,
              ),
        );
        break;
      case 'audio':
        audioRef.current?.enqueue(frame.data);
        break;
      case 'turn_complete':
        setAgentSpeaking(false);
        break;
      case 'live_released':
        setConnection('released');
        setNotice(frame.message);
        break;
      case 'error':
        setError(frame.message);
        if (frame.code === 'consent_required') {
          setPhase('consent');
        }
        break;
      default:
        break;
    }
  }, []);

  const connect = useCallback(
    (meetingId: string) => {
      closingRef.current = false;
      setConnection(reconnectsRef.current > 0 ? 'reconnecting' : 'connecting');

      const socket = new WebSocket(meetingSocketUrl(meetingId));
      socketRef.current = socket;

      socket.onmessage = (event) => {
        try {
          handleFrame(JSON.parse(event.data as string) as ServerFrame);
        } catch {
          /* ignore malformed frame */
        }
      };
      socket.onerror = () => setConnection('error');
      socket.onclose = () => {
        if (closingRef.current) {
          setConnection('closed');
          return;
        }
        // Unexpected drop: back off and retry. The backend de-duplicates, so a
        // replayed utterance cannot corrupt the transcript.
        if (reconnectsRef.current < MAX_RECONNECTS) {
          reconnectsRef.current += 1;
          const delay = Math.min(1000 * 2 ** (reconnectsRef.current - 1), 8000);
          setConnection('reconnecting');
          setNotice(`Connection lost. Retrying in ${Math.round(delay / 1000)}s…`);
          window.setTimeout(() => connectRef.current(meetingId), delay);
        } else {
          setConnection('error');
          setError('Could not restore the meeting connection. The transcript is safe.');
        }
      };
    },
    [handleFrame],
  );

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // ------------------------------------------------------------ actions -- //

  async function joinMeeting() {
    if (!view) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await meetingApi.grantConsent(view.session.meeting_id, {
        participant_name: participant.trim() || 'Client representative',
        ai_disclosure_acknowledged: ackAi,
        transcription_acknowledged: ackRecording,
      });

      if (liveVoice && audioSupported()) {
        const audio = new MeetingAudio({
          inputSampleRate: view.capability.input_sample_rate,
          outputSampleRate: view.capability.output_sample_rate,
          onFrame: (base64) => {
            const socket = socketRef.current;
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'audio', data: base64 }));
            }
          },
          onLevel: setMicLevel,
          onAgentAudio: setAgentSpeaking,
        });
        await audio.start();
        await audio.resume();
        audioRef.current = audio;
      }

      connect(view.session.meeting_id);
      setPhase('meeting');
    } catch (caught) {
      if (caught instanceof MicrophonePermissionError) {
        setError(
          'Microphone access was refused. You can still take part by typing below.',
        );
        connect(view.session.meeting_id);
        setPhase('meeting');
      } else {
        setError(caught instanceof Error ? caught.message : 'Could not join the meeting.');
      }
    } finally {
      setBusy(false);
    }
  }

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    audioRef.current?.setMuted(next);
  }

  function sendText() {
    const content = draft.trim();
    if (!content) return;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      // Interrupting: drop buffered agent audio so it does not talk over them.
      audioRef.current?.flush();
      socket.send(JSON.stringify({ type: 'text', content }));
      setDraft('');
    } else {
      setError('Not connected. Your message was not sent.');
    }
  }

  async function endMeeting() {
    if (!view) return;
    setBusy(true);
    setError(null);
    closingRef.current = true;
    try {
      socketRef.current?.send(JSON.stringify({ type: 'end' }));
    } catch {
      /* socket may already be closed */
    }
    socketRef.current?.close();
    await audioRef.current?.stop();
    audioRef.current = null;

    try {
      const result = await meetingApi.finalize(view.session.meeting_id);
      setHandoff(result);
      setPhase('complete');
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The meeting ended but the specification could not be generated.',
      );
      setPhase('complete');
    } finally {
      setBusy(false);
    }
  }

  useEffect(
    () => () => {
      closingRef.current = true;
      socketRef.current?.close();
      void audioRef.current?.stop();
    },
    [],
  );

  // ------------------------------------------------------------- topics -- //

  const topicState = useMemo(() => {
    const topics = view?.topics ?? [];
    if (handoff) {
      const covered = new Set(handoff.topics_covered);
      return topics.map((topic) => ({ topic, covered: covered.has(topic), provisional: false }));
    }
    const haystack = utterances.map((item) => item.content.toLowerCase()).join(' ');
    return topics.map((topic) => ({
      topic,
      covered: (TOPIC_HINTS[topic] ?? []).some((hint) => haystack.includes(hint)),
      provisional: true,
    }));
  }, [view?.topics, utterances, handoff]);

  // ---------------------------------------------------------------- UI --- //

  if (phase === 'loading') {
    return (
      <main className="mr-shell mr-center" role="status">
        <div className="mr-brand-mark"><Icon name="spark" size={22} /></div>
        <p className="mr-eyebrow">Agent OS Meeting Room</p>
        <h1>Preparing the room…</h1>
      </main>
    );
  }

  const session = view?.session;

  return (
    <main className={`mr-shell${phase === 'meeting' ? ' is-pinned' : ''}`}>
      <header className="mr-topbar">
        <div className="mr-brand">
          <span className="mr-brand-mark"><Icon name="spark" size={17} /></span>
          <div>
            <strong>Agent OS Meeting Room</strong>
            <small>{projectName ?? 'Discovery session'}{clientName ? ` · ${clientName}` : ''}</small>
          </div>
        </div>

        <div className="mr-status-cluster">
          {phase === 'meeting' && (
            <>
              <span className={`mr-conn is-${connection}`}>
                <i className="mr-dot" />
                {connection === 'connected'
                  ? liveVoice
                    ? 'Live voice connected'
                    : 'Text mode connected'
                  : connection === 'reconnecting'
                    ? 'Reconnecting…'
                    : connection === 'released'
                      ? 'Live session released'
                      : connection === 'error'
                        ? 'Connection error'
                        : 'Connecting…'}
              </span>
              <span className="mr-elapsed" aria-label="Elapsed time">
                <Icon name="clock" size={14} /> {formatElapsed(elapsed)}
              </span>
            </>
          )}
          {onExit && (
            <button type="button" className="mr-ghost" onClick={onExit}>
              <Icon name="logout" size={14} /> Leave
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="mr-banner is-error" role="alert">
          <Icon name="shield" size={15} /> {error}
        </div>
      )}
      {notice && !error && (
        <div className="mr-banner is-notice" role="status">
          <Icon name="pulse" size={15} /> {notice}
        </div>
      )}

      {/* ------------------------------------------------------- consent -- */}
      {phase === 'consent' && (
        <section className="mr-consent">
          <div className="mr-consent-card">
            <span className="mr-chip is-ai"><Icon name="spark" size={11} /> AI participant</span>
            <h1>You are about to speak with an AI agent.</h1>
            <p className="mr-lead">{view?.disclosure}</p>

            <div className="mr-mode-note">
              <Icon name={liveVoice ? 'meeting' : 'artifact'} size={15} />
              <div>
                <strong>{liveVoice ? 'Live voice discovery' : 'Text discovery (fallback)'}</strong>
                <small>{capability?.reason}</small>
              </div>
            </div>

            <label className="mr-field">
              <span>Your name</span>
              <input
                value={participant}
                onChange={(event) => setParticipant(event.target.value)}
                placeholder="Who is joining?"
                maxLength={120}
              />
            </label>

            <label className="mr-check">
              <input
                type="checkbox"
                checked={ackAi}
                onChange={(event) => setAckAi(event.target.checked)}
              />
              <span>
                I understand I am speaking with an <strong>AI agent</strong>, not a
                human consultant, and that it cannot agree pricing, contracts or
                delivery dates.
              </span>
            </label>

            <label className="mr-check">
              <input
                type="checkbox"
                checked={ackRecording}
                onChange={(event) => setAckRecording(event.target.checked)}
              />
              <span>
                I consent to this session being <strong>transcribed</strong> and stored
                as project evidence, and to a specification being drafted from it for
                human approval.
              </span>
            </label>

            <button
              type="button"
              className="mr-primary mr-join"
              onClick={joinMeeting}
              disabled={busy || !ackAi || !ackRecording || !view}
            >
              {busy ? 'Joining…' : liveVoice ? 'Join with microphone' : 'Join discovery session'}
              <Icon name="arrow" size={15} />
            </button>

            <p className="mr-fineprint">
              {capability?.note} Capture cannot start until both boxes are ticked —
              the backend refuses any utterance without a consent record.
            </p>
          </div>
        </section>
      )}

      {/* ------------------------------------------------------- meeting -- */}
      {phase === 'meeting' && (
        <section className="mr-stage">
          <div className="mr-stage-main">
            <div className="mr-speakers">
              <div className={`mr-speaker ${agentSpeaking ? 'is-active' : ''}`}>
                <span className="mr-avatar is-agent"><Icon name="spark" size={20} /></span>
                <div>
                  <strong>Discovery Agent</strong>
                  <small>{agentSpeaking ? 'Speaking…' : 'Listening'}</small>
                </div>
                <span className="mr-wave" aria-hidden="true">
                  <i /><i /><i /><i />
                </span>
              </div>

              <div className={`mr-speaker ${micLevel > 0.05 && !muted ? 'is-active' : ''}`}>
                <span className="mr-avatar is-client">
                  {(participant || 'C').slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <strong>{participant || 'You'}</strong>
                  <small>
                    {!liveVoice
                      ? 'Typing'
                      : muted
                        ? 'Microphone muted'
                        : micLevel > 0.05
                          ? 'Speaking…'
                          : 'Microphone live'}
                  </small>
                </div>
                <span className="mr-level" aria-hidden="true">
                  <i style={{ transform: `scaleX(${Math.min(1, micLevel * 3)})` }} />
                </span>
              </div>
            </div>

            <MeetingTranscript
              utterances={utterances}
              finalized={false}
            />

            <div className="mr-composer">
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') sendText();
                }}
                placeholder={
                  liveVoice
                    ? 'Type to add a point without interrupting…'
                    : 'Describe what you need…'
                }
                maxLength={4000}
              />
              <button type="button" className="mr-secondary" onClick={sendText}>
                Send <Icon name="arrow" size={14} />
              </button>
            </div>

            <div className="mr-controls">
              {liveVoice && (
                <button
                  type="button"
                  className={`mr-control ${muted ? 'is-muted' : ''}`}
                  onClick={toggleMute}
                  aria-pressed={muted}
                >
                  <Icon name={muted ? 'lock' : 'pulse'} size={16} />
                  {muted ? 'Unmute' : 'Mute'}
                </button>
              )}
              <button
                type="button"
                className="mr-danger"
                onClick={endMeeting}
                disabled={busy}
              >
                {busy ? 'Finalizing…' : 'End meeting & draft specification'}
                <Icon name="check" size={15} />
              </button>
            </div>
          </div>

          <aside className="mr-side">
            <section className="mr-panel">
              <header className="mr-panel-head">
                <div>
                  <p className="mr-eyebrow">Coverage</p>
                  <h3>Topics</h3>
                </div>
                <span className="mr-chip is-soft">
                  {topicState.filter((item) => item.covered).length}/{topicState.length}
                </span>
              </header>
              <ul className="mr-topics">
                {topicState.map(({ topic, covered }) => (
                  <li key={topic} className={covered ? 'is-covered' : ''}>
                    <span className="mr-topic-dot">
                      {covered ? <Icon name="check" size={11} /> : null}
                    </span>
                    {TOPIC_LABELS[topic] ?? topic}
                  </li>
                ))}
              </ul>
              <p className="mr-fineprint">
                Provisional while the meeting is open. Confirmed coverage comes from
                the discovery record after the meeting ends.
              </p>
            </section>

            <section className="mr-panel">
              <header className="mr-panel-head">
                <div>
                  <p className="mr-eyebrow">Governance</p>
                  <h3>Agent boundaries</h3>
                </div>
              </header>
              <ul className="mr-boundaries">
                <li><Icon name="lock" size={12} /> Cannot approve its own specification</li>
                <li><Icon name="lock" size={12} /> Cannot access any repository</li>
                <li><Icon name="lock" size={12} /> Cannot read secrets or deploy</li>
                <li><Icon name="lock" size={12} /> Cannot schedule meetings</li>
                <li><Icon name="lock" size={12} /> Cannot quote price or delivery dates</li>
              </ul>
              <p className="mr-fineprint">
                Enforced by the deterministic policy engine, not by the prompt.
              </p>
            </section>

            <section className="mr-panel">
              <header className="mr-panel-head">
                <div>
                  <p className="mr-eyebrow">Session</p>
                  <h3>Room</h3>
                </div>
              </header>
              <dl className="mr-facts">
                <div><dt>Mode</dt><dd>{liveVoice ? 'Live voice' : 'Text fallback'}</dd></div>
                <div><dt>Meeting</dt><dd><code>{session?.meeting_id.slice(0, 8)}</code></dd></div>
                <div><dt>Reconnects</dt><dd>{reconnectCount}</dd></div>
                {liveVoice && capability && (
                  <div>
                    <dt>Session cap</dt>
                    <dd>{Math.round(capability.max_session_seconds / 60)} min</dd>
                  </div>
                )}
              </dl>
            </section>
          </aside>
        </section>
      )}

      {/* ------------------------------------------------------ complete -- */}
      {phase === 'complete' && (
        <section className="mr-complete">
          <div className="mr-complete-main">
            {handoff ? (
              <SpecificationReview
                handoff={handoff}
                specificationMarkdown={handoff.specification_markdown}
                approverEmail={approverEmail}
                approved={false}
              />
            ) : (
              <div className="mr-panel mr-complete-empty">
                <Icon name="shield" size={22} />
                <strong>The meeting ended without a specification</strong>
                <p>{error ?? 'Structured generation did not complete.'}</p>
              </div>
            )}
          </div>

          <aside className="mr-side">
            <MeetingTranscript utterances={utterances} finalized />

            {handoff && (
              <section className="mr-panel">
                <header className="mr-panel-head">
                  <div>
                    <p className="mr-eyebrow">From the discovery record</p>
                    <h3>Unresolved questions</h3>
                  </div>
                  <span className="mr-chip is-soft">{handoff.unresolved_questions.length}</span>
                </header>
                {handoff.unresolved_questions.length ? (
                  <ul className="mr-questions">
                    {handoff.unresolved_questions.map((question) => (
                      <li key={question}>{question}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mr-fineprint">
                    None recorded. Worth confirming that is genuinely true.
                  </p>
                )}
              </section>
            )}
          </aside>
        </section>
      )}
    </main>
  );
}
