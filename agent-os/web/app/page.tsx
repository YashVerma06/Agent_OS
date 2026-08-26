'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Icon, type IconName } from './components/icon';
import './landing.css';

/* -------------------------------------------------------------------------- */
/* Content                                                                     */
/*                                                                            */
/* Every claim below is traceable to docs/PRODUCT_SCOPE.md, docs/              */
/* PERMISSION_MATRIX.md, or app/platform/*.py. Nothing here describes a        */
/* capability the platform does not implement.                                 */
/* -------------------------------------------------------------------------- */

const PIPELINE_STEPS = ['Discover', 'Specify', 'Plan', 'Build', 'Review', 'Release'] as const;

interface Station {
  /** Must match the offset-path coordinates in landing.css. */
  x: number;
  label: string;
  sub: string;
  /** Seconds into the 13s cycle when the travelling packet reaches this stop. */
  delay: number;
  gate?: string;
  /** Build lights twice: once on the first pass, once on the repair. */
  rePulse?: number;
}

const STATIONS: Station[] = [
  { x: 120, label: 'Discover', sub: 'DISCOVERY', delay: 0 },
  { x: 324, label: 'Specify', sub: 'SPEC_REVIEW', delay: 1.3, gate: 'HUMAN GATE' },
  { x: 528, label: 'Plan', sub: 'PLANNING', delay: 2.6 },
  { x: 732, label: 'Build', sub: 'IMPLEMENTING', delay: 3.9, rePulse: 7.8 },
  { x: 936, label: 'Review', sub: 'REVIEWING', delay: 5.2 },
  { x: 1140, label: 'Release', sub: 'STAGING', delay: 12.2, gate: 'HUMAN GATE' },
];

const PROOF = [
  { figure: '5', label: 'specialist roles', note: 'One manager, four specialists' },
  { figure: '11', label: 'workflow states', note: 'Every transition is explicit' },
  { figure: '0', label: 'service-account keys', note: 'Managed identity only' },
  { figure: '0', label: 'models in the release path', note: 'Deployment is deterministic' },
];

const PILLARS: { icon: IconName; tone: string; title: string; body: string }[] = [
  {
    icon: 'shield',
    tone: 'iris',
    title: 'Control',
    body: 'Authority lives in deterministic policy code, never in a prompt. Human approval is required at every consequential step, and the gate is enforced by the state machine rather than requested politely.',
  },
  {
    icon: 'workflow',
    tone: 'cyan',
    title: 'Coordination',
    body: 'Specialists never message each other. Work advances through a workflow engine and is handed off as versioned, hash-addressed artifacts, so no step depends on another agent behaving.',
  },
  {
    icon: 'artifact',
    tone: 'mint',
    title: 'Accountability',
    body: 'Every action and every denial emits an audit event carrying actor, capability, workflow state, policy rule, and trace ID. The refusals are as inspectable as the approvals.',
  },
];

interface FleetMember {
  no: string;
  role: string;
  name: string;
  body: string;
  produces: string;
  cannot: string;
  /** True only for the Release Service, which is deliberately not an agent. */
  service?: boolean;
}

const FLEET: FleetMember[] = [
  {
    no: 'AGENT / 01',
    role: 'Coordination',
    name: 'Workforce Manager',
    body: 'Reads workflow status, delegates to the correct specialist, and raises approval requests when a gate is reached.',
    produces: 'Assignments, approval requests',
    cannot: 'Approve its own request, write code, deploy',
  },
  {
    no: 'AGENT / 02',
    role: 'Requirements',
    name: 'Discovery & Specification',
    body: 'Interrogates an ambiguous client request until users, data, states, acceptance criteria and exclusions are explicit, then drafts the versioned specification.',
    produces: 'Transcript, discovery record, SPECIFICATIONS.md',
    cannot: 'Touch a repository, approve its own specification',
  },
  {
    no: 'AGENT / 03',
    role: 'Architecture',
    name: 'Planner & Architect',
    body: 'Works only from an approved specification, mapping every critical requirement to tasks, interfaces, verification steps and architecture notes.',
    produces: 'Build plan, architecture notes',
    cannot: 'Change requirements, write application code',
  },
  {
    no: 'AGENT / 04',
    role: 'Implementation',
    name: 'Builder',
    body: 'Implements approved tasks inside a repository jail on an allowlisted branch, using an allowlisted command runner instead of a shell.',
    produces: 'Patches, build evidence',
    cannot: 'Read secrets, write protected branches, deploy',
  },
  {
    no: 'AGENT / 05',
    role: 'Assurance',
    name: 'Reviewer',
    body: 'Traces every critical requirement to deterministic evidence, then issues either a structured revision request or a pass. Independent of the Builder by construction.',
    produces: 'Review reports, revision requests',
    cannot: 'Edit code, waive its own findings, approve release',
  },
  {
    no: 'SERVICE / 06',
    role: 'Deterministic',
    name: 'Release Service',
    body: 'Executes the staging release. This is ordinary code with no model in it, because the step with the most consequence is the step that should have the least improvisation.',
    produces: 'Release manifest, staging outcome',
    cannot: 'Run without a reviewer pass and a human approval',
    service: true,
  },
];

