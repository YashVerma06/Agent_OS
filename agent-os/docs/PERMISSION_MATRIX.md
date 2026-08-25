# Agent OS Permission Matrix

## Enforcement principle

Prompts describe behavior; they never grant authority. Every consequential action follows this deterministic chain:

```text
authenticated actor
-> requested capability
-> tool gateway
-> role + resource + workflow-state policy
-> human approval check when required
-> short-lived provider credential
-> bounded execution with idempotency key
-> audit event
```

No agent receives raw provider credentials or an unrestricted shell.

## Autonomy levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Observe | Read and recommend only. |
| 1 | Draft | Create versioned internal artifacts. |
| 2 | Execute with approval | Prepare an action; execute only after an authenticated human approves it. |
| 3 | Execute within policy | Execute a narrow action inside explicit role, resource, state, command, and budget limits. |

## Reduced role matrix

| Actor | Default autonomy | Allowed capabilities | Explicitly forbidden |
|---|---:|---|---|
| Workforce Manager Agent | 1 | inspect workflow; delegate to registered specialist; request clarification/approval; propose a calendar event | decide approval; repository write; spec mutation; merge; deployment; IAM change |
| Discovery & Specification Agent | 1 | participate in assigned meeting; read assigned context; write transcript, discovery, clarification, and specification artifacts | calendar mutation; repository access; commercial commitment; self-approval; deployment |
| Planner & Architect Agent | 1 | read approved spec/repository metadata; write build plan, dependency graph, contracts, and architecture notes | change requirements; write application code; approve; deploy |
| Builder Agent | 3 | read/write the assigned demo repository on an allowlisted branch; apply patch; run allowlisted test/build commands; commit | other repositories; protected branches; secrets; spec mutation; merge; deploy; unrestricted shell/network |
| Reviewer Agent | 1 | read approved spec and Builder diff; run deterministic QA/security profile; create traceability, findings, pass, and revision artifacts | edit code; waive its own findings; change acceptance criteria; merge; deploy |
| Deterministic Release Service | 2 | create release manifest and deploy the approved immutable artifact to configured staging | bypass evidence; edit code; deploy production; accept natural-language approval as authority |
| Human approver | n/a | approve/reject specification, exceptions, protected merge, and staging release within tenant scope | act outside authenticated role/tenant scope |

## Core capability policy

| Capability | Manager | Discovery | Planner | Builder | Reviewer | Release service | Human |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| workflow.inspect | allow | allow | allow | allow | allow | allow | allow |
| agent.delegate | allow | deny | deny | deny | deny | deny | deny |
| calendar.event.create | approval | deny | deny | deny | deny | deny | allow |
| artifact.specification.write | deny | allow | deny | deny | deny | deny | deny |
| artifact.plan.write | deny | deny | allow | deny | deny | deny | deny |
| repository.write | deny | deny | deny | state-bound | deny | deny | deny |
| test.run | deny | deny | deny | allowlisted | allowlisted | deny | deny |
| security.scan | deny | deny | deny | deny | allowlisted | deny | deny |
| approval.decide | deny | deny | deny | deny | deny | deny | allow |
| deployment.staging | deny | deny | deny | deny | deny | approved only | approve |
| deployment.production | deny | deny | deny | deny | deny | deny | disabled |

## Builder boundary

```yaml
principal: builder-agent:v1
allow:
  - repository.read
  - repository.write
  - workspace.apply_patch
  - test.run
  - build.run
  - git.commit
conditions:
  repository: agent-os-demo-maintenance-portal
  branch_prefix: agentos/
  workflow_state: [IMPLEMENTING, REVISION_REQUIRED]
  command_profile: demo-web-app
deny:
  - protected_branch.write
  - secret.read
  - specification.write
  - deployment.*
  - shell.unrestricted
```

## Required denial demonstrations

1. Discovery Agent attempts calendar creation → denied.
2. Discovery Agent attempts repository write → denied.
3. Builder invoked before specification approval → denied.
4. Builder attempts protected-branch write → denied.
5. Builder requests a secret → denied.
6. Release requested before Reviewer pass and human approval → denied.
7. Production deployment request → denied.
8. Prompt-injection content requesting a secret upload is stored as untrusted data; no tool executes.

Every denial emits an `AuditEvent` containing actor, capability, resource, workflow state, trace ID, idempotency key, policy rule, and denial reason.
