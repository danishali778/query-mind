import { jsonRequest, request } from './http';
import { ApiRequestError } from './http';
import type { LlmConfiguration, LlmCredentialResult, LlmPreflight, LlmProvider, LlmUsagePage } from '../types/llmSettings';

export function getLlmConfiguration() {
  return request<LlmConfiguration>('/settings/llm');
}

export function saveLlmCredential(
  provider: LlmProvider,
  data: { api_key: string; model: string; expected_credential_revision?: number },
) {
  return jsonRequest<LlmCredentialResult>(`/settings/llm/credentials/${provider}`, 'PUT', data);
}

export function revalidateLlmCredential(provider: LlmProvider) {
  return request<LlmCredentialResult>(`/settings/llm/credentials/${provider}/validate`, { method: 'POST' });
}

export function deleteLlmCredential(
  provider: LlmProvider,
  data: { expected_credential_revision: number; replacement_provider?: LlmProvider },
) {
  return jsonRequest<{ deleted: boolean }>(`/settings/llm/credentials/${provider}`, 'DELETE', data);
}

export function updateLlmPreferences(data: {
  expected_preference_revision: number;
  preferred_provider: LlmProvider | null;
  preferred_model: string | null;
  allow_background_ai: boolean;
}) {
  return jsonRequest<Pick<LlmConfiguration, 'preferred_provider' | 'preferred_model' | 'preference_revision' | 'allow_background_ai'>>(
    '/settings/llm/preferences',
    'PATCH',
    data,
  );
}

export function preflightLlm(feature: string, interactionType: 'explicit' | 'automatic' = 'explicit') {
  const params = new URLSearchParams({ feature, interaction_type: interactionType });
  return request<LlmPreflight>(`/settings/llm/preflight?${params.toString()}`);
}

export function getLlmUsage(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request<LlmUsagePage>(`/settings/llm/usage?${params.toString()}`);
}

const SETUP_ERROR_CODES = new Set([
  'llm_credential_required',
  'llm_credential_invalid',
  'deployment_llm_trial_exhausted',
  'deployment_llm_unavailable',
]);

export function isLlmSetupError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError && SETUP_ERROR_CODES.has(error.code);
}
