# Five-Day Execution Plan

## Day 1 — Foundation and contracts

- merge the foundation branch;
- confirm team names, branches, and ownership;
- run workflow/policy tests locally;
- verify ADC, project, region, Vertex AI API, and `gemini-3.6-flash` access;
- freeze API and artifact contracts.

**Exit:** each teammate can run the foundation and owns an isolated branch.

## Day 2 — Discovery to approval

- build the control-room shell and meeting transcript experience;
- implement Discovery/Specification Agent output;
- persist artifacts and display versions/hashes;
- implement authenticated specification approval.

**Exit:** client conversation produces a reviewable `SPECIFICATIONS.md` and the Builder remains blocked before approval.

## Day 3 — Planning and real build

- implement Planner output and requirements traceability;
- connect the repository jail and allowlisted command runner;
- create a real branch/patch in the demo repository;
- seed the deterministic status mismatch.

**Exit:** approved specification produces a real failing implementation branch.

## Day 4 — Review, repair, and cloud proof

- implement Reviewer QA/security report;
- route the failing report back to Builder;
- repair and re-run the same checks;
- deploy the backend to Cloud Run with Vertex AI, logs, and traces;
- add policy-denial evidence and demo reset.

**Exit:** one reliable end-to-end run exists in Google Cloud.

## Day 5 — Polish and submission

- freeze features by midday;
- improve 1440×900 UI hierarchy, loading, error, and empty states;
- rehearse and record the deterministic golden path;
- capture architecture, policy denial, Google Cloud execution, and final outcome;
- prepare backup video/screenshots and reset data.

**Exit:** three consecutive clean demos with no manual database repair or hidden mock.

## Scope-cut order if behind

1. Remove Calendar integration.
2. Defer Agent Registry and Agent Gateway.
3. Use text transcript instead of live voice.
4. Use a simulated staging outcome while retaining a real repository patch and real Vertex AI calls; label the staging adapter honestly.
5. Never cut specification approval, policy denial, real code change, reviewer failure/repair, or audit visibility.
