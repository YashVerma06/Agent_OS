'use client';

import { useState } from 'react';
import type { SpecificationHandoff } from '../lib/meeting-types';
import { Icon } from './icon';

function shortHash(value: string) {
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

/**
 * Post-meeting specification status and the human approval gate.
 *
 * This component presents; it never approves. `onApprove` is wired to the
 * control plane's human transition, and the button is the operator's action,
 * not the agent's.
 */
export function SpecificationReview({
  handoff,
  specificationMarkdown,
  approverEmail,
  approved,
  busy,
  onApprove,
}: {
  handoff: SpecificationHandoff;
  specificationMarkdown: string | null;
  approverEmail?: string;
  approved: boolean;
  busy?: boolean;
  onApprove?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const problems = handoff.validation_problems;
  const complete = problems.length === 0;

  return (
    <section className="mr-spec" aria-label="Specification review">
      <header className="mr-panel-head">
        <div>
          <p className="mr-eyebrow">Post-meeting</p>
          <h3>SPECIFICATIONS.md</h3>
        </div>
        <span className={`mr-chip ${approved ? 'is-locked' : 'is-gate'}`}>
          {approved ? (
            <>
              <Icon name="check" size={11} /> Approved &amp; locked
            </>
          ) : (
            <>
              <Icon name="lock" size={11} /> Awaiting human approval
            </>
          )}
        </span>
      </header>

      <div className="mr-spec-grid">
        <div className="mr-spec-fact">
          <small>Workflow state</small>
          <strong>{handoff.workflow_state}</strong>
        </div>
        <div className="mr-spec-fact">
          <small>Utterances used</small>
          <strong>{handoff.utterance_count}</strong>
        </div>
        <div className="mr-spec-fact">
          <small>Sections</small>
          <strong className={complete ? 'is-ok' : 'is-warn'}>
            {handoff.required_sections.length - problems.length}/
            {handoff.required_sections.length}
          </strong>
        </div>
        <div className="mr-spec-fact">
          <small>Artifact hash</small>
          <code>{shortHash(handoff.specification_sha256)}</code>
        </div>
      </div>

      {/* Lineage is the point: the specification is traceable to the meeting. */}
      <div className="mr-lineage">
        <p className="mr-eyebrow">Artifact lineage</p>
        <ol>
          <li>
            <span className="mr-lineage-dot" />
            <div>
              <strong>MEETING_TRANSCRIPT</strong>
              <code>{handoff.transcript_artifact_id.slice(0, 8)}</code>
            </div>
          </li>
          <li>
            <span className="mr-lineage-dot" />
            <div>
              <strong>DISCOVERY_RECORD</strong>
              <code>{handoff.discovery_record_artifact_id.slice(0, 8)}</code>
            </div>
          </li>
          <li>
            <span className="mr-lineage-dot is-final" />
            <div>
              <strong>SPECIFICATIONS</strong>
              <code>{handoff.specification_artifact_id.slice(0, 8)}</code>
            </div>
          </li>
        </ol>
      </div>

      {!complete && (
        <div className="mr-spec-problems" role="status">
          <Icon name="shield" size={14} />
          <div>
            <strong>{problems.length} section gap{problems.length === 1 ? '' : 's'}</strong>
            <ul>
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
            <small>
              The document is rendered honestly rather than padded. Gaps mean the
              conversation did not settle those points.
            </small>
          </div>
        </div>
      )}

      {specificationMarkdown ? (
        <div className={`mr-spec-preview ${expanded ? 'is-expanded' : ''}`}>
          <pre>{specificationMarkdown}</pre>
          <button
            type="button"
            className="mr-text-button"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? 'Collapse document' : 'Read full document'}
          </button>
        </div>
      ) : null}

      {!approved && onApprove ? (
        <div className="mr-approval">
          <div className="mr-approval-copy">
            <Icon name="lock" size={15} />
            <span>
              <strong>Human decision required</strong>
              <small>
                {approverEmail
                  ? `Configured approver: ${approverEmail}`
                  : 'No agent may approve this artifact.'}
              </small>
            </span>
          </div>
          <button
            type="button"
            className="mr-primary"
            onClick={onApprove}
            disabled={busy}
          >
            {busy ? 'Locking artifact…' : 'Approve exact hash'}
            <Icon name="check" size={15} />
          </button>
        </div>
      ) : null}

      {approved ? (
        <div className="mr-approved">
          <Icon name="check" size={15} />
          <span>
            <strong>Specification locked</strong>
            <small>Planning may begin from this immutable hash.</small>
          </span>
        </div>
      ) : null}
    </section>
  );
}
