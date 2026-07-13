import { RefreshCw, Sparkles, X } from 'lucide-react';
import { T } from '../dashboard/tokens';
import { useQuestionSuggestions } from '../../hooks/useQuestionSuggestions';
import type { QuestionSuggestion, SuggestionSurface } from '../../types/questionSuggestions';

interface Props {
  connectionId: string | null | undefined;
  surface: SuggestionSurface;
  onSelect: (suggestion: QuestionSuggestion) => void;
  onSecondarySelect?: (suggestion: QuestionSuggestion) => void;
  primaryLabel?: string;
  secondaryLabel?: string;
  compact?: boolean;
}

export function SuggestionGrid({
  connectionId,
  surface,
  onSelect,
  onSecondarySelect,
  primaryLabel = 'Use idea',
  secondaryLabel = 'Build dashboard',
  compact = false,
}: Props) {
  const { suggestions, status, loading, refreshing, error, failure, refresh, dismiss } =
    useQuestionSuggestions(connectionId, surface);

  if (!connectionId) return null;
  if (loading && suggestions.length === 0) {
    return <div role="status" style={{ color: T.text3, fontSize: '0.75rem', fontFamily: T.fontMono }}>Finding useful questions...</div>;
  }
  if (status === 'disabled') return null;

  return (
    <section aria-label="Suggested questions" style={{ width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Sparkles size={14} aria-hidden="true" />
        <span style={{ fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Ideas for this source
        </span>
        {(refreshing || status === 'queued' || status === 'running') && (
          <span aria-live="polite" style={{ fontSize: '0.68rem', color: T.text3 }}>Personalizing suggestions...</span>
        )}
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={refreshing}
          aria-label="Refresh question suggestions"
          style={{ marginLeft: 'auto', border: `1px solid ${T.border}`, background: T.s1, color: T.text2, padding: 6, cursor: refreshing ? 'default' : 'pointer' }}
        >
          <RefreshCw size={13} aria-hidden="true" />
        </button>
      </div>
      {(error || failure) && (
        <div role="status" style={{ color: T.text3, fontSize: '0.7rem', marginBottom: 8 }}>
          {failure?.message || error} Safe schema-based ideas are still available.
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: compact ? 'repeat(auto-fit,minmax(210px,1fr))' : 'repeat(auto-fit,minmax(260px,1fr))', gap: 10 }}>
        {suggestions.map((suggestion) => (
          <article key={suggestion.id} style={{ position: 'relative', border: `1px solid ${T.border}`, background: T.s1, padding: compact ? 12 : 16, minWidth: 0 }}>
            <button
              type="button"
              onClick={() => void dismiss(suggestion.id)}
              aria-label={`Dismiss ${suggestion.title}`}
              style={{ position: 'absolute', right: 7, top: 7, border: 0, background: 'transparent', color: T.text3, cursor: 'pointer', padding: 3 }}
            ><X size={13} aria-hidden="true" /></button>
            <div style={{ fontFamily: T.fontMono, fontSize: '0.58rem', color: T.text3, textTransform: 'uppercase', marginBottom: 7 }}>{suggestion.category} · {suggestion.source === 'ai' ? 'personalized' : 'schema based'}</div>
            <div style={{ fontWeight: 800, color: T.text, fontSize: compact ? '0.78rem' : '0.9rem', marginBottom: 6, paddingRight: 18 }}>{suggestion.title}</div>
            {!compact && <div style={{ fontSize: '0.75rem', color: T.text2, lineHeight: 1.5, marginBottom: 8 }}>{suggestion.rationale}</div>}
            {suggestion.based_on.length > 0 && (
              <div style={{ fontSize: '0.62rem', color: T.text3, marginBottom: 10 }}>Based on {suggestion.based_on.join(', ')}</div>
            )}
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              <button type="button" onClick={() => onSelect(suggestion)} style={{ border: 0, background: T.text, color: T.bg, padding: '7px 10px', fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 800, cursor: 'pointer', textTransform: 'uppercase' }}>{primaryLabel}</button>
              {onSecondarySelect && <button type="button" onClick={() => onSecondarySelect(suggestion)} style={{ border: `1px solid ${T.border}`, background: T.s2, color: T.text, padding: '7px 10px', fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 800, cursor: 'pointer', textTransform: 'uppercase' }}>{secondaryLabel}</button>}
            </div>
          </article>
        ))}
      </div>
      {!loading && suggestions.length === 0 && <div style={{ color: T.text3, fontSize: '0.72rem' }}>No safe suggestions are available for this source yet.</div>}
    </section>
  );
}
