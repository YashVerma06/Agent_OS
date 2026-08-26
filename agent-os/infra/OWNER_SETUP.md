# Owner Setup Runbook — Google Cloud Console

**Who performs this:** the project/billing owner (`sv3981158@gmail.com`).
**Where:** Google Cloud Console, in the owner's own browser.
**Project:** `agent-os-506220` · **Region:** `us-central1`
**Estimated time:** 30–45 minutes.

Every step below is a Console click-through. No terminal is required.

---

## 0. Read this first

### Security boundary

The owner must **never** share any of the following with a teammate, an assistant, a chat window, or source control:

- the Google account password or recovery codes;
- a `gcloud` credential file or an authenticated shell session;
- a service-account JSON key (this project creates **none** — see below);
- the browser session, via screen-share of an authenticated console with secrets visible;
- billing-account ID, payment method, or card details.

Everything in this runbook is an **administrative grant**, not a credential transfer. When it is done, Arpit authenticates as *himself* and Cloud Run authenticates as *itself*. No secret changes hands.

### The no-keys rule

`AGENTS.md` and `infra/README.md` forbid service-account keys. Do **not** click "Create key" anywhere in this runbook. Local development uses Application Default Credentials; Cloud Run uses an attached managed identity. If a step ever seems to require a downloaded `.json` key, stop and raise it — the answer is a different grant, not a key.

### What already exists

| Item | Status |
|---|---|
| Project `agent-os-506220` | Created |
| Region `us-central1` | Approved, not yet materialised in Firestore |
| Arpit's role | `roles/editor` |
| Credits | Redeemed by owner; **linkage to this project unverified** |

`roles/editor` is broad and already covers most day-to-day resource creation. The genuinely missing capabilities — the reason this runbook exists — are the things Editor deliberately excludes: **changing IAM policy**, **linking billing**, and **creating an OAuth client**. Do not assume which of the other grants Arpit already has; §14 has him measure it rather than guess.

---

## 1. Link the credited billing account

Credits that are redeemed but not linked to *this* project spend nothing and protect nothing. This is the single highest-priority step — Vertex AI, Cloud Run, and Artifact Registry will all refuse to work without it.

1. Open <https://console.cloud.google.com/billing/linkedaccount?project=agent-os-506220>.
2. Confirm the project selector at the top reads **agent-os-506220**.
3. If the page shows *"This project has no billing account"*, click **Link a billing account**.
4. Choose the billing account that holds the redeemed hackathon credits, then click **Set account**.
5. Go to **Billing → My projects** and confirm the `agent-os-506220` row shows the billing-account **name** rather than *Billing is disabled*.

**Done when:** the project row names a billing account.

---

## 2. Create the budget guardrail

Do this immediately after §1, while billing is fresh in mind.

1. Open <https://console.cloud.google.com/billing/budgets>, selecting the billing account from §1.
2. Click **Create budget** and choose scope **Alerts only**.
3. Name: `Agent OS Hackathon Guardrail`.
4. Scope: **Projects → agent-os-506220** only. Include all services.
5. Set a fixed budget amount representing the maximum spend you want visibility on — set it even though credits are expected to cover usage.
6. Add **actual-spend** thresholds at **25%, 50%, 75%, 90%, 100%**.
7. Enable email notification to billing admins and users. Click **Finish**.

> **Note:** a budget alert **notifies**; it does **not** cap spend or stop resources. Treat it as a smoke detector, not a sprinkler.

**Done when:** the budget appears in the list, scoped to one project, with five thresholds.

---

## 3. Enable the required APIs

Each link below opens that API's page with the project preselected. Click **Enable** on each and wait for the button to become **Manage**. Several take 30–60 seconds.

