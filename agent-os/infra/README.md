# Google Cloud Deployment Boundary

Target project: `agent-os-506220`; region: `us-central1`.

The first deployment should contain:

- Agent OS control plane on Cloud Run;
- Vertex AI access through the attached runtime identity;
- Firestore for workflow/audit metadata;
- Cloud Storage for immutable artifacts;
- Secret Manager for provider credentials;
- Cloud Logging and Cloud Trace.

Do not create service-account keys. Do not deploy until the local golden-path tests pass. Agent Runtime, Agent Registry, Agent Gateway, Calendar, and BigQuery analytics remain P1 unless the P0 path is stable.

## Setup

| File | Who runs it | What it does |
|---|---|---|
| [`OWNER_SETUP.md`](OWNER_SETUP.md) | Project owner (`sv3981158@gmail.com`) | Console click-through for billing, budget, APIs, the runtime service account, all IAM grants, resources, the OAuth client, and the secret containers. |
| [`scripts/verify-access.sh`](scripts/verify-access.sh) | Arpit, in Cloud Shell | Measures what the caller can actually do and reports pass/fail against every item the runbook creates. Read-only, free, never reads a secret value. |

Run them in that order. `verify-access.sh` exiting 0 is the definition of "ready to deploy" — the Console is not a reliable substitute, because it shows roles rather than effective permissions.

```bash
# in https://shell.cloud.google.com
gcloud config set project agent-os-506220
bash agent-os/infra/scripts/verify-access.sh
```

`gcloud` is **not** installed on the primary workstation. Cloud Shell is the approved workspace for all `gcloud` work; see `docs/PHASE_1_CHECKLIST.md` for the correction and the one open question it leaves (Application Default Credentials for live local ADK runs).

## Identity boundary

Two identities, deliberately separated.

**`agent-os-runtime@agent-os-506220.iam.gserviceaccount.com`** — what the deployed control plane runs as. Holds Vertex AI, Firestore, Storage, Pub/Sub, logging, tracing, and `roles/secretmanager.secretAccessor` (it reads secret *values*). It deliberately holds no deploy permission: the runtime must not be able to redeploy or rewrite itself. It has **no keys**, per `AGENTS.md`.

**`tech.team@agiledonetech.com`** — the human deploying. Holds Cloud Run, Artifact Registry, Cloud Build, Vertex AI, Firestore, Storage, and `roles/secretmanager.viewer` (secret *names* only, not values). `roles/iam.serviceAccountUser` is granted on the runtime service account **as a resource**, never project-wide — project-wide would confer impersonation of every service account in the project, including ones created later.

`verify-access.sh` asserts both halves: that the required permissions are present, and that `secretmanager.versions.access` is absent.
