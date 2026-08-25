# Agent OS Control Room

The control room is the operator-facing React application for Agent OS. It reads
workforce, workflow, artifact, policy, and audit state from the FastAPI control
plane; it does not authorize actions in browser state.

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Start the API on `http://127.0.0.1:8080` first. The first implemented vertical
slice runs from engagement creation through immutable specification approval and
the Planner handoff. The remaining golden-path stages stay visible but are not
presented as complete.
