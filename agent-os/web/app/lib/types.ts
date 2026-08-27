export type ActorRole =
  | 'manager'
  | 'discovery'
  | 'planner'
  | 'builder'
  | 'reviewer'
  | 'release_service'
  | 'human';

export type WorkflowState =
  | 'INTAKE'
  | 'DISCOVERY'
  | 'SPEC_REVIEW'
  | 'PLANNING'
  | 'IMPLEMENTING'
  | 'REVIEWING'
  | 'REVISION_REQUIRED'
  | 'RELEASE_REVIEW'
  | 'RELEASE_APPROVED'
  | 'STAGING_RELEASED'
  | 'REJECTED';

export type MeetingMode = 'agent_os_room' | 'transcript_upload' | 'written_brief';

export type AgentRunStatus =
  | 'READY'
  | 'COMPLETED'
  | 'WAITING_FOR_HUMAN'
  | 'DENIED'
  | 'FAILED';

export type HandoffGate =
  | 'NONE'
  | 'SPECIFICATION_APPROVAL'
  | 'RELEASE_APPROVAL';

export type CompanySize = '1-10' | '11-50' | '51-200' | '201-1000' | '1000+';

export interface OrganizationProfile {
  organization_id: string;
  tenant_id: string;
  display_name: string;
  legal_name: string | null;
  owner_name: string;
  owner_email: string;
  company_size: string;
  identity_status: 'UNVERIFIED_FOUNDATION';
  created_at: string;
}

export interface WorkforceTemplate {
  template_id: string;
  display_name: string;
  description: string;
  agent_roles: ActorRole[];
  human_gates: string[];
  version: number;
}

export interface ActivatedWorkforce {
  workforce_id: string;
  organization_id: string;
  template_id: string;
  display_name: string;
  meeting_mode: MeetingMode;
  repository_url: string;
  base_branch: string;
  working_branch_prefix: string;
  specification_approver_email: string;
  release_approver_email: string;
  status: 'CONFIGURED';
  integration_status: Record<string, string>;
  created_at: string;
}

export interface WorkflowSnapshot {
  workflow_id: string;
  tenant_id: string;
  name: string;
  client_request: string;
  organization_id: string | null;
  workforce_id: string | null;
  client_name: string | null;
  client_contact_name: string | null;
  client_contact_email: string | null;
  state: WorkflowState;
  version: number;
  reviewer_passed: boolean;
  release_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentDefinition {
  role: ActorRole;
  display_name: string;
  purpose: string;
  outputs: string[];
  forbidden: string[];
}

export interface ArtifactVersion {
  artifact_id: string;
  workflow_id: string;
  logical_name: string;
  kind: string;
  version: number;
  content: string;
  sha256: string;
  source_artifact_ids: string[];
  generated_by: ActorRole;
  approved: boolean;
  approved_by: ActorRole | null;
  immutable: boolean;
  created_at: string;
}

export interface AuditEvent {
  event_id: string;
  workflow_id: string;
  actor: ActorRole;
  action: string;
  state_before: WorkflowState;
  state_after: WorkflowState;
  allowed: boolean;
  reason: string;
  rule_id: string;
  idempotency_key: string;
  trace_id: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface PolicyDecision {
  allowed: boolean;
  actor: ActorRole;
  capability: string;
  reason: string;
  rule_id: string;
  workflow_state: WorkflowState | null;
  resource: string | null;
  trace_id: string;
}

export interface PlatformHealth {
  status: string;
  service: string;
  google_cloud_project: string;
  google_cloud_location: string;
  model: string;
  vertex_ai: boolean;
  persistence: string;
}

export interface ArtifactReference {
  artifact_id: string;
  logical_name: string;
  kind: string;
  version: number;
  sha256: string;
  generated_by: ActorRole;
  approved: boolean;
  immutable: boolean;
  source_artifact_ids: string[];
}

export interface RepositoryBoundary {
  repository_url: string;
  base_branch: string;
  working_branch_prefix: string;
}

export interface ClientContext {
  client_name: string | null;
  contact_name: string | null;
  contact_email: string | null;
  project_name: string;
  initial_request: string;
}

export interface ContextManifest {
  workflow_id: string;
  tenant_id: string;
  organization_id: string | null;
  workforce_id: string | null;
  workflow_state: WorkflowState;
  workflow_version: number;
  target_agent: ActorRole;
  client: ClientContext;
  artifact_references: ArtifactReference[];
  repository_boundary: RepositoryBoundary | null;
  candidate_capabilities: string[];
  unresolved_questions: string[];
  trace_id: string;
  created_at: string;
}

export interface AgentRunRequest {
  workflow_id: string;
  target_agent: ActorRole;
  context: ContextManifest;
  input_artifact_ids: string[];
  trace_id: string;
  idempotency_key: string;
}

export interface OrchestrationDecision {
  workflow_id: string;
  workflow_state: WorkflowState;
  status: AgentRunStatus;
  target_agent: ActorRole | null;
  required_gate: HandoffGate;
  reason: string;
  run_request: AgentRunRequest | null;
  trace_id: string;
  replayed: boolean;
}
