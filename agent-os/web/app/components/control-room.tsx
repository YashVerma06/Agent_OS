'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { controlPlane } from '../lib/api';
import type {
  ActivatedWorkforce,
  ActorRole,
  AgentDefinition,
  ArtifactVersion,
  AuditEvent,
  OrganizationProfile,
  PlatformHealth,
  PolicyDecision,
  WorkflowSnapshot,
  WorkflowState,
} from '../lib/types';
import { Icon } from './icon';

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

function titleCase(value: string) {
  return value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortHash(value: string) {
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

function meetingModeLabel(mode: ActivatedWorkforce['meeting_mode']) {
  return {
    agent_os_room: 'Agent OS Meeting Room',
    transcript_upload: 'Transcript upload',
    written_brief: 'Written discovery brief',
  }[mode];
}

function initialDiscoveryRecord(workflow: WorkflowSnapshot, workforce: ActivatedWorkforce) {
  return JSON.stringify(
    {
      source: 'enterprise_onboarding_intake',
      capture_status: 'initial_brief_only_not_live_meeting',
      client: workflow.client_name,
      project: workflow.name,
      meeting_mode: workforce.meeting_mode,
      client_request: workflow.client_request,
      known_constraints: {
        repository: workforce.repository_url,
        base_branch: workforce.base_branch,
        working_branch_prefix: workforce.working_branch_prefix,
      },
      open_questions: [
        'Who are the exact user roles and permission levels?',
        'Which workflows and edge cases are mandatory for the first release?',
        'What measurable acceptance criteria define success?',
        'Which integrations, data sources, and compliance constraints apply?',
      ],
    },
    null,
    2,
  );
}

function initialSpecification(workflow: WorkflowSnapshot, workforce: ActivatedWorkforce) {
  return `# SPECIFICATIONS.md

## Engagement
- Organization tenant: ${workflow.tenant_id}
- Client: ${workflow.client_name ?? 'Not supplied'}
- Project: ${workflow.name}
- Discovery source: ${meetingModeLabel(workforce.meeting_mode)}

## Client request
${workflow.client_request}

## Operating boundaries
- Repository: ${workforce.repository_url}
- Protected base branch: ${workforce.base_branch}
- Agent working branches: ${workforce.working_branch_prefix}*
- Specification approver: ${workforce.specification_approver_email}
- Release approver: ${workforce.release_approver_email}

## Requirements status
This is an intake-derived draft. Requirements must be clarified against discovery evidence before implementation begins.

## Open discovery questions
1. Who are the exact users and permission levels?
2. What workflows, validations, and edge cases are mandatory?
3. What measurable acceptance criteria define success?
4. Which integrations, data sources, and compliance constraints apply?

## Explicit governance
The Builder cannot start until a human approves this exact artifact hash. Protected-branch writes, secrets, production deployment, and self-approval remain prohibited.`;
}

export function ControlRoom({
  health,
  organization,
  workforce,
  initialWorkflow,
  fleet,
  onExit,
}: {
  health: PlatformHealth;
  organization: OrganizationProfile;
  workforce: ActivatedWorkforce;
  initialWorkflow: WorkflowSnapshot;
  fleet: AgentDefinition[];
  onExit: () => void;
}) {
  const [workflow, setWorkflow] = useState(initialWorkflow);
  const [artifacts, setArtifacts] = useState<ArtifactVersion[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [policyDecision, setPolicyDecision] = useState<PolicyDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshEvidence(initialWorkflow.workflow_id);
  }, [initialWorkflow.workflow_id]);

  const currentStage = useMemo(
    () => STAGES.findIndex((stage) => stage.states.includes(workflow.state)),
    [workflow.state],
  );
  const activeRole = ACTIVE_ROLE[workflow.state] ?? 'manager';
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

  function startDiscovery() {
    void runAction(async () => {
      const result = await controlPlane.transition(
        workflow.workflow_id,
        'start_discovery',
        'manager',
        { organization_id: organization.organization_id, workforce_id: workforce.workforce_id },
      );
      setWorkflow(result.workflow);
      await refreshEvidence(workflow.workflow_id);
    });
  }

  /** Open the client-facing meeting room for this engagement, in a new tab. */
  function openMeetingRoom() {
    const params = new URLSearchParams({
      workflow: workflow.workflow_id,
      project: workflow.name,
      approver: workforce.specification_approver_email,
    });
    if (workflow.client_name) {
      params.set('client', workflow.client_name);
    }
    window.open(`/meeting?${params.toString()}`, '_blank', 'noopener');
  }

  function createIntakeDraft() {
    void runAction(async () => {
      const record = await controlPlane.createArtifact(workflow.workflow_id, {
        logical_name: 'DISCOVERY_RECORD',
        kind: 'application/json',
        content: initialDiscoveryRecord(workflow, workforce),
        actor: 'discovery',
        idempotency_key: `${workflow.workflow_id}-discovery-record-v1`,
      });
      await controlPlane.createArtifact(workflow.workflow_id, {
        logical_name: 'SPECIFICATIONS',
        kind: 'text/markdown',
        content: initialSpecification(workflow, workforce),
        actor: 'discovery',
        source_artifact_ids: [record.artifact_id],
        idempotency_key: `${workflow.workflow_id}-specifications-v1`,
      });
      const result = await controlPlane.transition(
        workflow.workflow_id,
        'submit_specification',
        'discovery',
        { source: 'onboarding_intake', live_meeting_executed: false },
      );
      setWorkflow(result.workflow);
      await refreshEvidence(workflow.workflow_id);
    });
  }

  function approveSpecification() {
    if (!specification) return;
    void runAction(async () => {
      await controlPlane.approveArtifact(workflow.workflow_id, specification);
      const result = await controlPlane.transition(
        workflow.workflow_id,
        'approve_specification',
        'human',
        {
          approved_sha256: specification.sha256,
          configured_approver: workforce.specification_approver_email,
          authentication_status: 'foundation_not_verified',
        },
      );
      setWorkflow(result.workflow);
      await refreshEvidence(workflow.workflow_id);
    });
  }

  function provePolicyBoundary() {
    void runAction(async () => {
      setPolicyDecision(
        await controlPlane.evaluatePolicy('builder', 'deployment.production', workflow.state),
      );
    });
  }

  return (
    <main className="app-shell" id="overview">
      <aside className="nav-rail" aria-label="Workspace navigation">
        <Link className="brand-mark" href="/" aria-label="Agent OS — back to the overview">A<span>O</span></Link>
        <nav>
          <a className="nav-icon active" href="#overview" aria-label="Overview"><Icon name="grid" /></a>
          <a className="nav-icon" href="#workflow" aria-label="Workflow"><Icon name="workflow" /></a>
          <a className="nav-icon" href="#artifacts" aria-label="Artifacts"><Icon name="artifact" /></a>
          <a className="nav-icon" href="#governance" aria-label="Governance"><Icon name="shield" /></a>
          <a className="nav-icon" href="#audit" aria-label="Audit"><Icon name="pulse" /></a>
        </nav>
        <button type="button" className="avatar" title="Leave workspace" onClick={onExit}>{organization.owner_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{organization.display_name} / {workforce.display_name}</p>
            <div className="title-row"><h1>{workflow.name}</h1><span className="foundation-badge">Software delivery workforce</span></div>
          </div>
          <div className="runtime-cluster">
            <div className="connection online"><span className="connection-dot" />Control plane live</div>
            <div className="runtime-copy"><strong>{health.model}</strong><span>{health.google_cloud_location} · Vertex AI configured</span></div>
            <button type="button" className="exit-button" onClick={onExit}><Icon name="logout" size={15} /> Exit workspace</button>
          </div>
        </header>

        <div className="control-summary">
          <div><span className="summary-icon client"><Icon name="building" /></span><div><small>Client</small><strong>{workflow.client_name}</strong></div></div>
          <div><span className="summary-icon meeting"><Icon name="meeting" /></span><div><small>Discovery input</small><strong>{meetingModeLabel(workforce.meeting_mode)}</strong></div></div>
          <div><span className="summary-icon repo"><Icon name="repo" /></span><div><small>Repository boundary</small><strong>{workforce.repository_url.replace('https://github.com/', '')}</strong></div></div>
          <div><span className="summary-icon gate"><Icon name="lock" /></span><div><small>Mandatory gates</small><strong>Specification + release</strong></div></div>
        </div>

        <div className="content-grid">
          <section className="main-column">
            <section className="hero-card">
              <div className="hero-copy">
                <div className="client-line"><span className="client-logo">{workflow.client_name?.slice(0, 1).toUpperCase()}</span>{workflow.client_name}</div>
                <h2>Turn this client request into governed delivery.</h2>
                <p>{workflow.client_request}</p>
              </div>
              <div className="hero-metric"><span>Engagement state</span><strong>{titleCase(workflow.state)}</strong><small>Workflow v{workflow.version} · {workflow.workflow_id.slice(0, 8)}</small></div>
            </section>

            {error && <div className="error-banner" role="alert"><Icon name="shield" />{error}</div>}

            <section className="section-card workflow-card" id="workflow">
              <div className="section-heading"><div><p className="eyebrow">Golden path</p><h3>Workforce handoff</h3></div><span className="section-meta">{Math.max(currentStage + 1, 1)} of {STAGES.length}</span></div>
              <div className="stage-list">
                {STAGES.map((stage, index) => {
                  const completed = currentStage > index;
                  const active = currentStage === index;
                  return (
                    <div className={`stage ${completed ? 'completed' : ''} ${active ? 'active' : ''}`} key={stage.label}>
                      <div className="stage-marker">{completed ? <Icon name="check" size={14} /> : index + 1}</div>
                      <div className="stage-copy"><strong>{stage.label}</strong><span>{stage.owner}</span></div>
                      {stage.gate && <span className="gate-chip"><Icon name="lock" size={12} /> Human gate</span>}
                      {active && !stage.gate && <span className="live-chip">Active</span>}
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="section-card artifact-card" id="artifacts">
              <div className="section-heading artifact-heading">
                <div><p className="eyebrow">Versioned deliverable</p><h3>SPECIFICATIONS.md</h3></div>
                {specification ? <div className="artifact-meta"><span className={specification.immutable ? 'status-approved' : 'status-draft'}>{specification.immutable ? 'Approved & locked' : 'Awaiting human review'}</span><code>sha256:{shortHash(specification.sha256)}</code></div> : <span className="status-empty">Created after discovery intake</span>}
              </div>
              <div className={`document-preview ${specification ? '' : 'empty'}`}>
                {specification ? <pre>{specification.content}</pre> : <div className="empty-artifact"><span><Icon name="artifact" size={24} /></span><strong>No specification artifact yet</strong><p>Activate discovery, gather evidence, and let the specialist prepare the first versioned draft.</p></div>}
              </div>
            </section>
          </section>

          <aside className="right-column">
            <section className="section-card action-card">
              <div className="agent-orbit"><span><Icon name="spark" size={20} /></span></div>
              <p className="eyebrow">Current owner</p>
              <h3>{activeAgent?.display_name ?? 'Workforce Manager'}</h3>
              <p>{activeAgent?.purpose ?? 'The registered specialist responsible for this workflow state.'}</p>
              {workflow.state === 'INTAKE' && <button className="primary-button" onClick={startDiscovery} disabled={busy}>{busy ? 'Activating…' : 'Activate discovery'}<Icon name="arrow" /></button>}
              {workflow.state === 'DISCOVERY' && (
                <>
                  {/* The client-facing room is its own route, so a client
                      following the link never lands on this control surface. */}
                  <button className="primary-button" onClick={openMeetingRoom} disabled={busy}>
                    Open Agent OS Meeting Room<Icon name="arrow" />
                  </button>
                  <button className="secondary-button" onClick={createIntakeDraft} disabled={busy}>
                    {busy ? 'Preparing draft…' : 'Skip: draft from intake brief'}
                  </button>
                </>
              )}
              {workflow.state === 'SPEC_REVIEW' && <div className="approval-box"><div className="approval-title"><Icon name="lock" /><span><strong>Human decision required</strong><small>Configured approver: {workforce.specification_approver_email}</small></span></div><button className="approve-button" onClick={approveSpecification} disabled={busy || !specification}>{busy ? 'Locking artifact…' : 'Approve exact hash'}<Icon name="check" /></button></div>}
              {workflow.state === 'PLANNING' && <div className="handoff-complete"><Icon name="check" /><span><strong>Planner handoff authorized</strong><small>The approved hash is the immutable planning source.</small></span></div>}
              <div className="authority-strip"><span><Icon name="shield" size={15} /> Deterministic authority</span><small>Prompts cannot grant tools, approvals, or workflow transitions.</small></div>
            </section>

            <section className="section-card readiness-card">
              <div className="section-heading compact"><div><p className="eyebrow">Adapter readiness</p><h3>Connected operations</h3></div></div>
              <div className="readiness-list">
                <div><span><Icon name="meeting" size={15} /></span><div><strong>Meeting input</strong><small>{meetingModeLabel(workforce.meeting_mode)}</small></div><em className="configured">Configured</em></div>
                <div><span><Icon name="repo" size={15} /></span><div><strong>GitHub boundary</strong><small>OAuth adapter not connected</small></div><em>Pending</em></div>
                <div><span><Icon name="lock" size={15} /></span><div><strong>Human approvers</strong><small>Emails saved; auth not connected</small></div><em className="configured">Configured</em></div>
              </div>
            </section>

            <section className="section-card fleet-card">
              <div className="section-heading compact"><div><p className="eyebrow">Activated template</p><h3>Agent fleet</h3></div><span className="fleet-count">{fleet.length}</span></div>
              <div className="fleet-list">{fleet.map((agent, index) => <div className={`fleet-agent ${agent.role === activeRole ? 'active' : ''}`} key={agent.role}><span className={`agent-index tone-${index}`}>{String(index + 1).padStart(2, '0')}</span><div><strong>{agent.display_name.replace(' Agent', '')}</strong><span>{agent.outputs.length} governed outputs</span></div><span className="agent-state">{agent.role === activeRole ? 'Working' : 'Standby'}</span></div>)}</div>
            </section>

            <section className="section-card policy-card" id="governance">
              <div className="policy-heading"><span><Icon name="shield" /></span><div><p className="eyebrow">Permission proof</p><h3>Try a forbidden action</h3></div></div>
              <p>Ask the Builder to deploy production. The policy gateway must deny it regardless of prompt content.</p>
              <button className="secondary-button" onClick={provePolicyBoundary} disabled={busy}>Evaluate boundary</button>
              {policyDecision && <div className={`decision ${policyDecision.allowed ? 'allow' : 'deny'}`}><strong>{policyDecision.allowed ? 'Allowed' : 'Denied by policy'}</strong><span>{policyDecision.rule_id}</span><small>{policyDecision.reason}</small></div>}
            </section>
          </aside>
        </div>

        <section className="audit-strip" id="audit" aria-label="Audit timeline">
          <div className="audit-title"><span><Icon name="pulse" /></span><div><p className="eyebrow">Execution evidence</p><h3>Audit timeline</h3></div></div>
          <div className="audit-events">{audit.length === 0 ? <div className="audit-empty"><Icon name="clock" /> Consequential actions appear here with trace and rule IDs.</div> : audit.slice(-4).reverse().map((event) => <div className="audit-event" key={event.event_id}><span className={`audit-dot ${event.allowed ? 'allowed' : 'denied'}`} /><div><strong>{titleCase(event.action)}</strong><span>{event.actor} · {event.rule_id}</span></div><code>{event.trace_id.slice(0, 8)}</code></div>)}</div>
        </section>
      </section>
    </main>
  );
}
