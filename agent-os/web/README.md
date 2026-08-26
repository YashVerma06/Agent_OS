# Agent OS Control Room

This React application provides the generic enterprise entry experience and the
operator control room. It creates organization, workforce, and engagement records,
then reads workflow, artifact, policy, and audit state from the FastAPI control plane.
It never authorizes actions in browser state.

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Start the API on `http://127.0.0.1:8080` first. Onboarding records only non-secret
configuration; authentication and provider OAuth are clearly marked as unconnected.
The implemented vertical slice runs from generic workspace activation through an
intake-derived specification, immutable approval, and the Planner handoff. Remaining
golden-path stages stay visible but are not presented as complete.
