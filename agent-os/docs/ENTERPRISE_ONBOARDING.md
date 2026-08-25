# Agent OS Enterprise Onboarding

## Product hierarchy

Agent OS is a multi-tenant workforce platform. The product hierarchy is:

```text
Organization
  -> one or more activated workforces
      -> one or more client engagements
          -> governed workflow, artifacts, approvals, tools, and outcomes
```

- **Organization** owns members, policies, approvers, integration boundaries, and billing.
- **Workforce** is a reusable operating template containing agents, permissions, tools, and gates.
- **Engagement** is one concrete client or internal initiative processed by a workforce.

Client-specific content must never be the default Agent OS identity. The Northstar
maintenance portal remains an optional hackathon sample engagement only.

## Enterprise journey

### 1. Create and verify the organization

An enterprise owner creates an account, verifies their email, names the organization,
and selects the company size. The production implementation will use Supabase Auth for
email verification and session management. SSO, domain verification, and SCIM are later
enterprise capabilities.

The current foundation records organization and owner metadata but does not claim that
the email has been authenticated. Authentication must be enforced before any external
deployment.

### 2. Select a workforce template

The initial template is **Software Product Delivery**:

```text
Workforce Manager
-> Discovery & Specification
-> Planner & Architect
-> Builder
-> Reviewer
-> deterministic Release Service
```

The template establishes outputs, autonomy levels, mandatory human gates, and explicit
denials. Activating a template creates tenant-scoped agent registrations; it does not
grant credentials or broaden the permission matrix.

### 3. Configure operating boundaries

The enterprise provides non-secret configuration:

- discovery mode: Agent OS Meeting Room, transcript upload, or written brief;
- allowlisted GitHub repository URL;
- protected base branch and agent working-branch prefix;
- specification approver email;
- release approver email.

OAuth grants, refresh tokens, installation tokens, and service-account credentials are
never collected in these forms. Provider connection flows will store credentials in
Secret Manager and issue short-lived credentials to bounded adapters.

### 4. Create the first engagement

The operator enters the client name, project name, client contact, and initial request.
Agent OS creates a tenant-scoped workflow in `INTAKE`. The Workforce Manager may then
delegate discovery, but cannot approve artifacts, write code, or deploy.

### 5. Operate the workforce

```text
Client input or meeting
-> evidence-backed transcript and discovery record
-> versioned SPECIFICATIONS.md
-> authenticated human approval of an exact SHA-256
-> requirement-linked plan and architecture
-> Builder change inside repository jail
-> independent QA and security review
-> revision loop when required
-> authenticated human release approval
-> deterministic staging release
```

The control room shows the active specialist, workflow state, immutable artifact,
approvals, policy decisions, and audit evidence. Prompts never advance state or grant
authority directly.

## Current implementation boundary

| Capability | Foundation status |
|---|---|
| Organization, workforce, and engagement records | implemented with in-memory adapters |
| Generic guided onboarding UI | implemented |
| Dynamic engagement control room | implemented |
| Workflow, policy, artifacts, approvals, audit | implemented with deterministic adapters |
| Supabase email/session authentication | not connected |
| Google ADK/Gemini discovery execution | agent graph configured; runtime invocation pending |
| Agent OS Meeting Room | configuration only; realtime meeting execution pending |
| GitHub App/OAuth and repository jail | configuration boundary only; adapter pending |
| Firestore and Cloud Storage persistence | pending |
| Cloud Run and Sites production deployment | pending |

This boundary must remain visible in engineering and demo claims. The generic onboarding
is the product entry experience; the controlled sample remains a repeatable demonstration,
not a tenant baked into the platform.
