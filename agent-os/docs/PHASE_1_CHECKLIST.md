# Phase 1 Setup and Readiness Checklist

## Local readiness snapshot — August 25, 2026

| Tool | Detected status | Phase 1 action |
|---|---|---|
| Git | Installed (`2.54.0.windows.1`) | Ready. |
| Node.js | Installed (`26.2.0`) | Ready; we will confirm framework compatibility before scaffolding. |
| npm | Installed (`11.13.0`) | Ready. |
| Google Cloud CLI | **Not installed** on the current workstation | Corrected August 26, 2026. Google Cloud Shell is the approved workspace for all `gcloud` work — see the note below. |
| `uv` | Installed (`0.12.5`); current Codex session has stale `PATH` | Verified through its installed path. Restart Codex before using `uv` by name. |
| GitHub CLI | Not found on `PATH` | Optional; repositories can be created through github.com. Install later if desired. |
| WinGet | Not found on `PATH` | Use the providers' official Windows installers instead of WinGet commands. |

> **Correction, August 26, 2026.** The earlier snapshot recorded Google Cloud CLI `581.0.0` as installed with a stale `PATH`. That is wrong for this workstation. There is no Cloud SDK under `%LOCALAPPDATA%\Google`, `Program Files\Google`, or `C:\google-cloud-sdk`, and no Cloud SDK entry in the persisted user or machine `PATH`. Restarting the shell will not surface it.