const DENIALS = [
  { attempt: 'Discovery Agent requests calendar creation', rule: 'calendar.human_gate' },
  { attempt: 'Builder invoked before specification approval', rule: 'repository.workflow_state' },
  { attempt: 'Builder writes outside the agentos/ branch jail', rule: 'repository.branch_jail' },
  { attempt: 'Builder requests a secret value', rule: 'global.explicit_deny' },
  { attempt: 'Release requested before the Reviewer passed', rule: 'gate.review_evidence_missing' },
  { attempt: 'Production deployment requested', rule: 'global.explicit_deny' },
];

const MECHANISMS = [
  {
    q: 'When',
    title: 'The workflow engine',
    body: 'A transition table maps (state, action) to the next state and the roles allowed to trigger it. The Builder cannot act early because no transition exists for it anywhere else.',
    file: 'app/platform/workflow.py',
  },
  {
    q: 'What',
    title: 'The artifact store',
    body: 'Work is handed off as immutable versions carrying a SHA-256 hash and the IDs of their sources. Approval binds to the hash, so approving a specification approves exactly those bytes.',
    file: 'app/platform/artifacts.py',
  },
  {
    q: 'Whether',
    title: 'The policy engine',
    body: 'Deny by default. Every capability is checked against role, workflow state, target resource and the presence of a human approval. A missing rule is a denial, not an oversight.',
    file: 'app/platform/policy.py',
  },
];

interface JourneyStage {
  stage: string;
  title: string;
  body: string;
  tag: string;
  gate?: boolean;
  alert?: boolean;
}

const JOURNEY: JourneyStage[] = [
  {
    stage: '01',
    title: 'An ambiguous request arrives',
    body: 'A client says they manage rental properties and need a maintenance portal. That is not a specification. The Discovery Agent clarifies users, fields, workflow states, validation and explicit exclusions until it becomes one.',
    tag: 'INTAKE → DISCOVERY',
  },
  {
    stage: '02',
    title: 'A human approves the specification',
    body: 'The approval is bound to the artifact hash, not the filename. Change a byte and the approval no longer matches. Only an authenticated human actor can move this transition.',
    tag: 'SPEC_REVIEW → PLANNING',
    gate: true,
  },
  {
    stage: '03',
    title: 'The plan becomes a real code change',
    body: 'The Planner maps requirements to tasks. The Builder implements them inside a repository jail, on a branch it is allowed to touch, running only allowlisted commands.',
    tag: 'PLANNING → IMPLEMENTING',
  },
  {
    stage: '04',
    title: 'Independent review catches a real defect',
    body: 'The Manager UI offers a status the API rejects. The Reviewer traces it to the approved requirement, files a structured revision request, and the workflow routes back to the Builder.',
    tag: 'REVIEWING → REVISION_REQUIRED',
    alert: true,
  },
  {
    stage: '05',
    title: 'The repair is verified, not asserted',
    body: 'The Builder repairs. The Reviewer re-runs the same deterministic check and passes. Release approval stays impossible until that pass exists on the record.',
    tag: 'REVISION_REQUIRED → REVIEWING',
  },
  {
    stage: '06',
    title: 'A human releases to staging',
    body: 'The deterministic release service executes only after a reviewer pass and an authenticated human approval. Production is not a reachable state.',
    tag: 'RELEASE_APPROVED → STAGING_RELEASED',
    gate: true,
  },
];

