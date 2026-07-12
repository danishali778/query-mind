import { T } from './tokens';
import { countWidgetsByGenerationStatus } from '../../utils/dashboardGeneration';
import type { DashboardWidget } from '../../types/api';

interface GenerationBannerProps {
  widgets: DashboardWidget[];
  stageLabel?: string | null;
  busy?: boolean;
  onCancel?: () => void;
  onRetryFailed?: () => void;
}

export function GenerationBanner({
  widgets,
  stageLabel,
  busy = false,
  onCancel,
  onRetryFailed,
}: GenerationBannerProps) {
  const { ready, inProgress, failed, total } = countWidgetsByGenerationStatus(widgets);
  const active = inProgress > 0 || failed > 0;
  if (!active || total === 0) return null;

  return (
    <div
      style={{
        margin: '0 clamp(20px, 4vw, 40px) 16px',
        padding: '14px 16px',
        border: `1px solid ${failed > 0 ? 'rgba(239,68,68,0.3)' : T.border}`,
        background: failed > 0 ? T.redDim : T.s2,
        borderRadius: T.radius.md,
        display: 'flex',
        flexWrap: 'wrap',
        gap: 12,
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{
          fontFamily: T.fontMono,
          fontSize: '0.62rem',
          fontWeight: 800,
          letterSpacing: '0.08em',
          color: T.text3,
          marginBottom: 4,
        }}>
          AI GENERATION
        </div>
        <div style={{ fontFamily: T.fontBody, fontSize: '0.88rem', color: T.text, fontWeight: 600 }}>
          {stageLabel || (inProgress > 0 ? 'Generating widgets…' : 'Some widgets need attention')}
        </div>
        <div style={{ fontFamily: T.fontMono, fontSize: '0.68rem', color: T.text3, marginTop: 4 }}>
          {ready}/{total} ready · {inProgress} in progress · {failed} failed
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {failed > 0 && onRetryFailed && (
          <button
            type="button"
            onClick={onRetryFailed}
            disabled={busy}
            style={btnStyle}
          >
            Retry all failed
          </button>
        )}
        {inProgress > 0 && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            style={{ ...btnStyle, color: T.red, borderColor: 'rgba(239,68,68,0.35)' }}
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '8px 12px',
  borderRadius: 8,
  border: `1px solid ${T.border}`,
  background: T.s1,
  color: T.text,
  fontFamily: T.fontMono,
  fontSize: '0.68rem',
  fontWeight: 800,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  cursor: 'pointer',
};
