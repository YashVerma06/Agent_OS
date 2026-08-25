# Agent OS

Agent OS is infrastructure for creating and operating governed AI workforces. The five-day hackathon MVP demonstrates a software-delivery workforce that turns a client discovery conversation into an approved specification, implementation plan, real code change, independent review, revision loop, and human-controlled staging release.

The active product is in [`agent-os/`](agent-os/).

## Foundation branch

`codex/arpit-foundation` is the integration branch for the initial architecture. Teammates should branch from it and open pull requests back into it until the foundation is merged to `main`.

## Golden path

```text
Client meeting
-> Discovery & Specification Agent
-> SPECIFICATIONS.md
-> human approval
-> Planner & Architect Agent
-> Builder Agent
-> Reviewer Agent detects seeded defect
-> Builder repairs
-> Reviewer passes
-> human release approval
-> staging outcome + complete audit trail
```

Google ADK and a qualifying Gemini model on Vertex AI provide agent reasoning. Deterministic workflow, policy, approval, artifact, and audit services control authority.

## Start here

1. Read [`agent-os/docs/PRODUCT_SCOPE.md`](agent-os/docs/PRODUCT_SCOPE.md).
2. Read [`agent-os/docs/ARCHITECTURE.md`](agent-os/docs/ARCHITECTURE.md).
3. Read [`agent-os/docs/TEAM_OWNERSHIP.md`](agent-os/docs/TEAM_OWNERSHIP.md).
4. Follow [`agent-os/README.md`](agent-os/README.md) for local setup.

Never commit API keys, OAuth secrets, refresh tokens, GitHub tokens, service-account keys, or billing details.