**Decision:** all `gcloud` work is done in **Google Cloud Shell** (<https://shell.cloud.google.com>) rather than on the workstation. Cloud Shell ships `gcloud`, `curl`, `jq`, and Docker preauthenticated, which removes the local install, the `PATH` problem, and the need for `gcloud auth login` on a personal machine. Only `uv` and the Python test suite run locally.

Recommended order:

1. Owner completes [`../infra/OWNER_SETUP.md`](../infra/OWNER_SETUP.md).
2. Arpit opens Cloud Shell and runs [`../infra/scripts/verify-access.sh`](../infra/scripts/verify-access.sh).
3. Create the demo repository in the browser; GitHub CLI is not a Phase 1 blocker.

## 1. Hackathon administration

- [x] Claim Google Cloud credits.
- [ ] Join/confirm the Devpost project and team.
- [ ] Confirm participant eligibility.
- [ ] Record the official deadline in the project calendar.
- [ ] Create a draft submission under the preferred category.

## 2. Google Cloud project

- [x] Create a dedicated teammate-owned GCP project (`agent-os-506220`).
- [ ] Confirm the teammate's redeemed credits are linked to this exact project.
- [ ] Create budget alerts at sensible thresholds.
- [x] Record project ID.
- [ ] Record project number.
- [x] Confirm the primary region as `us-central1` before Firestore creation.
- [ ] Confirm the project owner can use Vertex AI.

Approved initial region: `us-central1`. It provides the safest cross-service fit for Agent Runtime, Sessions, Memory Bank, Agent Gateway, Cloud Run, Firestore, and full Model Armor support.

### Owner actions

Billing linkage, the budget alert, API enablement, the runtime service account, all IAM grants, and the OAuth client are administrative actions that only the project owner (`sv3981158@gmail.com`) can complete. They are written up as a single Console click-through runbook:

**→ [`../infra/OWNER_SETUP.md`](../infra/OWNER_SETUP.md)**

That runbook is the single source of truth for those steps; do not duplicate them here, or the two will drift. It covers billing (§1), the budget guardrail (§2), APIs (§3), the runtime service account (§4–§5), Arpit's roles (§6), the resource-scoped `roles/iam.serviceAccountUser` grant (§7), Artifact Registry / Firestore / Storage / Pub&nbsp;Sub (§8–§11), the OAuth client (§12), and the secret containers (§13).

The owner must never share a password, a `gcloud` credential, a service-account key, or a browser session in order to complete it. Every step is a grant, not a credential transfer.

Core APIs to enable after project creation:

```text
aiplatform.googleapis.com
run.googleapis.com
firestore.googleapis.com
pubsub.googleapis.com
storage.googleapis.com
secretmanager.googleapis.com
cloudbuild.googleapis.com
artifactregistry.googleapis.com
logging.googleapis.com
monitoring.googleapis.com
cloudtrace.googleapis.com
iamcredentials.googleapis.com
modelarmor.googleapis.com
calendar-json.googleapis.com
meet.googleapis.com                 # only if the Meet adapter is selected
```

Do not create permanent service-account keys. Use Application Default Credentials locally and managed identities in Cloud Run/Agent Runtime.

## 3. Google authentication and access verification

Because `gcloud` is not installed on the workstation, this runs in **Google Cloud Shell**. Cloud Shell is already authenticated as the signed-in Google account, so `gcloud auth login` is not needed.

Open <https://shell.cloud.google.com>, then:

```bash
gcloud config set project agent-os-506220
git clone https://github.com/YashVerma06/Agent_OS.git && cd Agent_OS
bash agent-os/infra/scripts/verify-access.sh
```

The script is read-only, costs nothing, and never reads a secret value. It reports pass/fail for billing, all 14 APIs, every deployment permission, the runtime service account and the `actAs` grant, Artifact Registry, Firestore location and mode, the bucket, Pub/Sub, the three secret names, and a live Vertex AI reachability check. Each failure names the `OWNER_SETUP.md` section that fixes it.

Send the output to the owner. It is the objective evidence for this section and for §4 below — far more reliable than re-reading the Console.

- [ ] `verify-access.sh` run in Cloud Shell.
- [ ] Output sent to the owner.
- [ ] Exit code 0 (every required check passing).

> **Open decision — local ADK execution.** Cloud Shell covers administration, verification, and deployment. It does **not** provide Application Default Credentials on the workstation, which `agent-os/README.md` requires for live (non-mocked) ADK runs via `gcloud auth application-default login`. The deterministic test suite is unaffected — it does not call a model. Before the availability spike in §4, choose one:
>
> 1. install the Google Cloud CLI on the workstation after all, purely for ADC; or
> 2. run live ADK execution inside Cloud Shell, keeping the workstation for tests and editing only.
>
> Do not leave this unresolved past the spike — it gates every live Gemini call.

## 4. Enterprise-agent availability spike

Complete this before application scaffolding:

- [ ] Gemini 3.5+ model access verified in the target region.
- [ ] Google ADK local sample can authenticate.
- [ ] Agent Runtime creation/deployment page accessible.
- [ ] Agent Registry publishing/discovery path accessible.
- [ ] Managed Sessions/Memory Bank path accessible.
- [ ] Agent Identity availability checked.
- [ ] Agent Gateway availability checked.
- [ ] Model Armor template creation checked.
- [ ] Cloud Trace/Logging permissions checked.

Record each result as `available`, `preview/conditional`, `blocked`, or `fallback required`. Never label a fallback as an official integration.

## 5. Google OAuth and meeting account

- [x] Choose the dedicated demo Google account (recorded locally; not tracked).
- [x] Choose Agent OS Meeting Room with a Google Calendar invite as the MVP meeting flow.
- [ ] Configure OAuth consent screen in Testing mode.
- [ ] Add the demo Google account as a test user.
- [ ] Create a Web OAuth client.
- [ ] Register the local callback URL.
- [ ] Register the deployed callback URL after Cloud Run exists.
- [ ] Grant only the calendar scopes needed to create/update demo events.
- [ ] Store the client secret and refresh token in Secret Manager.

Owner performs all of the above — step-by-step in [`../infra/OWNER_SETUP.md`](../infra/OWNER_SETUP.md) §12 (consent screen, test user, scopes, Web client) and §13 (secret containers). The deployed callback URL stays open until Cloud Run exists and its URL is known.

Recommended MVP meeting design:

```text
Manager Agent creates Google Calendar event
-> event contains Agent OS Meeting Room URL
-> Sales Agent participates in controlled room
-> transcript is finalized as a versioned artifact
```

## 6. GitHub

- [x] Choose the GitHub user/organization (`YashVerma06`).
- [x] Create the main repository (`https://github.com/YashVerma06/Agent_OS`).
- [x] Connect this workspace to the main repository as Git remote `origin`.
- [ ] Create `agent-os-demo-maintenance-portal` repository.
- [ ] Protect the default branch of the demo repository.
- [ ] Create a fine-grained token scoped only to the demo repository.
- [ ] Grant Metadata read, Contents read/write, and Pull Requests read/write.
- [ ] Store the token in Secret Manager.
- [ ] Confirm no token appears in chat, source control, logs, or screenshots.

## 7. Phase 1 approval gate

- [ ] Owner approves `PRODUCT_SCOPE.md`.
- [ ] Owner approves `PERMISSION_MATRIX.md`.
- [ ] Owner completes `PHASE_1_INTAKE.md`.
- [ ] Cloud/platform capability results are documented.
- [ ] No unresolved naming or identity decision blocks scaffolding.
- [ ] No secrets exist in tracked files.

The local foundation is now scaffolded on `codex/arpit-foundation`. Cloud deployment remains blocked until the project/IAM/API checks above are complete.

**Definition of unblocked:** `infra/scripts/verify-access.sh` exits 0 in Cloud Shell. Until then, treat cloud deployment as blocked regardless of what the Console appears to show.
