import type {
  ActorRole,
  ActivatedWorkforce,
  AgentDefinition,
  ArtifactVersion,
  AuditEvent,
  CompanySize,
  MeetingMode,
  OrganizationProfile,
  PlatformHealth,
  PolicyDecision,
  WorkforceTemplate,
  WorkflowSnapshot,
  WorkflowState,
} from './types';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8080';

export class ControlPlaneError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string | { message?: string } }
      | null;
    const detail = body?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message ?? `Control plane request failed (${response.status}).`;
    throw new ControlPlaneError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export const controlPlane = {
  health: () => request<PlatformHealth>('/health'),
  workforce: () => request<AgentDefinition[]>('/v1/workforce'),
  workforceTemplates: () => request<WorkforceTemplate[]>('/v1/workforce-templates'),
  createOrganization: (input: {
    display_name: string;
    legal_name?: string;
    owner_name: string;
    owner_email: string;
    company_size: CompanySize;
    idempotency_key: string;
  }) =>
    request<OrganizationProfile>('/v1/organizations', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  organization: (organizationId: string) =>
    request<OrganizationProfile>(`/v1/organizations/${organizationId}`),
  activateWorkforce: (
    organizationId: string,
    input: {
      template_id: string;
      display_name: string;
      meeting_mode: MeetingMode;
      repository_url: string;
      base_branch: string;
      working_branch_prefix: string;
      specification_approver_email: string;
      release_approver_email: string;
      idempotency_key: string;
    },
  ) =>
    request<ActivatedWorkforce>(`/v1/organizations/${organizationId}/workforces`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  activatedWorkforce: (organizationId: string, workforceId: string) =>
    request<ActivatedWorkforce>(
      `/v1/organizations/${organizationId}/workforces/${workforceId}`,
    ),
  createEngagement: (
    organizationId: string,
    input: {
      workforce_id: string;
      client_name: string;
      project_name: string;
      client_contact_name?: string;
      client_contact_email?: string;
      client_request: string;
      idempotency_key: string;
    },
  ) =>
    request<WorkflowSnapshot>(`/v1/organizations/${organizationId}/engagements`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  workflow: (workflowId: string) => request<WorkflowSnapshot>(`/v1/workflows/${workflowId}`),
  createWorkflow: (name: string, clientRequest: string) =>
    request<WorkflowSnapshot>('/v1/workflows', {
      method: 'POST',
      body: JSON.stringify({ name, client_request: clientRequest }),
    }),
  transition: (
    workflowId: string,
    action: string,
    actor: ActorRole,
    metadata: Record<string, unknown> = {},
  ) =>
    request<{ workflow: WorkflowSnapshot; audit_event: AuditEvent; replayed: boolean }>(
      `/v1/workflows/${workflowId}/transitions`,
      {
        method: 'POST',
        body: JSON.stringify({
          action,
          actor,
          idempotency_key: `${action}-${crypto.randomUUID()}`,
          trace_id: crypto.randomUUID(),
          metadata,
        }),
      },
    ),
  createArtifact: (
    workflowId: string,
    artifact: {
      logical_name: string;
      kind: string;
      content: string;
      actor: ActorRole;
      source_artifact_ids?: string[];
      idempotency_key: string;
    },
  ) =>
    request<ArtifactVersion>(`/v1/workflows/${workflowId}/artifacts`, {
      method: 'POST',
      body: JSON.stringify({ source_artifact_ids: [], ...artifact }),
    }),
  artifacts: (workflowId: string) =>
    request<ArtifactVersion[]>(`/v1/workflows/${workflowId}/artifacts`),
  audit: (workflowId: string) =>
    request<AuditEvent[]>(`/v1/workflows/${workflowId}/audit`),
  approveArtifact: (workflowId: string, artifact: ArtifactVersion) =>
    request<ArtifactVersion>(
      `/v1/workflows/${workflowId}/artifacts/${artifact.artifact_id}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({ actor: 'human', expected_sha256: artifact.sha256 }),
      },
    ),
  evaluatePolicy: (
    actor: ActorRole,
    capability: string,
    workflowState: WorkflowState | null,
  ) =>
    request<PolicyDecision>('/v1/policy/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        actor,
        capability,
        workflow_state: workflowState,
        resource: 'production',
        approval_present: false,
        trace_id: crypto.randomUUID(),
      }),
    }),
};
