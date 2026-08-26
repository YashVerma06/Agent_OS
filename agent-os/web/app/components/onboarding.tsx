'use client';

import Link from 'next/link';
import { useMemo, useState, type ReactNode } from 'react';
import type {
  AgentDefinition,
  CompanySize,
  MeetingMode,
  PlatformHealth,
  WorkforceTemplate,
} from '../lib/types';
import { Icon } from './icon';

export interface OnboardingDraft {
  organizationName: string;
  legalName: string;
  ownerName: string;
  ownerEmail: string;
  companySize: CompanySize;
  templateId: string;
  workforceName: string;
  meetingMode: MeetingMode;
  repositoryUrl: string;
  baseBranch: string;
  workingBranchPrefix: string;
  specificationApproverEmail: string;
  releaseApproverEmail: string;
  clientName: string;
  projectName: string;
  clientContactName: string;
  clientContactEmail: string;
  clientRequest: string;
}

const STEPS = [
  { label: 'Organization', caption: 'Create workspace' },
  { label: 'Workforce', caption: 'Select the fleet' },
  { label: 'Boundaries', caption: 'Define authority' },
  { label: 'Engagement', caption: 'Add first project' },
];

const MEETING_OPTIONS: Array<{
  value: MeetingMode;
  title: string;
  description: string;
  status: string;
}> = [
  {
    value: 'agent_os_room',
    title: 'Agent OS Meeting Room',
    description: 'Use the native controlled room when the realtime meeting adapter is connected.',
    status: 'Recommended',
  },
  {
    value: 'transcript_upload',
    title: 'Transcript upload',
    description: 'Start from a transcript supplied by your team or an approved meeting provider.',
    status: 'Supported next',
  },
  {
    value: 'written_brief',
    title: 'Written discovery brief',
    description: 'Begin with the client request entered during engagement creation.',
    status: 'Available now',
  },
];

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const REPOSITORY_PATTERN = /^https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/?$/;

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Onboarding({
  health,
  templates,
  fleet,
  busy,
  error,
  onSubmit,
}: {
  health: PlatformHealth | null;
  templates: WorkforceTemplate[];
  fleet: AgentDefinition[];
  busy: boolean;
  error: string | null;
  onSubmit: (draft: OnboardingDraft) => void;
}) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<OnboardingDraft>({
    organizationName: '',
    legalName: '',
    ownerName: '',
    ownerEmail: '',
    companySize: '11-50',
    templateId: '',
    workforceName: 'Software Product Delivery Workforce',
    meetingMode: 'written_brief',
    repositoryUrl: '',
    baseBranch: 'main',
    workingBranchPrefix: 'agentos/',
    specificationApproverEmail: '',
    releaseApproverEmail: '',
    clientName: '',
    projectName: '',
    clientContactName: '',
    clientContactEmail: '',
    clientRequest: '',
  });

  const selectedTemplate =
    templates.find((template) => template.template_id === draft.templateId) ?? templates[0];

  const stepValid = useMemo(() => {
    if (step === 0) {
      return (
        draft.organizationName.trim().length >= 2 &&
        draft.ownerName.trim().length >= 2 &&
        EMAIL_PATTERN.test(draft.ownerEmail)
      );
    }
    if (step === 1) {
      return Boolean(selectedTemplate && draft.workforceName.trim().length >= 3);
    }
    if (step === 2) {
      return (
        REPOSITORY_PATTERN.test(draft.repositoryUrl) &&
        draft.baseBranch.trim().length > 0 &&
        draft.workingBranchPrefix.trim().length >= 2 &&
        EMAIL_PATTERN.test(draft.specificationApproverEmail) &&
        EMAIL_PATTERN.test(draft.releaseApproverEmail)
      );
    }
    return (
      draft.clientName.trim().length >= 2 &&
      draft.projectName.trim().length >= 3 &&
      draft.clientRequest.trim().length >= 20 &&
      (!draft.clientContactEmail || EMAIL_PATTERN.test(draft.clientContactEmail))
    );
  }, [draft, selectedTemplate, step]);

  function update<K extends keyof OnboardingDraft>(key: K, value: OnboardingDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function nextStep() {
    if (!stepValid) return;
    if (step === 0) {
      setDraft((current) => ({
        ...current,
        templateId: current.templateId || selectedTemplate?.template_id || '',
        specificationApproverEmail: current.specificationApproverEmail || current.ownerEmail,
        releaseApproverEmail: current.releaseApproverEmail || current.ownerEmail,
      }));
    }
    setStep((current) => Math.min(current + 1, STEPS.length - 1));
  }

  return (
    <main className="onboarding-shell">
      <section className="onboarding-story">
        <Link className="onboarding-brand" href="/"><span className="brand-mark">A<span>O</span></span><div><strong>Agent OS</strong><small>Workforce infrastructure</small></div></Link>
        <div className="story-copy">
          <p className="eyebrow">Build the operating system for your AI team</p>
          <h1>Activate a governed workforce for real client delivery.</h1>
          <p>Configure the people, agents, tools, and approval boundaries once. Then run every engagement through the same observable operating model.</p>
        </div>
        <div className="story-flow" aria-label="Agent OS operating flow">
          {[
            ['01', 'Discover', 'Client meeting or approved input'],
            ['02', 'Specify', 'Versioned requirements and decisions'],
            ['03', 'Build', 'Bounded repository implementation'],
            ['04', 'Review', 'Independent QA and security evidence'],
          ].map(([number, title, caption]) => (
            <div className="story-stage" key={number}>
              <span>{number}</span><div><strong>{title}</strong><small>{caption}</small></div><Icon name="chevron" size={15} />
            </div>
          ))}
        </div>
        <div className="story-trust">
          <span><Icon name="shield" size={16} /> Deterministic permissions</span>
          <span><Icon name="lock" size={16} /> Mandatory human gates</span>
          <span><Icon name="pulse" size={16} /> Complete audit evidence</span>
        </div>
      </section>

      <section className="onboarding-panel">
        <header className="onboarding-header">
          <div>
            <p className="eyebrow">Enterprise setup</p>
            <h2>Create your Agent OS workspace</h2>
          </div>
          <div className={`connection ${health ? 'online' : 'offline'}`}><span className="connection-dot" />{health ? 'Platform ready' : 'API offline'}</div>
        </header>

        <div className="onboarding-steps">
          {STEPS.map((item, index) => (
            <button
              type="button"
              className={`onboarding-step ${index === step ? 'active' : ''} ${index < step ? 'complete' : ''}`}
              key={item.label}
              onClick={() => index < step && setStep(index)}
              disabled={index > step}
            >
              <span>{index < step ? <Icon name="check" size={13} /> : index + 1}</span>
              <div><strong>{item.label}</strong><small>{item.caption}</small></div>
            </button>
          ))}
        </div>

        <div className="onboarding-form">
          {step === 0 && (
            <section className="form-section">
              <div className="form-intro"><span><Icon name="building" /></span><div><h3>Organization profile</h3><p>This becomes the tenant boundary for every workforce, engagement, artifact, and approval.</p></div></div>
              <div className="form-grid two-columns">
                <Field label="Organization name"><input value={draft.organizationName} onChange={(event) => update('organizationName', event.target.value)} placeholder="e.g. Acme Software" autoFocus /></Field>
                <Field label="Legal name" hint="Optional for the hackathon foundation"><input value={draft.legalName} onChange={(event) => update('legalName', event.target.value)} placeholder="Registered company name" /></Field>
                <Field label="Workspace owner"><input value={draft.ownerName} onChange={(event) => update('ownerName', event.target.value)} placeholder="Full name" /></Field>
                <Field label="Owner email" hint="Stored as configuration until Supabase Auth is connected"><input type="email" value={draft.ownerEmail} onChange={(event) => update('ownerEmail', event.target.value)} placeholder="owner@company.com" /></Field>
                <Field label="Company size"><select value={draft.companySize} onChange={(event) => update('companySize', event.target.value as CompanySize)}>{['1-10', '11-50', '51-200', '201-1000', '1000+'].map((size) => <option value={size} key={size}>{size} employees</option>)}</select></Field>
              </div>
              <div className="truth-note"><Icon name="shield" size={16} /><span><strong>Identity boundary</strong>This foundation does not treat the entered email as authenticated. Verification, sessions, and SSO are connected before external deployment.</span></div>
            </section>
          )}

          {step === 1 && (
            <section className="form-section">
              <div className="form-intro"><span><Icon name="team" /></span><div><h3>Select the workforce</h3><p>Templates define agent roles, permitted outputs, required gates, and explicit denials.</p></div></div>
              {selectedTemplate && (
                <div className="template-card selected">
                  <div className="template-icon"><Icon name="spark" size={22} /></div>
                  <div className="template-copy"><span className="selected-chip"><Icon name="check" size={11} /> Selected</span><h4>{selectedTemplate.display_name}</h4><p>{selectedTemplate.description}</p><div className="template-facts"><span>{selectedTemplate.agent_roles.length} specialist agents</span><span>{selectedTemplate.human_gates.length} mandatory human gates</span><span>v{selectedTemplate.version}</span></div></div>
                </div>
              )}
              <Field label="Workforce name" hint="Your organization can activate more workforce templates later"><input value={draft.workforceName} onChange={(event) => update('workforceName', event.target.value)} /></Field>
              <div className="fleet-preview">
                {fleet.map((agent, index) => (
                  <div className="fleet-preview-agent" key={agent.role}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{agent.display_name}</strong><small>{agent.purpose}</small></div><em>{agent.outputs.length} outputs</em></div>
                ))}
              </div>
            </section>
          )}

          {step === 2 && (
            <section className="form-section">
              <div className="form-intro"><span><Icon name="settings" /></span><div><h3>Operating boundaries</h3><p>Define where agents may work and which humans retain decision authority.</p></div></div>
              <div className="subsection-label"><Icon name="meeting" size={15} /> Discovery input</div>
              <div className="choice-grid">
                {MEETING_OPTIONS.map((option) => (
                  <button type="button" className={`choice-card ${draft.meetingMode === option.value ? 'selected' : ''}`} key={option.value} onClick={() => update('meetingMode', option.value)}>
                    <span className="choice-radio">{draft.meetingMode === option.value && <span />}</span><div><strong>{option.title}</strong><p>{option.description}</p><small>{option.status}</small></div>
                  </button>
                ))}
              </div>
              <div className="subsection-label"><Icon name="repo" size={15} /> Repository jail</div>
              <div className="form-grid repository-grid">
                <Field label="GitHub repository URL" hint="Configuration only—no token or secret is collected"><input value={draft.repositoryUrl} onChange={(event) => update('repositoryUrl', event.target.value)} placeholder="https://github.com/organization/repository" /></Field>
                <Field label="Base branch"><input value={draft.baseBranch} onChange={(event) => update('baseBranch', event.target.value)} /></Field>
                <Field label="Agent branch prefix"><input value={draft.workingBranchPrefix} onChange={(event) => update('workingBranchPrefix', event.target.value)} /></Field>
              </div>
              <div className="subsection-label"><Icon name="lock" size={15} /> Human authority</div>
              <div className="form-grid two-columns">
                <Field label="Specification approver"><input type="email" value={draft.specificationApproverEmail} onChange={(event) => update('specificationApproverEmail', event.target.value)} /></Field>
                <Field label="Release approver"><input type="email" value={draft.releaseApproverEmail} onChange={(event) => update('releaseApproverEmail', event.target.value)} /></Field>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="form-section">
              <div className="form-intro"><span><Icon name="workflow" /></span><div><h3>Create the first engagement</h3><p>This client project becomes the first governed workflow operated by your workforce.</p></div></div>
              <div className="form-grid two-columns">
                <Field label="Client or business unit"><input value={draft.clientName} onChange={(event) => update('clientName', event.target.value)} placeholder="e.g. Orbit Retail" autoFocus /></Field>
                <Field label="Project name"><input value={draft.projectName} onChange={(event) => update('projectName', event.target.value)} placeholder="e.g. Customer operations portal" /></Field>
                <Field label="Client contact" hint="Optional"><input value={draft.clientContactName} onChange={(event) => update('clientContactName', event.target.value)} placeholder="Full name" /></Field>
                <Field label="Client contact email" hint="Optional"><input type="email" value={draft.clientContactEmail} onChange={(event) => update('clientContactEmail', event.target.value)} placeholder="contact@client.com" /></Field>
              </div>
              <Field label="Initial client request" hint={`${draft.clientRequest.length}/10,000 characters`}><textarea value={draft.clientRequest} onChange={(event) => update('clientRequest', event.target.value)} placeholder="Describe the problem, users, desired outcome, constraints, and any known deadlines. The Discovery Agent will clarify what is missing." rows={6} /></Field>
              <div className="activation-summary">
                <div><span>Organization</span><strong>{draft.organizationName}</strong></div>
                <Icon name="chevron" />
                <div><span>Workforce</span><strong>{draft.workforceName}</strong></div>
                <Icon name="chevron" />
                <div><span>First engagement</span><strong>{draft.projectName || 'Enter project name'}</strong></div>
              </div>
              <div className="truth-note"><Icon name="lock" size={16} /><span><strong>Activation outcome</strong>The Manager may delegate discovery. Agents still cannot self-approve specifications, access secrets, write protected branches, or deploy production.</span></div>
            </section>
          )}
        </div>

        {error && <div className="error-banner" role="alert"><Icon name="shield" />{error}</div>}

        <footer className="onboarding-actions">
          <button type="button" className="text-button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0 || busy}>Back</button>
          <div><span>Step {step + 1} of {STEPS.length}</span>{step < STEPS.length - 1 ? (
            <button type="button" className="primary-button compact-button" onClick={nextStep} disabled={!stepValid}>Continue <Icon name="arrow" /></button>
          ) : (
            <button type="button" className="primary-button activate-button" onClick={() => onSubmit(draft)} disabled={!stepValid || busy || !health}>
              {busy ? 'Activating workspace…' : 'Activate workforce'} <Icon name="spark" />
            </button>
          )}</div>
        </footer>
      </section>
    </main>
  );
}
