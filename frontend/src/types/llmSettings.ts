export type LlmProvider = 'gemini' | 'groq' | 'openai';

export interface LlmProviderConfiguration {
  provider: LlmProvider;
  enabled: boolean;
  configured: boolean;
  status: 'valid' | 'invalid' | null;
  key_hint: string | null;
  credential_revision: number | null;
  last_validated_at: string | null;
  validation_failure_code: string | null;
  allowed_models: string[];
}

export interface LlmConfiguration {
  mode: 'deployment' | 'hybrid' | 'byok_required';
  preferred_provider: LlmProvider | null;
  preferred_model: string | null;
  preference_revision: number;
  allow_background_ai: boolean;
  providers: LlmProviderConfiguration[];
  deployment_fallback: {
    available: boolean;
    privileged: boolean;
    calls_used: number;
    calls_limit: number;
    calls_remaining: number;
  };
}

export interface LlmCredentialResult {
  id: string;
  owner_id: string;
  provider: LlmProvider;
  key_hint: string;
  status: string;
  credential_revision: number;
  preference_revision: number;
  last_validated_at: string | null;
}

export interface LlmPreflight {
  available: boolean;
  provider: LlmProvider;
  model: string;
  credential_source: 'user' | 'deployment';
}

export interface LlmUsageEvent {
  id: string;
  provider: LlmProvider;
  model: string;
  credential_source: 'user' | 'deployment';
  feature: string;
  workflow_type: string | null;
  workflow_id: string | null;
  interaction_type: 'explicit' | 'automatic';
  status: 'started' | 'completed' | 'failed';
  failure_code: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface LlmUsagePage {
  items: LlmUsageEvent[];
  next_cursor: string | null;
}