/* -------------------------------------------------------------------------- */

function Arrow() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h13M13 6l6 6-6 6" />
    </svg>
  );
}

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [motionOk, setMotionOk] = useState(true);
  const [activeStep, setActiveStep] = useState(0);
  const [journeyStage, setJourneyStage] = useState(0);
  const parallaxRefs = useRef<(HTMLElement | null)[]>([]);

  // Respect the OS motion preference for everything JS-driven. The stylesheet
  // handles the CSS half; this switch also removes the travelling packets from
  // the DOM so nothing animates off-screen.
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setMotionOk(!query.matches);
    sync();
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  // Smooth anchor scrolling, set on the scrolling element and restored on
  // unmount so the control room at / keeps its default behaviour.
  useEffect(() => {
    if (!motionOk) return;
    const root = document.documentElement;
    const previous = root.style.scrollBehavior;
    root.style.scrollBehavior = 'smooth';
    return () => { root.style.scrollBehavior = previous; };
  }, [motionOk]);

  // Nav background, and parallax on the hero layers. One rAF-throttled scroll
  // listener drives both so we never lay out twice in a frame.
  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        const y = window.scrollY;
        setScrolled(y > 12);
        if (motionOk) {
          parallaxRefs.current.forEach((node) => {
            if (!node) return;
            const speed = Number(node.dataset.speed ?? 0);
            node.style.transform = `translate3d(0, ${y * speed}px, 0)`;
          });
        }
        frame = 0;
      });
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [motionOk]);

  // Scroll reveals.
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('.lp-reveal'));
    if (!motionOk) {
      nodes.forEach((node) => node.setAttribute('data-visible', 'true'));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.setAttribute('data-visible', 'true');
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.12 },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [motionOk]);

  // Hero request card cycles through the pipeline so the card is never static.
  useEffect(() => {
    if (!motionOk) return;
    const timer = window.setInterval(() => {
      setActiveStep((step) => (step + 1) % PIPELINE_STEPS.length);
    }, 1400);
    return () => window.clearInterval(timer);
  }, [motionOk]);

  // Sticky journey: the left panel tracks whichever stage is crossing the
  // middle of the viewport.
  useEffect(() => {
    const stages = Array.from(document.querySelectorAll<HTMLElement>('[data-stage-index]'));
    if (!stages.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setJourneyStage(Number((entry.target as HTMLElement).dataset.stageIndex));
          }
        });
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 },
    );
    stages.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="lp-root" data-motion={motionOk ? 'on' : 'off'}>
      {/* Reveals start at opacity 0 and are switched on by IntersectionObserver.
          Without JS that would render a blank page, so undo it up front. */}
      <noscript>
        <style>{'.lp-reveal{opacity:1 !important;transform:none !important}'}</style>
      </noscript>

      {/* ------------------------------------------------------------- nav -- */}
      <header className="lp-nav" data-scrolled={scrolled}>
        <div className="lp-nav-inner">
          <a className="lp-brand" href="#top">
            <span className="lp-brand-mark"><Icon name="spark" size={17} /></span>
            Agent OS
          </a>
          <nav className="lp-nav-links">
            <a className="lp-nav-link" href="#platform">Platform</a>
            <a className="lp-nav-link" href="#problem">Problem</a>
            <a className="lp-nav-link" href="#fleet">Agent fleet</a>
            <a className="lp-nav-link" href="#connect">How it connects</a>
          </nav>
          <Link className="lp-btn lp-btn--primary lp-btn--sm" href="/console">
            Enter control room <Arrow />
          </Link>
        </div>
      </header>

      {/* ------------------------------------------------------------ hero -- */}
      <section className="lp-hero lp-section" id="top">
        <div className="lp-aurora" aria-hidden="true">
          <div className="lp-aurora-layer lp-aurora-layer--a" data-speed="0.16" ref={(n) => { parallaxRefs.current[0] = n; }} />
          <div className="lp-aurora-layer lp-aurora-layer--b" data-speed="0.28" ref={(n) => { parallaxRefs.current[1] = n; }} />
          <div className="lp-aurora-layer lp-aurora-layer--c" data-speed="0.09" ref={(n) => { parallaxRefs.current[2] = n; }} />
        </div>
        <div className="lp-grid-veil" aria-hidden="true" />

        <div className="lp-hero-grid">
          <div className="lp-reveal" data-visible="true">
            <p className="lp-eyebrow">Governed AI workforces</p>
            <h1 className="lp-h1">
              Build an AI workforce
              <br />
              you can trust to ship.
            </h1>
            <p className="lp-lead">
              Agent OS is the infrastructure layer for creating and operating governed AI
              workforces. One client conversation becomes an approved specification, a real
              code change, an independent review, and a release no agent can authorise.
            </p>
            <div className="lp-hero-actions">
              <a className="lp-btn lp-btn--primary" href="#connect">See how it works <Arrow /></a>
              <a className="lp-btn lp-btn--ghost" href="#fleet">Meet the fleet</a>
              <span className="lp-hero-note">Built for accountable delivery</span>
            </div>
          </div>

          <div
            className="lp-request-card lp-reveal"
            data-delay="2"
            data-speed="-0.05"
            ref={(n) => { parallaxRefs.current[3] = n; }}
          >
            <div className="lp-request-head">
              <span className="lp-mono lp-request-id">Request / 0147</span>
              <span className="lp-chip lp-chip--live"><i className="lp-dot" /> In flight</span>
            </div>
            <p className="lp-request-quote">
              &ldquo;We manage rental properties and need a small maintenance-request portal.&rdquo;
            </p>
            <div className="lp-request-rail">
              {PIPELINE_STEPS.map((step, index) => (
                <span key={step} className="lp-request-step" data-on={index <= activeStep}>
                  {step}
                </span>
              ))}
            </div>
            <div className="lp-request-foot">
              <span className="lp-chip lp-chip--gate"><Icon name="lock" size={11} /> Gate</span>
              <span className="lp-mono">Human approval required before staging release</span>
            </div>
          </div>
        </div>

        <div className="lp-trust lp-reveal" data-delay="3">
          {['Deny by default', 'SHA-256 artifact lineage', 'Immutable audit trail', 'No service-account keys', 'Production locked'].map((item) => (
            <span className="lp-trust-item" key={item}>
              <span className="lp-accent-mint"><Icon name="check" size={14} /></span>
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* ----------------------------------------------------------- proof -- */}
      <div className="lp-divider" />
      <section className="lp-section lp-proof-section">
        <div className="lp-proof">
          {PROOF.map((item, index) => (
            <div className="lp-proof-item lp-reveal" data-delay={index} key={item.label}>
              <span className="lp-proof-figure">{item.figure}</span>
              <span className="lp-proof-label">{item.label}</span>
              <span className="lp-proof-note">{item.note}</span>
            </div>
          ))}
        </div>
      </section>

      {/* -------------------------------------------------------- platform -- */}
      <section className="lp-section" id="platform">
        <div className="lp-section-head">
          <div className="lp-reveal">
            <p className="lp-eyebrow">What Agent OS is</p>
            <h2 className="lp-h2">The operating layer for accountable AI delivery.</h2>
          </div>
          <div className="lp-reveal" data-delay="1">
            <p className="lp-lead">
              Agent OS Labs builds infrastructure, not an assistant. Agent OS replaces isolated
              prompts and opaque handoffs with a governed workforce where every decision,
              artifact and release gate is visible, reviewable and owned by a named actor.
            </p>
          </div>
        </div>

        <div className="lp-cards">
          {PILLARS.map((pillar, index) => (
            <article className="lp-card lp-reveal" data-delay={index} key={pillar.title}>
              <span className="lp-card-icon" data-tone={pillar.tone}><Icon name={pillar.icon} size={19} /></span>
              <h3 className="lp-h3">{pillar.title}</h3>
              <p className="lp-body">{pillar.body}</p>
            </article>
          ))}
        </div>

        <div className="lp-goal lp-reveal" data-delay="2">
          <p className="lp-eyebrow">Our goal</p>
          <p className="lp-goal-text">
            Make AI work <span className="lp-accent-mint">employable</span> — accountable enough
            that an enterprise can put it on the org chart, not just in a sandbox.
          </p>
        </div>
      </section>

      {/* --------------------------------------------------------- problem -- */}
      <div className="lp-divider" />
      <section className="lp-section" id="problem">
        <div className="lp-section-head">
          <div className="lp-reveal">
            <p className="lp-eyebrow">The problem we solve</p>
            <h2 className="lp-h2">Prompts are not permissions.</h2>
          </div>
          <div className="lp-reveal" data-delay="1">
            <p className="lp-lead">
              Agent demos work in a sandbox and stall in an enterprise, because four questions
              have no answer: who authorised this, what evidence backs it, what structurally
              prevented something worse, and can you prove all three afterwards?
            </p>
          </div>
        </div>

        <div className="lp-problem-grid">
          <div className="lp-problem-copy lp-reveal">
            <p className="lp-body">
              The root cause is a category error. <strong className="lp-accent-cyan">&ldquo;Never
              deploy to production&rdquo; in a system prompt is a suggestion</strong> made to a
              probabilistic text generator. Once an agent holds a shell and a token, the only
              thing between you and an incident is the model behaving as described.
            </p>
            <p className="lp-body">
              Agent OS moves that boundary into code. Agents propose; deterministic services
              decide. Prompts shape behaviour and never grant authority, so an instruction the
              model ignores changes nothing about what it is able to do.
            </p>
            <p className="lp-body">
              Every refusal on the right is produced by the policy engine, recorded with its
              rule ID, and rendered in the control room. The denials are evidence, not errors.
            </p>
          </div>

          <div className="lp-deny-panel lp-reveal" data-delay="1">
            <div className="lp-request-head">
              <span className="lp-mono lp-request-id">Policy decisions</span>
              <span className="lp-chip lp-chip--deny">Denied</span>
            </div>
            {DENIALS.map((denial) => (
              <div className="lp-deny-row" key={denial.rule + denial.attempt}>
                <div>
                  <span className="lp-body">{denial.attempt}</span>
                  <code className="lp-mono lp-deny-rule">{denial.rule}</code>
                </div>
                <span className="lp-accent-iris"><Icon name="lock" size={15} /></span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------------- fleet -- */}
      <div className="lp-divider" />
      <section className="lp-section" id="fleet">
        <div className="lp-section-head">
          <div className="lp-reveal">
            <p className="lp-eyebrow">A specialist workforce, not a black box</p>
            <h2 className="lp-h2">Every agent has one job and one clear handoff.</h2>
          </div>
          <div className="lp-reveal" data-delay="1">
            <p className="lp-lead">
              Five model-backed specialists carry the work forward through durable artifacts.
              The sixth block is deliberately not an agent — release execution is deterministic
              code, because the step with the most consequence should have the least improvisation.
            </p>
          </div>
        </div>

        <div className="lp-fleet">
          {FLEET.map((agent, index) => (
            <article
              className={`lp-agent lp-reveal${agent.service ? ' lp-agent--service' : ''}`}
              data-delay={index % 3}
              key={agent.name}
            >
              <span className="lp-mono lp-agent-no">{agent.no}</span>
              <span className="lp-agent-role">{agent.role}</span>
              <h3 className="lp-h3">{agent.name}</h3>
              <p className="lp-body">{agent.body}</p>
              <div className="lp-agent-meta">
                <div className="lp-agent-row">
                  <span className="lp-agent-key">Makes</span>
                  <span className="lp-agent-val">{agent.produces}</span>
                </div>
                <div className="lp-agent-row">
                  <span className="lp-agent-key">Cannot</span>
                  <span className="lp-agent-val lp-agent-val--deny">{agent.cannot}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* --------------------------------------------------------- connect -- */}
      <div className="lp-divider" />
      <section className="lp-section" id="connect">
        <div className="lp-section-head">
          <div className="lp-reveal">
            <p className="lp-eyebrow">How the agents connect</p>
            <h2 className="lp-h2">They never talk to each other.</h2>
          </div>
          <div className="lp-reveal" data-delay="1">
            <p className="lp-lead">
              There is no agent-to-agent chat passing work along. A request travels a
              deterministic pipeline, and three platform services decide when it moves, what
              moves with it, and whether it is allowed at all.
            </p>
          </div>
        </div>

        <div className="lp-pipeline-shell lp-reveal">
          <svg className="lp-pipeline-svg" viewBox="0 0 1260 250" role="img" aria-label="A request travels from Discover through Specify, Plan, Build and Review, loops back to Build when the Reviewer requests a revision, then proceeds to Release.">
            {/* rails */}
            <path className="lp-track" d="M 120 96 L 1140 96" />
            <path className="lp-flow" d="M 120 96 L 1140 96" />
            <path className="lp-track lp-track--branch" d="M 936 96 C 936 200 732 200 732 96" />
            <text className="lp-station-sub" x="834" y="222" fill="rgba(242,119,119,0.7)">
              REVISION REQUIRED
            </text>

            {/* stations */}
            {STATIONS.map((station) => (
              <g key={station.label}>
                {station.gate ? (
                  <>
                    <rect className="lp-gate-badge" x={station.x - 44} y={34} width={88} height={20} rx={10} />
                    <text className="lp-gate-text" x={station.x} y={48}>{station.gate}</text>
                  </>
                ) : null}
                <circle
                  className="lp-station-glow"
                  cx={station.x}
                  cy={96}
                  r={14}
                  style={{ animationDelay: `${station.delay}s` }}
                />
                <circle className="lp-station-ring" cx={station.x} cy={96} r={14} />
                <circle
                  className="lp-station-core"
                  cx={station.x}
                  cy={96}
                  r={6}
                  style={{ animationDelay: `${station.delay}s` }}
                />
                {station.rePulse ? (
                  <circle
                    className="lp-station-glow"
                    cx={station.x}
                    cy={96}
                    r={14}
                    style={{ animationDelay: `${station.rePulse}s` }}
                  />
                ) : null}
                <text className="lp-station-label" x={station.x} y={140}>{station.label}</text>
                <text className="lp-station-sub" x={station.x} y={159}>{station.sub}</text>
              </g>
            ))}

            {/* travelling request */}
            {motionOk ? (
              <>
                <g className="lp-packet lp-packet--a">
                  <circle className="lp-packet-halo" r={11} />
                  <circle className="lp-packet-core" r={4.5} />
                </g>
                <g className="lp-packet lp-packet--b">
                  <circle className="lp-packet-halo" r={11} fill="rgba(242,119,119,0.26)" />
                  <circle className="lp-packet-core" r={4.5} fill="#ffd9d9" />
                </g>
                <g className="lp-packet lp-packet--c">
                  <circle className="lp-packet-halo" r={11} />
                  <circle className="lp-packet-core" r={4.5} />
                </g>
              </>
            ) : null}
          </svg>

          <div className="lp-pipeline-legend">
            <span className="lp-legend-item">
              <span className="lp-legend-swatch" style={{ background: 'var(--cyan)' }} /> Request in flight
            </span>
            <span className="lp-legend-item">
              <span className="lp-legend-swatch" style={{ background: 'var(--red)' }} /> Revision loop on a failed review
            </span>
            <span className="lp-legend-item">
              <span className="lp-legend-swatch" style={{ background: 'var(--iris)' }} /> Human gate, enforced in the state machine
            </span>
          </div>
        </div>

        <div className="lp-mech">
          {MECHANISMS.map((mech, index) => (
            <article className="lp-mech-card lp-reveal" data-delay={index} key={mech.title}>
              <p className="lp-mech-q lp-accent-cyan">{mech.q}</p>
              <h3 className="lp-h3">{mech.title}</h3>
              <p className="lp-body">{mech.body}</p>
              <code className="lp-mono lp-mech-file">{mech.file}</code>
            </article>
          ))}
        </div>
      </section>

      {/* --------------------------------------------------------- journey -- */}
      <div className="lp-divider" />
      <section className="lp-section lp-journey-section">
        <div className="lp-journey">
          <aside className="lp-journey-aside">
            <p className="lp-eyebrow">One request, end to end</p>
            <h2 className="lp-h2">From client conversation to a staging-ready change.</h2>
            <p className="lp-body">
              The workflow engine holds eleven states. These are the six that matter to the
              people watching, including the one where the review actually catches something.
            </p>
            <div className="lp-journey-track">
              {JOURNEY.map((item, index) => (
                <span
                  className="lp-journey-tick"
                  data-on={index <= journeyStage}
                  key={item.stage}
                >
                  <i />
                  <span className="lp-mono">{item.stage}</span>
                </span>
              ))}
            </div>
          </aside>

          <div className="lp-journey-stages">
            {JOURNEY.map((item, index) => (
              <article
                className="lp-journey-stage lp-reveal"
                data-stage-index={index}
                data-active={index === journeyStage}
                key={item.stage}
              >
                <div className="lp-journey-stage-head">
                  <span className="lp-mono lp-journey-no">{item.stage}</span>
                  {item.gate ? <span className="lp-chip lp-chip--gate"><Icon name="lock" size={11} /> Human gate</span> : null}
                  {item.alert ? <span className="lp-chip lp-chip--deny">Defect found</span> : null}
                </div>
                <h3 className="lp-h3">{item.title}</h3>
                <p className="lp-body">{item.body}</p>
                <code className="lp-mono lp-journey-tag">{item.tag}</code>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ governance -- */}
      <div className="lp-divider" />
      <section className="lp-section">
        <div className="lp-section-head lp-section-head--center">
          <div className="lp-reveal">
            <p className="lp-eyebrow">Enforcement, not etiquette</p>
            <h2 className="lp-h2">Three independent locks on every write.</h2>
            <p className="lp-lead">
              For the Builder to change a single file, three unrelated conditions must hold at
              once. Miss any one and the request is denied with the rule that stopped it.
            </p>
          </div>
        </div>

        <div className="lp-locks">
          <article className="lp-lock lp-reveal">
            <p className="lp-lock-no">Lock 01 — Role</p>
            <p className="lp-body">The actor must hold the capability. Roles are frozen sets in code, not sentences in a prompt.</p>
            <code className="lp-mono lp-code">BUILDER → repository.write</code>
          </article>
          <article className="lp-lock lp-reveal" data-delay="1">
            <p className="lp-lock-no">Lock 02 — State</p>
            <p className="lp-body">The workflow must be mid-build or mid-repair. In any other state the same actor with the same role is refused.</p>
            <code className="lp-mono lp-code">IMPLEMENTING | REVISION_REQUIRED</code>
          </article>
          <article className="lp-lock lp-reveal" data-delay="2">
            <p className="lp-lock-no">Lock 03 — Resource</p>
            <p className="lp-body">The target must sit inside the branch jail. Protected branches are globally denied and cannot be re-enabled by configuration.</p>
            <code className="lp-mono lp-code">branch startswith &quot;agentos/&quot;</code>
          </article>
        </div>
      </section>

      {/* ------------------------------------------------------------- cta -- */}
      <div className="lp-cta">
        <section className="lp-section">
          <div className="lp-reveal">
            <p className="lp-eyebrow">Move fast without surrendering control</p>
            <h2 className="lp-h2">Put the workforce on the org chart.</h2>
            <p className="lp-lead" style={{ margin: '0 auto 36px' }}>
              Agent OS turns fragmented AI assistance into a governed operating system for
              software delivery, so your team can inspect the work, direct the workforce and
              own the release.
            </p>
            <div className="lp-hero-actions" style={{ justifyContent: 'center' }}>
              <Link className="lp-btn lp-btn--primary" href="/console">Enter the control room <Arrow /></Link>
              <a className="lp-btn lp-btn--ghost" href="#fleet">Review the fleet</a>
            </div>
          </div>
        </section>
      </div>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <span>Agent OS Labs — infrastructure for governed AI workforces.</span>
          <span className="lp-footer-links">
            <a href="#platform">Platform</a>
            <a href="#fleet">Fleet</a>
            <a href="#connect">Architecture</a>
            <Link href="/console">Control room</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
