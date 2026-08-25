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

export interface WorkflowSnapshot {
  workflow_id: string;
  tenant_id: string;
  name: string;
  client_request: string;
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
