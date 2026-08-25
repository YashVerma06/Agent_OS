'use client';

import { useEffect, useMemo, useState } from 'react';
import { controlPlane } from './lib/api';
import type {
  ActorRole,
  AgentDefinition,
  ArtifactVersion,
  AuditEvent,
  PlatformHealth,
  PolicyDecision,
  WorkflowSnapshot,
  WorkflowState,
} from './lib/types';

const CLIENT_REQUEST =
  'We manage rental properties and need a small maintenance-request portal. Tenants should submit an issue, and our property manager should see requests and update their status.';

const DISCOVERY_TRANSCRIPT = JSON.stringify(
  {
    meeting: 'Northstar Property Group / Product discovery',
    participants: ['Maya Chen — Client', 'Discovery & Specification Agent'],
    decisions: [
      'Tenant authentication is excluded from the hackathon MVP.',
      'Severity is required and must be Low, Medium, High, or Emergency.',
      'Manager states are New, In Progress, and Resolved.',
      'Attachments and notifications are deferred.',
    ],
  },
  null,
  2,
);

const DISCOVERY_RECORD = JSON.stringify(
  {
    users: ['Tenant', 'Property manager'],
    required_fields: ['name', 'email', 'unit', 'category', 'description', 'severity'],
    success_signal: 'A manager can triage a valid request in under 30 seconds.',
    exclusions: ['Authentication', 'File attachments', 'Email notifications', 'Production deployment'],
  },
  null,
  2,
);

const SPECIFICATION = `# SPECIFICATIONS.md

## Product outcome
Give tenants a fast way to report maintenance issues and give property managers one reliable triage queue.

## Tenant request form
- Capture name, email, unit number, category, description, and severity.
- Validate required fields in the browser and API.
- Confirm successful submission without exposing internal identifiers.

## Property manager dashboard
- List submitted requests with newest first.
- Filter by status and severity.
- Move a request through New, In Progress, and Resolved.
- Work at desktop and mobile widths.

## Acceptance criteria
1. Invalid requests are rejected consistently by UI and API.
2. A submitted request appears in the manager queue.
3. All three approved statuses persist and render consistently.
4. Automated checks cover validation and status transitions.

## Explicit exclusions
Authentication, attachments, notifications, protected-branch merge, and production deployment.`;

const STAGES: Array<{
  label: string;
  owner: string;
  states: WorkflowState[];
  gate?: boolean;
}> = [
  { label: 'Client discovery', owner: 'Discovery Agent', states: ['INTAKE', 'DISCOVERY'] },
  { label: 'Specification approval', owner: 'Human gate', states: ['SPEC_REVIEW'], gate: true },
  { label: 'Plan & architecture', owner: 'Planner Agent', states: ['PLANNING'] },
  { label: 'Bounded build', owner: 'Builder Agent', states: ['IMPLEMENTING'] },
  {
    label: 'QA & security review',
    owner: 'Reviewer Agent',
    states: ['REVIEWING', 'REVISION_REQUIRED'],
  },
  {
    label: 'Release approval',
    owner: 'Human + Release Service',
    states: ['RELEASE_REVIEW', 'RELEASE_APPROVED', 'STAGING_RELEASED'],
    gate: true,
  },
];

const ACTIVE_ROLE: Partial<Record<WorkflowState, ActorRole>> = {
  INTAKE: 'manager',
  DISCOVERY: 'discovery',
  SPEC_REVIEW: 'discovery',
  PLANNING: 'planner',
  IMPLEMENTING: 'builder',
  REVIEWING: 'reviewer',
  REVISION_REQUIRED: 'builder',
  RELEASE_REVIEW: 'reviewer',
  RELEASE_APPROVED: 'release_service',
  STAGING_RELEASED: 'release_service',
};

