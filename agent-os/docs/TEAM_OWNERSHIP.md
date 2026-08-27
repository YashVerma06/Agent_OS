# Four-Person Team Ownership

The five-day build uses folder ownership and pull requests to reduce merge conflicts. Replace the placeholder member names once the team shares them.

## Branch flow

1. Arpit maintains `codex/arpit-foundation` as the temporary integration branch.
2. Every teammate branches from the latest `origin/codex/arpit-foundation`.
3. Each teammate opens a small pull request back into `codex/arpit-foundation`.
4. Arpit integrates and runs the golden-path checks.
5. The verified foundation is submitted to `main` through one reviewed pull request.

No one pushes directly to `main`.

## Work division

| Owner | Suggested branch | Primary responsibility | Five-day deliverable |
|---|---|---|---|
| **Arpit — Product & Foundation Lead** | `codex/arpit-foundation` | architecture, contracts, workflow state machine, policy gateway, integration, demo narrative | stable contracts/API; permission denials; integrated golden path; final demo build |
| **Yash — Discovery Experience** | `feature/discovery-experience` | professional web control room, meeting transcript experience, Discovery/Specification Agent, specification approval UI | meeting → transcript → spec → approval flow with polished responsive UI |
| **Piyush — Planning & Build Runtime** | `feature/planner-builder` | Planner and Builder agents, repository jail, allowlisted command runner, real branch/patch flow, seeded bug and repair | approved spec → plan → real patch → deterministic repair loop |
| **Kushagra — Review, Cloud & Reliability** | `feature/reviewer-cloud` | Reviewer Agent, QA/security checks, Firestore/Cloud Storage adapters, Cloud Run/Vertex deployment, logging/tracing, demo reset | review fail/pass evidence, persistent Google Cloud proof, repeatable deployment/reset |

## Foundation-owned files

Arpit owns the shared contracts and integration seams. Teammates add specialist
modules and adapters without editing these files unless a focused contract change
is agreed first:

- `app/contracts.py`, `app/agent.py`, and `app/fast_api_app.py`;
- `app/platform/workflow.py`, `app/platform/policy.py`, and
  `app/platform/artifacts.py`;
- `app/orchestration/` and package `__init__.py` files;
- `web/app/lib/api.ts` and `web/app/lib/types.ts`.

Specialist ownership is isolated under `app/agents/`, `app/services/`,
`app/adapters/`, and separate API router modules. Arpit performs the final router
and ADK composition wiring on the integration branch.

## Shared contracts that require Arpit review

- workflow states and transition actions;
- artifact schemas and hashes;
- capability names and policy decisions;
- API request/response schemas;
- environment variable names;
- demo repository and branch conventions.

If a teammate needs to change a shared contract, update the relevant document and open a focused contract pull request before implementing dependent work.

## Pull-request rule

Each pull request must state:

- golden-path step affected;
- tests executed;
- configuration added;
- new permissions requested;
- whether the demo reset still works;
- screenshots for visible UI changes.
