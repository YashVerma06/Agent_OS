'use client';

import { useEffect, useRef } from 'react';
import type { Utterance } from '../lib/meeting-types';
import { Icon } from './icon';

const SOURCE_LABEL: Record<Utterance['source'], string> = {
  live_voice: 'Live voice',
  uploaded_transcript: 'Uploaded',
  written_brief: 'Typed',
  system_event: 'System',
};

function clockTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? '--:--'
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function MeetingTranscript({
  utterances,
  finalized,
  partial,
}: {
  utterances: Utterance[];
  finalized: boolean;
  /** In-flight agent text that has not yet been committed to the transcript. */
  partial?: string;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const count = utterances.length;

  // Follow the conversation, but only when new lines arrive.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [count, partial]);

  return (
    <section className="mr-transcript" aria-label="Live transcript">
      <header className="mr-panel-head">
        <div>
          <p className="mr-eyebrow">Evidence</p>
          <h3>Live transcript</h3>
        </div>
        <span className={`mr-chip ${finalized ? 'is-locked' : 'is-live'}`}>
          {finalized ? (
            <>
              <Icon name="lock" size={11} /> Finalized
            </>
          ) : (
            <>
              <i className="mr-dot" /> Capturing
            </>
          )}
        </span>
      </header>

      <div className="mr-transcript-scroll">
        {count === 0 && !partial ? (
          <div className="mr-transcript-empty">
            <Icon name="meeting" size={22} />
            <strong>Nothing captured yet</strong>
            <p>
              Every utterance is stored with a sequence number, timestamp and trace
              ID. The backend assigns the order, so a reconnect cannot duplicate a
              line.
            </p>
          </div>
        ) : (
          utterances.map((item) => (
            <article
              className={`mr-utterance is-${item.speaker}`}
              key={item.utterance_id}
            >
              <div className="mr-utterance-meta">
                <span className="mr-seq">
                  {String(item.sequence_number).padStart(3, '0')}
                </span>
                <strong>
                  {item.speaker === 'client'
                    ? 'Client'
                    : item.speaker === 'agent'
                      ? 'Discovery Agent'
                      : 'System'}
                </strong>
                <time dateTime={item.timestamp}>{clockTime(item.timestamp)}</time>
                <span className="mr-source">{SOURCE_LABEL[item.source]}</span>
              </div>
              <p>{item.content}</p>
            </article>
          ))
        )}

        {partial ? (
          <article className="mr-utterance is-agent is-partial">
            <div className="mr-utterance-meta">
              <span className="mr-seq">···</span>
              <strong>Discovery Agent</strong>
              <span className="mr-source">Speaking</span>
            </div>
            <p>{partial}</p>
          </article>
        ) : null}

        <div ref={endRef} />
      </div>

      <footer className="mr-transcript-foot">
        <span>{count} utterance{count === 1 ? '' : 's'}</span>
        <span>Backend-ordered · de-duplicated on reconnect</span>
      </footer>
    </section>
  );
}