type IconName =
  | 'grid'
  | 'workflow'
  | 'artifact'
  | 'shield'
  | 'pulse'
  | 'team'
  | 'arrow'
  | 'check'
  | 'lock'
  | 'spark'
  | 'clock';

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    workflow: <><circle cx="5" cy="6" r="2" /><circle cx="19" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="M7 6h10M6.7 7.5l4.1 8.7M17.3 7.5l-4.1 8.7" /></>,
    artifact: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></>,
    shield: <><path d="M12 3l8 3v5c0 5.2-3.3 8.4-8 10-4.7-1.6-8-4.8-8-10V6z" /><path d="M9 12l2 2 4-4" /></>,
    pulse: <path d="M3 12h4l2.2-6 4.1 12 2.2-6H21" />,
    team: <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2" /><path d="M3.5 20c.5-4 2.4-6 5.5-6s5 2 5.5 6M15 15c3 0 4.6 1.7 5 5" /></>,
    arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>,
    check: <path d="M5 12l4 4L19 6" />,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 018 0v3" /></>,
    spark: <><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5z" /><path d="M19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function shortHash(value: string) {
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function titleCase(value: string) {
  return value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function Home() {
  const [health, setHealth] = useState<PlatformHealth | null>(null);
  const [fleet, setFleet] = useState<AgentDefinition[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowSnapshot | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactVersion[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [policyDecision, setPolicyDecision] = useState<PolicyDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([controlPlane.health(), controlPlane.workforce()])
      .then(([platform, workforce]) => {
        setHealth(platform);
        setFleet(workforce);
      })
      .catch(() => {
        setHealth(null);
      });
  }, []);

  const currentStage = useMemo(() => {
    if (!workflow) return -1;
    return STAGES.findIndex((stage) => stage.states.includes(workflow.state));
  }, [workflow]);

  const activeRole = workflow ? ACTIVE_ROLE[workflow.state] : 'manager';
  const activeAgent = fleet.find((agent) => agent.role === activeRole);
  const specification = [...artifacts]
    .reverse()
    .find((artifact) => artifact.logical_name === 'SPECIFICATIONS');

  async function refreshEvidence(workflowId: string) {
    const [nextArtifacts, nextAudit] = await Promise.all([
      controlPlane.artifacts(workflowId),
      controlPlane.audit(workflowId),
    ]);
    setArtifacts(nextArtifacts);
    setAudit(nextAudit);
  }

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The control plane rejected this action.');
    } finally {
      setBusy(false);
    }
  }

  function launchEngagement() {
    void runAction(async () => {
      const created = await controlPlane.createWorkflow('Northstar maintenance portal', CLIENT_REQUEST);
      const started = await controlPlane.transition(created.workflow_id, 'start_discovery', 'manager', {
        requested_by: 'Arpit Mishra',
        interface: 'control-room',
      });
      setWorkflow(started.workflow);
      await refreshEvidence(created.workflow_id);
    });
  }

  function completeDiscovery() {
    if (!workflow) return;
    void runAction(async () => {
      const transcript = await controlPlane.createArtifact(workflow.workflow_id, {
        logical_name: 'MEETING_TRANSCRIPT',
        kind: 'application/json',
        content: DISCOVERY_TRANSCRIPT,
        actor: 'discovery',
        idempotency_key: `${workflow.workflow_id}-meeting-transcript-v1`,
      });
      const record = await controlPlane.createArtifact(workflow.workflow_id, {
        logical_name: 'DISCOVERY_RECORD',
        kind: 'application/json',
        content: DISCOVERY_RECORD,
        actor: 'discovery',
        source_artifact_ids: [transcript.artifact_id],
        idempotency_key: `${workflow.workflow_id}-discovery-record-v1`,
      });
      await controlPlane.createArtifact(workflow.workflow_id, {
        logical_name: 'SPECIFICATIONS',
        kind: 'text/markdown',
        content: SPECIFICATION,
        actor: 'discovery',
        source_artifact_ids: [transcript.artifact_id, record.artifact_id],
        idempotency_key: `${workflow.workflow_id}-specifications-v1`,
      });
      const result = await controlPlane.transition(
        workflow.workflow_id,
        'submit_specification',
        'discovery',
        { artifact: 'SPECIFICATIONS-v1.md' },
      );
      setWorkflow(result.workflow);
      await refreshEvidence(workflow.workflow_id);
    });
  }

  function approveSpecification() {
    if (!workflow || !specification) return;
    void runAction(async () => {
      await controlPlane.approveArtifact(workflow.workflow_id, specification);
      const result = await controlPlane.transition(
        workflow.workflow_id,
        'approve_specification',
        'human',
        { approved_sha256: specification.sha256, approved_by: 'Arpit Mishra' },
      );
      setWorkflow(result.workflow);
      await refreshEvidence(workflow.workflow_id);
    });
  }

  function provePolicyBoundary() {
    void runAction(async () => {
      const result = await controlPlane.evaluatePolicy(
        'builder',
        'deployment.production',
        workflow?.state ?? null,
      );
      setPolicyDecision(result);
    });
  }

  return (
    <main className="app-shell">
      <aside className="nav-rail" aria-label="Primary navigation">
        <div className="brand-mark" aria-label="Agent OS">A<span>O</span></div>
        <nav>
          <button className="nav-icon active" aria-label="Control room"><Icon name="grid" /></button>
          <button className="nav-icon" aria-label="Workflows"><Icon name="workflow" /></button>
          <button className="nav-icon" aria-label="Artifacts"><Icon name="artifact" /></button>
          <button className="nav-icon" aria-label="Policy"><Icon name="shield" /></button>
          <button className="nav-icon" aria-label="Observability"><Icon name="pulse" /></button>
          <button className="nav-icon" aria-label="Workforce"><Icon name="team" /></button>
        </nav>
        <div className="avatar" title="Arpit Mishra">AM</div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Agent OS / Control room</p>
            <div className="title-row">
              <h1>Northstar engagement</h1>
              <span className="foundation-badge">Foundation slice</span>
            </div>
          </div>
          <div className="runtime-cluster">
            <div className={`connection ${health ? 'online' : 'offline'}`}>
              <span className="connection-dot" />
              {health ? 'Control plane live' : 'Control plane offline'}
            </div>
            <div className="runtime-copy">
              <strong>{health?.model ?? 'Gemini runtime'}</strong>
              <span>{health ? `${health.google_cloud_location} · Vertex AI configured` : 'Start FastAPI on port 8080'}</span>
            </div>
          </div>
        </header>

        <div className="content-grid">
          <section className="main-column">
            <section className="hero-card">
              <div className="hero-copy">
                <div className="client-line"><span className="client-logo">N</span> Northstar Property Group</div>
                <h2>From client conversation to governed software.</h2>
                <p>{CLIENT_REQUEST}</p>
              </div>
              <div className="hero-metric">
                <span>Engagement state</span>
                <strong>{workflow ? titleCase(workflow.state) : 'Ready to launch'}</strong>
                <small>{workflow ? `Workflow v${workflow.version} · ${workflow.workflow_id.slice(0, 8)}` : 'No workflow created yet'}</small>
              </div>
            </section>

            {error && <div className="error-banner" role="alert"><Icon name="shield" />{error}</div>}

            <section className="section-card workflow-card">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Golden path</p>
                  <h3>Workforce handoff</h3>
                </div>
                <span className="section-meta">{workflow ? `${Math.max(currentStage + 1, 1)} of ${STAGES.length}` : `0 of ${STAGES.length}`}</span>
              </div>

              <div className="stage-list">
                {STAGES.map((stage, index) => {
                  const completed = currentStage > index;
                  const active = currentStage === index;
                  return (
                    <div className={`stage ${completed ? 'completed' : ''} ${active ? 'active' : ''}`} key={stage.label}>
                      <div className="stage-marker">{completed ? <Icon name="check" size={14} /> : index + 1}</div>
                      <div className="stage-copy"><strong>{stage.label}</strong><span>{stage.owner}</span></div>
                      {stage.gate && <span className="gate-chip"><Icon name="lock" size={12} /> Human gate</span>}
                      {active && <span className="live-chip">Active</span>}
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="section-card artifact-card">
              <div className="section-heading artifact-heading">
                <div>
                  <p className="eyebrow">Immutable deliverable</p>
                  <h3>SPECIFICATIONS.md</h3>
                </div>
                {specification ? (
                  <div className="artifact-meta">
                    <span className={specification.immutable ? 'status-approved' : 'status-draft'}>{specification.immutable ? 'Approved & locked' : 'Awaiting approval'}</span>
                    <code>sha256:{shortHash(specification.sha256)}</code>
                  </div>
                ) : <span className="status-empty">Generated after discovery</span>}
              </div>
              <div className={`document-preview ${specification ? '' : 'empty'}`}>
                {specification ? <pre>{specification.content}</pre> : (
                  <div className="empty-artifact">
                    <span><Icon name="artifact" size={24} /></span>
                    <strong>No specification artifact yet</strong>
                    <p>The Discovery Agent must ground it in a transcript and structured decision record.</p>
                  </div>
                )}
              </div>
            </section>
          </section>

          <aside className="right-column">
            <section className="section-card action-card">
              <div className="agent-orbit"><span><Icon name="spark" size={20} /></span></div>
              <p className="eyebrow">Current owner</p>
              <h3>{activeAgent?.display_name ?? 'Workforce Manager'}</h3>
              <p>{activeAgent?.purpose ?? 'Waiting for the control plane to return the governed workforce contract.'}</p>

              {!workflow && (
                <button className="primary-button" onClick={launchEngagement} disabled={busy || !health}>
                  {busy ? 'Creating engagement…' : 'Launch engagement'}<Icon name="arrow" />
                </button>
              )}
              {workflow?.state === 'DISCOVERY' && (
                <button className="primary-button" onClick={completeDiscovery} disabled={busy}>
                  {busy ? 'Recording evidence…' : 'Complete discovery packet'}<Icon name="arrow" />
                </button>
              )}
              {workflow?.state === 'SPEC_REVIEW' && (
                <div className="approval-box">
                  <div className="approval-title"><Icon name="lock" /><span><strong>Human decision required</strong><small>The agent cannot approve its own artifact.</small></span></div>
                  <button className="approve-button" onClick={approveSpecification} disabled={busy || !specification}>
                    {busy ? 'Locking artifact…' : 'Approve exact hash'}<Icon name="check" />
                  </button>
                </div>
              )}
              {workflow?.state === 'PLANNING' && (
                <div className="handoff-complete"><Icon name="check" /><span><strong>Planner handoff authorized</strong><small>The approved hash is now the immutable source of truth.</small></span></div>
              )}

              <div className="authority-strip">
                <span><Icon name="shield" size={15} /> Deterministic authority</span>
                <small>Permissions are enforced outside prompts.</small>
              </div>
            </section>

            <section className="section-card fleet-card">
              <div className="section-heading compact"><div><p className="eyebrow">Live registry</p><h3>Agent fleet</h3></div><span className="fleet-count">{fleet.length}</span></div>
              <div className="fleet-list">
                {fleet.map((agent, index) => (
                  <div className={`fleet-agent ${agent.role === activeRole ? 'active' : ''}`} key={agent.role}>
                    <span className={`agent-index tone-${index}`}>{String(index + 1).padStart(2, '0')}</span>
                    <div><strong>{agent.display_name.replace(' Agent', '')}</strong><span>{agent.outputs.length} governed outputs</span></div>
                    <span className="agent-state">{agent.role === activeRole ? 'Working' : 'Standby'}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="section-card policy-card">
              <div className="policy-heading"><span><Icon name="shield" /></span><div><p className="eyebrow">Permission proof</p><h3>Try a forbidden action</h3></div></div>
              <p>Ask the Builder to deploy to production. The policy gateway must deny it—regardless of prompt content.</p>
              <button className="secondary-button" onClick={provePolicyBoundary} disabled={busy || !health}>Evaluate boundary</button>
              {policyDecision && (
                <div className={`decision ${policyDecision.allowed ? 'allow' : 'deny'}`}>
                  <strong>{policyDecision.allowed ? 'Allowed' : 'Denied by policy'}</strong>
                  <span>{policyDecision.rule_id}</span>
                  <small>{policyDecision.reason}</small>
                </div>
              )}
            </section>
          </aside>
        </div>

        <section className="audit-strip" aria-label="Audit timeline">
          <div className="audit-title"><span><Icon name="pulse" /></span><div><p className="eyebrow">Execution evidence</p><h3>Audit timeline</h3></div></div>
          <div className="audit-events">
            {audit.length === 0 ? (
              <div className="audit-empty"><Icon name="clock" /> Consequential actions will appear here with trace and rule IDs.</div>
            ) : audit.slice(-4).reverse().map((event) => (
              <div className="audit-event" key={event.event_id}>
                <span className={`audit-dot ${event.allowed ? 'allowed' : 'denied'}`} />
                <div><strong>{titleCase(event.action)}</strong><span>{event.actor} · {event.rule_id}</span></div>
                <code>{event.trace_id.slice(0, 8)}</code>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
