export type SemanticKind =
  | 'table' | 'column' | 'entity' | 'dimension' | 'metric'
  | 'relationship' | 'filter' | 'date_policy' | 'synonym';

export interface SemanticFinding {
  code: string;
  message: string;
  field?: string;
}

export interface SemanticValidationReport {
  errors?: SemanticFinding[];
  warnings?: SemanticFinding[];
  schema_hash?: string;
  normalized_payload?: Record<string, unknown>;
  preview?: Record<string, unknown>;
  validated_at?: string;
}

export interface SemanticDefinitionVersion {
  id: string;
  definition_id: string;
  version: number;
  status: 'draft' | 'verified' | 'deprecated';
  display_name: string;
  description: string;
  payload: Record<string, unknown>;
  schema_hash?: string | null;
  validation_status: 'unvalidated' | 'valid' | 'invalid' | 'stale';
  validation_report: SemanticValidationReport;
  change_note?: string | null;
  draft_revision: number;
  created_by: string;
  verified_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  validated_at?: string | null;
  verified_at?: string | null;
  deprecated_at?: string | null;
}

export interface SemanticDefinition {
  id: string;
  owner_id: string;
  connection_id: string;
  kind: SemanticKind;
  key: string;
  versions: SemanticDefinitionVersion[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SemanticDefinitionList {
  items: SemanticDefinition[];
  total: number;
  page: number;
  page_size: number;
}

export interface SemanticSummary {
  connection_id: string;
  schema_hash?: string | null;
  total: number;
  draft: number;
  verified: number;
  deprecated: number;
  invalid: number;
  stale: number;
  last_validated_at?: string | null;
}

export interface SemanticImpactItem {
  definition_version_id: string;
  version: number;
  consumer_type: string;
  consumer_id: string;
  usage_role: string;
  created_at?: string | null;
}

export interface SemanticSuggestionCandidate {
  kind: SemanticKind;
  key: string;
  display_name: string;
  description: string;
  payload: Record<string, unknown>;
  rationale: string;
  assumptions: string[];
  structural_validation: {
    valid: boolean;
    errors: SemanticFinding[];
    warnings: SemanticFinding[];
    schema_hash: string;
  };
}

export interface SemanticSuggestionRun {
  id: string;
  connection_id: string;
  client_request_id: string;
  schema_hash: string;
  requested_kinds: SemanticKind[];
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  candidates: SemanticSuggestionCandidate[];
  failure_code?: string | null;
  failure_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SemanticLineageItem {
  definition_id: string;
  version_id: string;
  reference: string;
  kind: SemanticKind;
  display_name: string;
  version: number;
  usage_role: 'applied' | 'policy_enforced';
  verification_status: 'verified';
}
