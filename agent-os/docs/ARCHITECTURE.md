# Agent OS Foundation Architecture

## System boundary

Agent OS separates probabilistic reasoning from deterministic authority.

```text
Web control room
  -> Control-plane API
      -> Organization + workforce registry
      -> Workflow engine
      -> Policy/tool gateway
      -> Approval service
      -> Artifact store + audit ledger
      -> Google ADK workforce
          -> Manager
          -> Discovery & Specification
          -> Planner & Architect
          -> Builder
          -> Reviewer
      -> bounded external adapters
          -> demo repository
          -> Google Calendar (P1)
          -> staging deployer
```

## Foundation components

| Component | Responsibility | Five-day implementation |
|---|---|---|
| Organization/workforce registry | tenant metadata, template activation, approver and adapter boundaries | in-memory foundation behind stable tenant-scoped contracts |
| Google ADK app | model-backed specialist definitions and delegation | one ADK app with five role definitions using `gemini-3.6-flash` |
| Workflow engine | legal state transitions, idempotency, human gates | in-memory foundation behind stable interfaces; Firestore adapter next |
| Policy engine | role/capability/state decisions | deny by default with auditable decision objects |
| Artifact store | versioned immutable evidence | in-memory foundation; Cloud Storage/Firestore adapter next |
| FastAPI control plane | UI-facing contracts | health, workforce, workflow, transition, and audit endpoints |
| Web control room | meeting, workflow, artifacts, approvals, policy/audit timeline | React/TypeScript application in `web/`, backed only by control-plane APIs |
| Repository jail | bounded code changes and commands | teammate-owned adapter for one demo repository |
| Reviewer profile | deterministic acceptance and security checks | teammate-owned seeded failure/pass pipeline |
| Google Cloud runtime | Vertex AI model access, Cloud Run, persistence, logs/traces | deployed after local golden path passes |

## Workflow states

```text
INTAKE
-> DISCOVERY
-> SPEC_REVIEW
-> PLANNING
-> IMPLEMENTING
-> REVIEWING
-> REVISION_REQUIRED -> REVIEWING
-> RELEASE_REVIEW
-> RELEASE_APPROVED
-> STAGING_RELEASED
```

`SPEC_REVIEW -> PLANNING` and `RELEASE_REVIEW -> RELEASE_APPROVED` require authenticated human actors. Only the deterministic Release Service can execute `RELEASE_APPROVED -> STAGING_RELEASED`. Production is not a valid state.

## Contracts

- Every state change carries a unique idempotency key and trace ID.
- Every policy decision is allow or deny; missing rules deny.
- Every artifact version has a SHA-256 content hash and lineage.
- Approval records refer to immutable artifact hashes, not filenames alone.
- External adapters receive short-lived credentials at execution time.
- Prompts cannot change roles, policies, workflow state, or approvals.

## Web control room foundation

The application begins with a guided organization -> workforce -> engagement flow and
then opens a focused control room. Onboarding collects non-secret operating boundaries;
it never treats an entered owner email as authenticated identity or collects provider
credentials.

The control room presents one engagement as four linked surfaces:

1. the current workforce role and deterministic workflow state;
2. client discovery context and the artifact currently being produced;
3. the exact immutable artifact awaiting a human decision;
4. policy and audit evidence for every consequential action.

The application lives in `web/`, uses React and TypeScript, and calls the FastAPI
control plane through a configurable `VITE_API_BASE_URL`. Client-side state may cache
responses for rendering, but it is not authoritative for workflow transitions,
approvals, permissions, or artifact versions.

The canonical onboarding and enterprise operating flow is defined in
`docs/ENTERPRISE_ONBOARDING.md`.

## Google Cloud target

- Project ID: `agent-os-506220`
- Region: `us-central1`
- Model path: Vertex AI through ADC/managed identity
- Default model: `gemini-3.6-flash` (availability must be verified)
- Initial runtime: Cloud Run; Agent Runtime may replace it after the golden path is stable
- Persistent state: Firestore
- Artifacts: Cloud Storage
- Secrets: Secret Manager
- Observability: Cloud Logging and Cloud Trace

The GCP project owner remains responsible for billing, API enablement, IAM, and managed identities. Editor access alone may not permit those administrative operations.
