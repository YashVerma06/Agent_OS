# Agent OS ADK Guidance

- Use Google ADK 2.x patterns and Vertex AI authentication through ADC or managed identity.
- Keep `gemini-3.6-flash` configurable through `GEMINI_CORE_MODEL`.
- The ADK agent graph performs reasoning only. It never grants tool authority.
- Send every consequential tool request through `app/platform/policy.py` and the workflow engine.
- Never add an unrestricted shell tool, raw secret tool, protected-branch writer, or production deployer.
- Preserve artifact hashes, approval lineage, idempotency keys, and audit events.
- Extend persistence through adapters; do not weaken the in-memory foundation semantics.