| API | Why Agent OS needs it | Enable |
|---|---|---|
| `aiplatform.googleapis.com` | Gemini reasoning via Vertex AI | [Enable](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project=agent-os-506220) |
| `run.googleapis.com` | Control plane hosting | [Enable](https://console.cloud.google.com/apis/library/run.googleapis.com?project=agent-os-506220) |
| `firestore.googleapis.com` | Workflow and audit metadata | [Enable](https://console.cloud.google.com/apis/library/firestore.googleapis.com?project=agent-os-506220) |
| `storage.googleapis.com` | Immutable artifact store | [Enable](https://console.cloud.google.com/apis/library/storage.googleapis.com?project=agent-os-506220) |
| `secretmanager.googleapis.com` | Provider credentials | [Enable](https://console.cloud.google.com/apis/library/secretmanager.googleapis.com?project=agent-os-506220) |
| `pubsub.googleapis.com` | Workflow event topic | [Enable](https://console.cloud.google.com/apis/library/pubsub.googleapis.com?project=agent-os-506220) |
| `cloudbuild.googleapis.com` | Builds the container image | [Enable](https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=agent-os-506220) |
| `artifactregistry.googleapis.com` | Stores the container image | [Enable](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com?project=agent-os-506220) |
| `logging.googleapis.com` | Audit trail | [Enable](https://console.cloud.google.com/apis/library/logging.googleapis.com?project=agent-os-506220) |
| `monitoring.googleapis.com` | Service health | [Enable](https://console.cloud.google.com/apis/library/monitoring.googleapis.com?project=agent-os-506220) |
| `cloudtrace.googleapis.com` | Request tracing | [Enable](https://console.cloud.google.com/apis/library/cloudtrace.googleapis.com?project=agent-os-506220) |
| `iamcredentials.googleapis.com` | Managed identity and impersonation | [Enable](https://console.cloud.google.com/apis/library/iamcredentials.googleapis.com?project=agent-os-506220) |
| `modelarmor.googleapis.com` | Prompt/response screening (P1) | [Enable](https://console.cloud.google.com/apis/library/modelarmor.googleapis.com?project=agent-os-506220) |
| `calendar-json.googleapis.com` | Demo meeting invites | [Enable](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=agent-os-506220) |

`meet.googleapis.com` is **only** needed if the Google Meet stretch adapter is selected. Per `PHASE_1_INTAKE.md` §C the chosen MVP flow is a Calendar invite containing the Agent OS Meeting Room URL, so **skip Meet for now**.

If any API refuses to enable with a billing error, §1 did not take effect — return to it.

**Done when:** all 14 show **Manage** instead of **Enable**.

---

## 4. Create the runtime service account

This is the identity Cloud Run assumes at runtime. It is what makes the "managed identity, no keys" rule possible.

1. Open <https://console.cloud.google.com/iam-admin/serviceaccounts?project=agent-os-506220>.
2. Click **Create service account**.
3. **Service account name:** `agent-os-runtime`
   The **Service account ID** field must auto-fill to `agent-os-runtime`. If it does not, type it exactly — the resulting address must be
   `agent-os-runtime@agent-os-506220.iam.gserviceaccount.com`.
4. **Description:** `Runtime identity for the Agent OS control plane on Cloud Run.`
5. Click **Create and continue**.
6. On **Grant this service account access to project**, add the roles listed in §5 now — this is the same role picker. Then **Continue** and **Done**.
7. Back on the list, confirm the account exists and the **Keys** column shows no keys. **Do not create a key.**

> If the account already exists, skip creation and go straight to §5.

**Done when:** `agent-os-runtime@agent-os-506220.iam.gserviceaccount.com` is listed with **zero** keys.

---

## 5. Grant roles TO the runtime service account

These say what the *deployed application* may do. If you added them during §4 step 6, verify them here instead.

1. Open <https://console.cloud.google.com/iam-admin/iam?project=agent-os-506220>.
2. Tick **Include Google-provided role grants** (top right) so the list is complete.
3. Find `agent-os-runtime@agent-os-506220.iam.gserviceaccount.com`, click the **pencil** icon, and use **Add another role** for each row below.

| Role to add | Role ID | Why the running app needs it |
|---|---|---|
| Vertex AI User | `roles/aiplatform.user` | Call the Gemini model for agent reasoning |
| Cloud Datastore User | `roles/datastore.user` | Read/write workflow state and audit records in Firestore |
| Storage Object Admin | `roles/storage.objectAdmin` | Write and read immutable artifacts |
| Secret Manager Secret Accessor | `roles/secretmanager.secretAccessor` | Read the OAuth and GitHub credential **values** at runtime |
| Pub/Sub Publisher | `roles/pubsub.publisher` | Emit workflow events |
| Pub/Sub Subscriber | `roles/pubsub.subscriber` | Consume workflow events |
| Logs Writer | `roles/logging.logWriter` | Write the audit trail |
| Cloud Trace Agent | `roles/cloudtrace.agent` | Emit traces |

4. Click **Save**.

**Deliberately not granted:** `roles/run.developer`, `roles/artifactregistry.writer`, `roles/editor`, `roles/owner`. The runtime identity must not be able to redeploy or rewrite itself.

> **Tightening note (post-hackathon, not now):** `roles/secretmanager.secretAccessor` and `roles/storage.objectAdmin` are cleaner when granted on the individual secret and the single bucket rather than the whole project. Project-level is acceptable for the five-day build; record it as known debt rather than leaving it undocumented.

**Done when:** the runtime account shows all 8 roles, and neither Editor nor Owner.

---

## 6. Grant Arpit the deployment roles (project level)

These say what *the human deploying* may do. Arpit is `tech.team@agiledonetech.com`.

1. Still on <https://console.cloud.google.com/iam-admin/iam?project=agent-os-506220>.
2. Find `tech.team@agiledonetech.com` and click the **pencil** icon. If he is not listed, use **Grant access** and enter that address as the principal.
3. Add each role below.

| Role to add | Role ID | Unlocks |
|---|---|---|
| Cloud Run Developer | `roles/run.developer` | Deploy and update the control plane |
| Vertex AI User | `roles/aiplatform.user` | Run the Gemini availability spike |
| Service Usage Admin | `roles/serviceusage.serviceUsageAdmin` | Enable any API missed in §3 without another owner round-trip |
| Artifact Registry Writer | `roles/artifactregistry.writer` | Push the container image |
| Cloud Build Editor | `roles/cloudbuild.builds.editor` | Build the image from source |
| Secret Manager Viewer | `roles/secretmanager.viewer` | Confirm secrets **exist** — see the warning below |
| Cloud Datastore User | `roles/datastore.user` | Create and inspect Firestore data during development |
| Storage Object Admin | `roles/storage.objectAdmin` | Manage artifacts in the bucket |
| Logs Viewer | `roles/logging.viewer` | Debug deployments |

4. Click **Save**.

> **Grant `roles/secretmanager.viewer`, not `roles/secretmanager.secretAccessor`.**
> Viewer lists secret *names and metadata*. Accessor reads secret *values*. Arpit only needs to confirm a secret exists and is wired to the right resource name — the application reads the values, he does not. The verification script in §14 explicitly checks that he *cannot* read values and reports that absence as correct.

**Leave `roles/editor` in place for now.** Removing it mid-hackathon risks breaking something unrelated at the worst moment. Once the golden path is stable, the owner can remove Editor and confirm the roles above are sufficient — the §14 script is exactly the tool for testing that safely.

**Done when:** Arpit's principal lists the 9 roles above alongside Editor.

---

## 7. Grant Service Account User — on the runtime account only

This is the grant that most often gets done wrong. Cloud Run deployment fails without it, and granting it too broadly hands over every identity in the project.

> **Do not** add `roles/iam.serviceAccountUser` on the IAM page from §6. That grants it at the *project* level, meaning Arpit can impersonate **every** service account in `agent-os-506220`, including any created later.
>
> Grant it on the **single service-account resource**, using a different page:

1. Open <https://console.cloud.google.com/iam-admin/serviceaccounts?project=agent-os-506220>.
2. Click on **`agent-os-runtime@agent-os-506220.iam.gserviceaccount.com`** to open the account itself.
3. Select the **Permissions** tab. This is the service account's *own* IAM policy, not the project's.
4. Click **Grant access**.
5. **New principals:** `tech.team@agiledonetech.com`
6. **Role:** `Service Account User` (`roles/iam.serviceAccountUser`)
7. Click **Save**.

The distinction: §6's page answers *"what may Arpit do in the project?"*; this page answers *"who may act as this one identity?"* Only the second is correct here.

**Done when:** the **Permissions** tab of `agent-os-runtime` lists `tech.team@agiledonetech.com` as Service Account User. The project IAM page should **not** show that role for him.

---

## 8. Create the Artifact Registry repository

1. Open <https://console.cloud.google.com/artifacts?project=agent-os-506220>.
2. Click **Create repository**.
3. **Name:** `agent-os` · **Format:** `Docker` · **Mode:** `Standard`
4. **Region:** `us-central1`. This must match the deployment region.
5. **Encryption:** Google-managed. Click **Create**.

**Done when:** repository `agent-os` exists in `us-central1`.

---

## 9. Create the Firestore database

> **One-way door.** A Firestore database's location and mode cannot be changed after creation — the only remedy is deleting and recreating the database. `PHASE_1_INTAKE.md` §B explicitly gates this step on the region decision. That decision is **confirmed as `us-central1`**. Do not deviate.

1. Open <https://console.cloud.google.com/firestore/databases?project=agent-os-506220>.
2. Click **Create database**.
3. **Database ID:** `(default)` — leave as the default. `.env.example` sets `FIRESTORE_DATABASE=(default)`.
4. **Mode:** **Native mode**. Not Datastore mode — the client libraries expect Native.
5. **Location type:** **Region**, then **`us-central1 (Iowa)`**.
6. Leave the security-rules default. Click **Create**.

**Done when:** a `(default)` Native-mode database exists in `us-central1`.

---

## 10. Create the artifact bucket

Bucket names are globally unique, so a project-scoped name is used.

1. Open <https://console.cloud.google.com/storage/browser?project=agent-os-506220>.
2. Click **Create**.
3. **Name:** `agent-os-506220-artifacts`
4. **Location type:** **Region**, then **`us-central1`**.
5. **Storage class:** Standard.
6. **Access control:** **Uniform**, not fine-grained.
7. Tick **Enforce public access prevention on this bucket**.
8. Click **Create**.
9. **Send Arpit the exact bucket name.** It fills `ARTIFACT_BUCKET` in his `.env`, which is currently empty. It is not a secret.

**Done when:** the bucket exists, is uniform-access, and is not public.

---

## 11. Create the Pub/Sub topic and subscription

`.env.example` already names both.

1. Open <https://console.cloud.google.com/cloudpubsub/topic/list?project=agent-os-506220>.
2. **Create topic** with ID `agent-os-workflow-events`. Leave *Add a default subscription* **unticked**. Click **Create**.
3. Open the topic and click **Create subscription**.
4. **Subscription ID:** `agent-os-workflow-worker` · **Delivery type:** **Pull**.
5. Accept the defaults and click **Create**.

**Done when:** topic `agent-os-workflow-events` has pull subscription `agent-os-workflow-worker`.

---

## 12. Create the OAuth client

`PHASE_1_CHECKLIST.md` §5 requires Testing mode with an explicit test user. Creating an OAuth client can require permissions Arpit's Editor role may not carry, so the owner should do it.

### 12a. Configure the consent screen

The OAuth consent screen is now presented as **Google Auth Platform**; older documentation calls it *APIs & Services → OAuth consent screen*. Both refer to the same configuration.

1. Open <https://console.cloud.google.com/auth/overview?project=agent-os-506220>.
2. If prompted, click **Get started**.
3. **App name:** `Agent OS` · **User support email:** the owner's address.
4. **Audience:** **External**.
5. **Contact email:** the owner's address. Accept the policy and click **Create**.
6. Go to **Audience**. Confirm **Publishing status** is **Testing**, not In production.
7. Under **Test users**, click **Add users** and add the dedicated demo Google account chosen in `PHASE_1_INTAKE.md` §C.
   In Testing mode **only** listed test users can complete the OAuth flow, so this step is mandatory, not optional.

### 12b. Add the Calendar scopes

1. Go to **Data access**, then **Add or remove scopes**.
2. Add only:
   - `https://www.googleapis.com/auth/calendar.events` — create and update demo events
   - `https://www.googleapis.com/auth/calendar.readonly` — read them back
3. Do **not** add Gmail, Drive, or full-Calendar scopes. Click **Update**, then **Save**.

### 12c. Create the Web client

1. Go to **Clients**, then **Create client**.
2. **Application type:** **Web application** · **Name:** `Agent OS Web Client`.
3. **Authorised redirect URIs** — click **Add URI** and add the local one now:
   ```
   http://localhost:3000/api/integrations/google/callback
   ```
   This matches `OAUTH_CALLBACK_URL` in `.env.example`.
4. Click **Create**.
5. A dialog shows the **Client ID** and **Client secret**.
   - The **Client ID** is *not* a secret. Send it to Arpit — it fills `GOOGLE_OAUTH_CLIENT_ID`.
   - The **Client secret** **is** a secret. Do not paste it into chat, a document, or the repo. It goes into Secret Manager in §13 and nowhere else. If the dialog is dismissed before the value is saved, use **Reset secret** rather than trying to recover it.

> **Deferred:** the deployed callback URL (`https://<cloud-run-url>/api/integrations/google/callback`) cannot be added until Cloud Run exists and its URL is known. Arpit will send that URL after the first deploy; return to **Clients → Agent OS Web Client → Add URI** then. This is the open item in `PHASE_1_CHECKLIST.md` §5.

**Done when:** the consent screen is in Testing with the demo account as a test user, two Calendar scopes are set, and a Web client exists with the localhost redirect.

---

## 13. Create the secret containers

Create the *containers* now. Values can be added as they become available.

1. Open <https://console.cloud.google.com/security/secret-manager?project=agent-os-506220>.
2. For each row: **Create secret**, set the name exactly, paste the value, set **Replication: Automatic**, then **Create**.

| Secret name (must match exactly) | Value | Available now? |
|---|---|---|
| `agent-os-google-oauth-client-secret` | The client secret from §12c | Yes |
| `agent-os-google-oauth-refresh-token` | Obtained after the first OAuth consent run | Later |
| `agent-os-github-token` | Fine-grained PAT for the demo repo | Later |

The names are read from `.env.example` and must match character-for-character, or the application will look up a resource that does not exist.

For the two deferred secrets, create the container with a placeholder value such as `PENDING` and add the real value as a **new version** later. Secret Manager versions are immutable and additive — this is the intended pattern, and it lets Arpit verify the wiring before the real credentials exist.

> **The values belong here and only here.** Never in `.env`, never in the repo, never in chat. Arpit's `roles/secretmanager.viewer` lets him confirm these three names exist without ever reading the values.

**Done when:** all three secret names exist.

---

## 14. Hand back to Arpit

Send him this. None of it is sensitive:

```text
Billing linked:            yes / no
Budget alert created:      yes / no
APIs enabled:              yes / no
Runtime SA created:        agent-os-runtime@agent-os-506220.iam.gserviceaccount.com
Service Account User:      granted on the SA resource (not project-wide)
Artifact Registry repo:    agent-os (us-central1)
Firestore:                 (default), Native mode, us-central1
ARTIFACT_BUCKET:           agent-os-506220-artifacts
Pub/Sub topic + sub:       created
GOOGLE_OAUTH_CLIENT_ID:    <paste the client ID - not a secret>
Secrets created:           3 of 3 names
Project number:            <from the Cloud Console dashboard>
```

The **project number** closes an open item in `PHASE_1_CHECKLIST.md` §2 — find it on <https://console.cloud.google.com/home/dashboard?project=agent-os-506220> under **Project info**.

Arpit then runs `infra/scripts/verify-access.sh` in Cloud Shell, which measures every grant above and reports what is missing. Ask him for that output — it is the objective proof this runbook succeeded, and far more reliable than re-reading the Console.

---

## Troubleshooting

**"Permission denied on Cloud Build service account" during the first deploy.**
`gcloud run deploy --source` builds through Cloud Build, which runs as its own identity. If the build fails on permissions, grant the build service account `roles/artifactregistry.writer`, `roles/logging.logWriter`, and `roles/storage.objectAdmin` on the IAM page. The exact identity is named in the error message — usually `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com` or `<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`. Read it from the error rather than assuming which one.

**Arpit reports `PERMISSION_DENIED: iam.serviceaccounts.actAs`.**
§7 was applied at the project level, or not at all. Recheck the **Permissions** tab of the service account itself.

**An API refuses to enable, citing billing.**
§1 has not taken effect. APIs cannot be enabled on a project with billing disabled.

**Vertex AI returns 403 despite the role being granted.**
IAM changes propagate; allow up to about 2 minutes. If it persists past 5, confirm `aiplatform.googleapis.com` is enabled *and* that billing is linked — either alone is insufficient.

**Firestore was created in the wrong region.**
Location is immutable. Delete the database and recreate it in `us-central1`, immediately, before any data exists.
