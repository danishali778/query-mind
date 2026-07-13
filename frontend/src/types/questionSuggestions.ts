export type SuggestionSurface = 'chat' | 'dashboard' | 'connection' | 'library';
export type SuggestionCategory = 'kpi' | 'trend' | 'comparison' | 'ranking' | 'segmentation' | 'anomaly';

export interface QuestionSuggestion {
  id: string;
  surface: SuggestionSurface;
  title: string;
  prompt: string;
  rationale: string;
  category: SuggestionCategory;
  source: 'deterministic' | 'ai';
  based_on: string[];
}

export interface QuestionSuggestionResponse {
  connection_id: string;
  surface: SuggestionSurface;
  status: 'fallback' | 'queued' | 'running' | 'ready' | 'failed' | 'disabled';
  context_fingerprint: string;
  schema_hash: string;
  suggestions: QuestionSuggestion[];
  refresh_required: boolean;
  ai_available: boolean;
  generated_at: string | null;
  failure: { code: string; message: string } | null;
}
