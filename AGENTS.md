# Agent OS Repository Guidance

## Project scope

- The active product lives under `agent-os/`.
- Preserve unrelated files in `output/` and `tmp/`; they are not part of Agent OS.
- Treat `agent-os/docs/PRODUCT_SCOPE.md` as the authoritative MVP scope.
- Treat `agent-os/docs/PERMISSION_MATRIX.md` as the authoritative role and tool boundary.
- Record material product or architecture changes in the relevant document before implementation.

## Delivery rules

- Prefer a reliable end-to-end golden path over feature breadth.
- The core path must use Google ADK, a qualifying Gemini 3.5+ model, and Google Cloud services actually demonstrated.
- Never claim an integration that is mocked or unavailable. Clearly label fallbacks.
- Keep human approval mandatory for specification approval, protected-branch merge, security exceptions, and production deployment.
- Do not let prompts enforce permissions. Enforce permissions in deterministic policy and tool-gateway code.
- Every consequential tool action must produce audit metadata and use an idempotency key where retry is possible.
- Approved artifacts are immutable; changes create new versions.

## Security

- Never commit or paste API keys, OAuth client secrets, refresh tokens, GitHub tokens, service-account keys, or billing details.
- Use Application Default Credentials locally and managed identities in Google Cloud.
- Store third-party credentials in Google Secret Manager.
- The Builder Agent must use a repository jail and an allowlisted command runner; never expose an unrestricted shell.

## Quality

- Keep the UI professional, accessible, responsive, and suitable for a 1440x900 demo recording.
- Run relevant tests after each implementation phase and do not advance with failing critical checks.
- Maintain a deterministic reset path for the hackathon demo.
