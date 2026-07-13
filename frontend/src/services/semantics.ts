import { jsonRequest, request } from './http';
import type {
  SemanticDefinition,
  SemanticDefinitionList,
  SemanticImpactItem,
  SemanticKind,
  SemanticSuggestionRun,
  SemanticSummary,
} from '../types/semantics';

const base = (connectionId: string) => `/database/connections/${connectionId}/semantics`;

export function getSemanticSummary(connectionId: string) {
  return request<SemanticSummary>(`${base(connectionId)}/summary`);
}

export function listSemanticDefinitions(
  connectionId: string,
  filters: { kind?: SemanticKind | ''; status?: string; validation_status?: string; search?: string } = {},
) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
  const suffix = params.size ? `?${params.toString()}` : '';
  return request<SemanticDefinitionList>(`${base(connectionId)}/definitions${suffix}`);
}

export function createSemanticDefinition(connectionId: string, data: {
  kind: SemanticKind;
  key?: string;
  display_name: string;
  description: string;
  payload: Record<string, unknown>;
  change_note?: string;
}) {
  return jsonRequest<SemanticDefinition>(`${base(connectionId)}/definitions`, 'POST', data);
}

export function getSemanticDefinition(connectionId: string, definitionId: string) {
  return request<SemanticDefinition>(`${base(connectionId)}/definitions/${definitionId}`);
}

export function updateSemanticDraft(connectionId: string, definitionId: string, data: {
  expected_draft_revision: number;
  display_name: string;
  description: string;
  payload: Record<string, unknown>;
}) {
  return jsonRequest<SemanticDefinition>(`${base(connectionId)}/definitions/${definitionId}/draft`, 'PATCH', data);
}

export function createSemanticVersion(connectionId: string, definitionId: string, data: {
  display_name: string;
  description: string;
  payload: Record<string, unknown>;
  change_note?: string;
}) {
  return jsonRequest<SemanticDefinition>(`${base(connectionId)}/definitions/${definitionId}/versions`, 'POST', data);
}

export function deleteSemanticDraft(connectionId: string, definitionId: string) {
  return request(`${base(connectionId)}/definitions/${definitionId}/draft`, { method: 'DELETE' });
}

export function validateSemanticVersion(connectionId: string, definitionId: string, version: number) {
  return jsonRequest<SemanticDefinition>(
    `${base(connectionId)}/definitions/${definitionId}/versions/${version}/validate`,
    'POST',
    { run_preview: true },
  );
}

export function verifySemanticVersion(connectionId: string, definitionId: string, version: number, data: {
  expected_schema_hash: string;
  acknowledged_warning_codes: string[];
  change_note?: string;
}) {
  return jsonRequest<SemanticDefinition>(
    `${base(connectionId)}/definitions/${definitionId}/versions/${version}/verify`,
    'POST',
    data,
  );
}

export function deprecateSemanticVersion(connectionId: string, definitionId: string, version: number) {
  return request<SemanticDefinition>(
    `${base(connectionId)}/definitions/${definitionId}/versions/${version}/deprecate`,
    { method: 'POST' },
  );
}

export function getSemanticImpact(connectionId: string, definitionId: string) {
  return request<SemanticImpactItem[]>(`${base(connectionId)}/definitions/${definitionId}/impact`);
}

export function startSemanticSuggestions(connectionId: string, data: {
  client_request_id: string;
  requested_kinds: SemanticKind[];
  business_context?: string;
}) {
  return jsonRequest<SemanticSuggestionRun>(`${base(connectionId)}/suggestions`, 'POST', data);
}

export function getSemanticSuggestions(connectionId: string, runId: string) {
  return request<SemanticSuggestionRun>(`${base(connectionId)}/suggestions/${runId}`);
}

export function cancelSemanticSuggestions(connectionId: string, runId: string) {
  return request<SemanticSuggestionRun>(`${base(connectionId)}/suggestions/${runId}/cancel`, { method: 'POST' });
}
