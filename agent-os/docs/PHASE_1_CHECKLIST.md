# Phase 1 Setup and Readiness Checklist

## Local readiness snapshot — August 25, 2026

| Tool | Detected status | Phase 1 action |
|---|---|---|
| Git | Installed (`2.54.0.windows.1`) | Ready. |
| Node.js | Installed (`26.2.0`) | Ready; we will confirm framework compatibility before scaffolding. |
| npm | Installed (`11.13.0`) | Ready. |
| Google Cloud CLI | Installed (`581.0.0`); current Codex session has stale `PATH` | Verified through its installed path. Restart Codex before using `gcloud` by name. |
| `uv` | Installed (`0.12.5`); current Codex session has stale `PATH` | Verified through its installed path. Restart Codex before using `uv` by name. |
| GitHub CLI | Not found on `PATH` | Optional; repositories can be created through github.com. Install later if desired. |
| WinGet | Not found on `PATH` | Use the providers' official Windows installers instead of WinGet commands. |

Recommended installation order:

1. Restart Codex so the updated user `PATH` is inherited.
2. Verify `gcloud --version` and `uv --version` by name.
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

### Owner action: link billing

This is a financial-account action and must be completed by the owner in Google Cloud Console.

1. Sign in with the teammate GCP admin account and select project `agent-os-506220`.
2. Open **Billing > My projects**.
3. Find `agent-os-506220`, open its **Actions** menu, and choose **Change billing**.
4. Select the billing account containing the claimed hackathon credits and choose **Set account**.
5. Return to **Billing > My projects** and verify that the project row displays the intended billing-account name instead of **Billing is disabled**.
6. Never share the payment method, billing-account ID, card details, or recovery information in chat or source control.

### Owner action: create the budget alert

Complete this immediately after billing is linked.

1. Keep `agent-os-506220` selected and open **Billing > Budgets & alerts**.
2. Choose **Create budget** and select **Alerts only**.
3. Name it `Agent OS Hackathon Guardrail`.
4. Scope it only to project `agent-os-506220`; include all services.
5. Choose a fixed budget amount that represents the maximum spend you want visibility on, even if credits are expected to cover usage.
6. Add actual-spend thresholds at 25%, 50%, 75%, 90%, and 100%.
7. Enable email notifications for billing administrators/users and finish creating the budget.
8. Remember: a budget alert sends notifications; it does not automatically stop resources or cap spending. Automated shutdown controls can be added separately after the core deployment works.

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
modelarmor.googleapis.com
calendar-json.googleapis.com
meet.googleapis.com                 # only if the Meet adapter is selected
```

Do not create permanent service-account keys. Use Application Default Credentials locally and managed identities in Cloud Run/Agent Runtime.

## 3. Local Google authentication

Run only after the project ID is known:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project agent-os-506220

$env:GOOGLE_CLOUD_PROJECT="agent-os-506220"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
$env:GOOGLE_GENAI_USE_VERTEXAI="TRUE"
```

Then verify the current Google agent toolchain:

```powershell
uvx google-agents-cli setup
agents-cli login -i
agents-cli login --status
```

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
