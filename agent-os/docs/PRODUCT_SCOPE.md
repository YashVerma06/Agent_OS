# Agent OS Hackathon MVP — Five-Day Frozen Scope

## Product thesis

Agent OS is infrastructure for creating and operating governed AI workforces. The MVP proves the platform through one software-enterprise workflow that converts an ambiguous client request into reviewed software under explicit human governance.

## Winning demonstration

```text
Client
-> controlled discovery meeting
-> Discovery & Specification Agent
-> transcript + discovery record + SPECIFICATIONS.md
-> human specification approval
-> Planner & Architect Agent
-> requirement-linked build plan
-> Builder Agent
-> real repository branch and patch
-> Reviewer Agent detects a seeded defect
-> structured revision request
-> Builder repair
-> Reviewer quality and security pass
-> human release approval
-> staging outcome + policy/audit timeline
```

## Demo client request

> We manage rental properties and need a small maintenance-request portal. Tenants should submit a maintenance issue, and our property manager should see requests and update their status.

The request is intentionally incomplete. Discovery must clarify users, fields, workflow states, validation, authentication, attachments, notifications, success criteria, and explicit exclusions.

## Approved product output

### Tenant request form

- name, email, unit number, category, description, and severity;
- client and server validation.

### Property manager dashboard

- list and inspect maintenance requests;
- update status to New, In Progress, or Resolved;
- responsive layout;
- deterministic demo storage.

### Seeded review failure

The first Builder attempt exposes `Resolved` in the Manager UI while the API/schema rejects that value. The Reviewer must detect the mismatch against the approved requirement, create a revision request, and route the workflow back to the Builder. The repaired build must pass the same deterministic check.

## Reduced fleet

The five-day MVP uses five LLM-backed roles instead of nine:

1. **Workforce Manager Agent** — understands status, delegates to the correct specialist, and requests permitted actions; it cannot approve its own work.
2. **Discovery & Specification Agent** — conducts discovery and produces the versioned specification.
3. **Planner & Architect Agent** — converts an approved specification into a requirement-linked implementation plan and architecture notes.
4. **Builder Agent** — works in the allowlisted demo repository and branch, creates patches, and runs allowlisted checks.
5. **Reviewer Agent** — performs requirement-linked QA and security review and issues pass or revision evidence.

Release execution is a deterministic service, not another LLM agent. Workflow state, approvals, policy, artifacts, audit, identity, and the tool gateway are also deterministic platform services.

## Required artifacts

```text
MEETING_TRANSCRIPT-v1.json
DISCOVERY_RECORD-v1.json
SPECIFICATIONS-v1.md
BUILD_PLAN-v1.json
ARCHITECTURE_NOTES-v1.md
PATCH-v1.diff
REVIEW_REPORT-v1.json
REVISION_REQUEST-v1.json
PATCH-v2.diff
REVIEW_REPORT-v2.json
RELEASE_MANIFEST-v1.json
```

Each artifact records its version, SHA-256 hash, source artifact IDs, generator identity/version, workflow ID, creation time, and approval status. Approved artifacts are immutable; changes create a new version.

## Mandatory human gates

- specification approval;
- material scope changes;
- security exceptions;
- protected-branch merge;
- staging release approval;
- every production deployment, which remains disabled for the hackathon.

## P0 — submission critical

- professional 1440×900 control-room UI;
- controlled meeting transcript and meaningful discovery clarification;
- versioned specification with human approval;
- Google ADK agent graph using `gemini-3.6-flash` through Vertex AI;
- real Builder change in an isolated branch;
- deterministic failure, revision, and passing re-run;
- combined QA/security evidence from the Reviewer;
- at least one visible policy denial;
- persistent workflow/audit data and idempotent consequential actions;
- deployed Google Cloud backend with observable logs/traces;
- deterministic demo reset.

## P1 — only after the golden path is stable

- Google Calendar invite integration;
- Agent Registry publication;
- Agent Gateway enforcement beyond the local policy gateway;
- Gemini Live voice;
- richer memory, cost, and rollback views;
- independently deployed A2A specialists.

## Non-goals

- arbitrary Google Meet participation;
- multiple industries;
- universal software generation across stacks;
- unrestricted shell or network access;
- autonomous merge or production deployment;
- full CRM, Jira, GitHub, or billing replacement.

## Technical decision

The foundation uses Python 3.11+, `uv`, Google ADK 2.x, FastAPI, Vertex AI, and a deterministic policy/workflow core. The default model is `gemini-3.6-flash`, following the current Google ADK project structure. Model availability must still be verified inside project `agent-os-506220` before the live demo.
