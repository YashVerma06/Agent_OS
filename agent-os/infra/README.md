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
