/**
 * Meeting Room types.
 *
 * Deliberately separate from `lib/types.ts`, which is a shared control-plane
 * contract this feature does not own. Anything here mirrors
 * `app/api/meeting_routes.py` and `app/services/*`.
 */

export type Speaker = 'client' | 'agent' | 'system';

export type UtteranceSource =
  | 'live_voice'
  | 'uploaded_transcript'
  | 'written_brief'
  | 'system_event';

export type MeetingState =
  | 'CREATED'
  | 'CONSENT_GRANTED'
  | 'CONNECTED'
  | 'ENDED'
  | 'FAILED';

/** Mirrors `app.services.transcript.Utterance`. */
export interface Utterance {
  utterance_id: string;
  workflow_id: string;
  meeting_id: string;
  sequence_number: number;
  speaker: Speaker;
  timestamp: string;
  content: string;
  source: UtteranceSource;
  trace_id: string;
}

export interface ConsentRecord {
  granted: boolean;
  participant_name: string;
  ai_disclosure_acknowledged: boolean;
  transcription_acknowledged: boolean;
  granted_at: string;
  trace_id: string;
}

export interface MeetingSession {
  meeting_id: string;
  workflow_id: string;
  tenant_id: string;
  state: MeetingState;
  mode: string;
  consent: ConsentRecord | null;
  created_at: string;
  connected_at: string | null;
  ended_at: string | null;
  reconnect_count: number;
  error: string | null;
}

/** What the room can actually do right now. Never assume live voice is on. */
export interface MeetingCapability {
  live_voice_available: boolean;
  mode: 'live_voice' | 'fallback_text';
  reason: string;
  model: string | null;
  core_model: string;
  input_sample_rate: number;
  output_sample_rate: number;
  transport: string;
  max_session_seconds: number;
  idle_timeout_seconds: number;
  note: string;
}

export interface MeetingView {
  session: MeetingSession;
  disclosure: string;
  capability: MeetingCapability;
  topics: string[];
}

/** Mirrors the shared `HandoffEnvelope` contract. */
export interface HandoffEnvelope {
  workflow_id: string;
  from_agent: string;
  requested_next_agent: string | null;
  output_artifact_ids: string[];
  required_gate: 'NONE' | 'SPECIFICATION_APPROVAL' | 'RELEASE_APPROVAL';
  status: AgentRunStatus;
  trace_id: string;
  idempotency_key: string;
}

export type AgentRunStatus =
  | 'READY'
  | 'COMPLETED'
  | 'WAITING_FOR_HUMAN'
  | 'DENIED'
  | 'FAILED';

/** Mirrors the shared `AgentRunResult` contract. */
export interface AgentRunResult {
  workflow_id: string;
  agent: string;
  status: AgentRunStatus;
  output_artifact_ids: string[];
  summary: string;
  handoff: HandoffEnvelope | null;
  trace_id: string;
  replayed: boolean;
}

export interface SpecificationHandoff {
  run: AgentRunResult;
  meeting_id: string;
  workflow_state: string;
  transcript_artifact_id: string;
  discovery_record_artifact_id: string;
  specification_artifact_id: string;
  specification_sha256: string;
  lineage: Record<string, string[]>;
  validation_problems: string[];
  required_sections: string[];
  utterance_count: number;
  topics_covered: string[];
  topics_not_covered: string[];
  unresolved_questions: string[];
  confirmed_decisions: string[];
  assumptions: string[];
  specification_markdown: string;
}

export interface DiscoveryBoundary {
  capability: string;
  allowed: boolean;
  rule_id: string;
  reason: string;
}

export type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'released'
  | 'error'
  | 'closed';

/** Frames the backend sends down the meeting socket. */
export type ServerFrame =
  | { type: 'ready'; mode: string; capability: MeetingCapability; reconnect_count: number; meeting_id: string }
  | { type: 'utterance'; utterance: Utterance }
  | { type: 'audio'; data: string; sample_rate: number }
  | { type: 'turn_complete' }
  | { type: 'live_released'; code: string; message: string }
  | { type: 'pong' }
  | { type: 'error'; message: string; code?: string };
