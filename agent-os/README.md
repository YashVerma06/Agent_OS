# Agent OS — Foundation

This directory contains the five-day MVP foundation for the governed software-delivery workforce.

## What exists now

- reduced five-agent Google ADK workforce definition;
- deterministic workflow state machine with human gates and idempotency;
- generic organization -> workforce -> engagement onboarding contracts;
- deny-by-default capability policy engine;
- immutable versioned artifact store;
- FastAPI control-plane contracts;
- professional React control room wired to those contracts;
- unit tests for the security and workflow boundaries;
- team ownership, architecture, and five-day delivery documents.

## Local setup

Requirements: Python 3.11+, `uv`, Google Cloud CLI, and access to project `agent-os-506220`.

```powershell
Copy-Item .env.example .env
uv sync --extra dev
uv run python -m pytest
uv run uvicorn app.fast_api_app:api --reload --port 8080
```

In a second terminal, start the control room:

```powershell
Set-Location web
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. The guided setup creates an organization, activates
the Software Product Delivery workforce, records repository and approval boundaries,
and creates the first client engagement. The resulting control room can activate
discovery, produce a versioned intake-derived `SPECIFICATIONS.md`, stop for human
approval of its exact hash, and then authorize the Planner handoff.

The deterministic tests do not call a model. Live ADK execution requires:

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project agent-os-506220
```

Do not add a Gemini API key. The selected path is Vertex AI with ADC locally and a managed identity in Google Cloud.

## Core endpoints

- `GET /health`
- `GET /v1/workforce`
- `GET /v1/workforce-templates`
- `POST /v1/organizations`
- `GET /v1/organizations/{organization_id}`
- `POST /v1/organizations/{organization_id}/workforces`
- `GET /v1/organizations/{organization_id}/workforces/{workforce_id}`
- `POST /v1/organizations/{organization_id}/engagements`
- `POST /v1/workflows`
- `GET /v1/workflows/{workflow_id}`
- `POST /v1/workflows/{workflow_id}/transitions`
- `GET /v1/workflows/{workflow_id}/audit`
- `POST /v1/workflows/{workflow_id}/artifacts`
- `POST /v1/workflows/{workflow_id}/artifacts/{artifact_id}/approve`
- `POST /v1/policy/evaluate`

## Essential documents

- `docs/PRODUCT_SCOPE.md` — frozen five-day golden path;
- `docs/ARCHITECTURE.md` — component and contract boundaries;
- `docs/PERMISSION_MATRIX.md` — authoritative role/tool permissions;
- `docs/TEAM_OWNERSHIP.md` — branch and four-person work division;
- `docs/FIVE_DAY_EXECUTION_PLAN.md` — daily exit gates.
- `docs/ENTERPRISE_ONBOARDING.md` — canonical enterprise registration and operating flow.

The in-memory adapters are foundation implementations. Firestore, Cloud Storage, repository, and staging adapters must implement the same interfaces without weakening workflow or policy checks.
