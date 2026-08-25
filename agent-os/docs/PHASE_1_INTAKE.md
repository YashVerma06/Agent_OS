# Phase 1 Owner Intake

This document collects the decisions that only the project owner can make. You may fill this file directly or paste the response template at the bottom into the Codex task.

## Security rule

Safe to provide:

- names and branding preferences;
- GCP project ID and region;
- Google test-account email address;
- GitHub username or organization;
- repository names;
- public URLs and OAuth redirect URLs;
- whether an account/setup step is complete.

Never provide in chat or commit:

- Google passwords;
- API keys;
- OAuth client secrets or refresh tokens;
- GitHub personal access tokens;
- service-account JSON files;
- recovery codes;
- billing or card details.

Real credentials will be entered by the owner in the relevant provider console and stored in Google Secret Manager. Codex only needs the secret resource name, not its value.

## A. Product identity

You can accept all recommended defaults and change them later before UI implementation.

| Field | Recommended default | Owner answer |
|---|---|---|
| Product name | Agent OS | Agent OS |
| Software enterprise name | Agent OS Labs | |
| One-line tagline | The operating system for governed AI workforces. | |
| Demo client company | Replaceable synthetic fixture | Deferred until demo scripting |
| Demo client representative | Replaceable synthetic fixture | Deferred until demo scripting |
| Demo product | Maintenance Request Portal | |
| Human approver | Arpit, Founder / Product Director | |
| Primary UI mood | Premium enterprise control room | |
| Primary palette | Deep navy, ivory, blue, amber, emerald | |

## B. Google Cloud

| Field | Example | Owner answer/status |
|---|---|---|
| Credits claimed | yes | yes |
| GCP project created | yes/no | yes |
| GCP project ID | `agent-os-hackathon-2026` | `agent-os-506220` |
| Billing attached to that project | yes/no | Teammate redeemed credits; project linkage still requires verification |
| Budget alert created | yes/no | Not confirmed |
| Preferred region | `us-central1` | Approved |
| Project owner/admin Google email | `name@example.com` | `sv3981158@gmail.com` |
| Arpit project role | IAM role | Editor; additional service-specific roles may be required |
| Dedicated demo/test Google email | `name@example.com` | Received; stored only in ignored local config |
| Agent Runtime page accessible | yes/no/not checked | |
| Agent Registry page accessible | yes/no/not checked | |
| Model Armor page accessible | yes/no/not checked | |

Do not create Firestore until the region decision is confirmed because database location is consequential and difficult to change later.

## C. Google meeting setup

Choose one for the MVP:

- **Recommended:** Google Calendar invite containing the Agent OS Meeting Room URL. The Sales Agent participates inside the controlled room.
- Optional stretch: also create a Google Meet space and ingest supported post-meeting artifacts.

Owner choice: Agent OS Meeting Room URL inside a Google Calendar invite

Google account used to create demo calendar events: Received; stored only in ignored local config

## D. GitHub

| Field | Recommended default | Owner answer/status |
|---|---|---|
| GitHub username/organization | owner choice | `YashVerma06` |
| Main repository | `agent-os` | `https://github.com/YashVerma06/Agent_OS` - connected as `origin` |
| Demo product repository | `agent-os-demo-maintenance-portal` | Not created |
| Repositories created | yes/no | Main: yes; demo: no |
| Main branch protection enabled | yes/no | |
| Fine-grained token created | yes/no - do not paste it | |

The team repository is public, but branch pushes still require Arpit's authenticated collaborator access. Any GitHub token for the private demo repository should be scoped only to that repository with Metadata read, Contents read/write, and Pull Requests read/write.

## E. Demo decisions

These are product-level demo assumptions. The client name and representative are replaceable fixtures and can be selected after the platform is functional.

Please approve or change these assumptions:

1. The client starts with: "We manage rental properties and need a small maintenance-request portal."
2. Required tenant form fields: name, email, unit number, category, description, severity.
3. Manager statuses: New, In Progress, Resolved.
4. No authentication, payments, notifications, or photo upload in the hackathon build.
5. The seeded QA defect is: the Manager UI offers the Resolved state, but the API initially rejects it.
6. The human approves `SPECIFICATIONS.md` and the final staging release.
7. Staging deployment is allowed; production deployment remains locked.

Owner changes: ______________________________

## Fastest response format

Copy this block into the Codex task and fill only what you know. Use `ACCEPT` for recommended defaults and `UNKNOWN` where setup is incomplete.

```text
ACCEPT_RECOMMENDED_PRODUCT_DEFAULTS: yes/no
PRODUCT_NAME:
SOFTWARE_ENTERPRISE_NAME: optional for Phase 1
HUMAN_APPROVER_NAME_AND_TITLE:

GCP_PROJECT_CREATED: yes/no
GCP_PROJECT_ID:
GCP_REGION: us-central1/other/unknown
GCP_ADMIN_EMAIL:
GOOGLE_DEMO_EMAIL:
AGENT_RUNTIME_ACCESS: yes/no/not checked
AGENT_REGISTRY_ACCESS: yes/no/not checked
MODEL_ARMOR_ACCESS: yes/no/not checked

MEETING_OPTION: recommended/Google Meet stretch/undecided

GITHUB_OWNER:
MAIN_REPOSITORY_CREATED: yes/no
DEMO_REPOSITORY_CREATED: yes/no

ACCEPT_DEMO_ASSUMPTIONS: yes/no
REQUESTED_CHANGES:
```
