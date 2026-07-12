import { useState } from 'react';
import { T } from './tokens';
import type { DashboardWidgetItem } from '../../types/dashboard';
import { FAILED_WIDGET_STATUSES, IN_PROGRESS_WIDGET_STATUSES, stageLabelForWidget } from '../../utils/dashboardGeneration';

interface WidgetGenerationPlaceholderProps {
  widget: DashboardWidgetItem;
  onRetry?: () => void;
  onRegenerate?: (instruction?: string) => void;
  onStop?: () => void;
  busy?: boolean;
}

export function WidgetGenerationPlaceholder({
  widget,
  onRetry,
  onRegenerate,
  onStop,
  busy = false,
}: WidgetGenerationPlaceholderProps) {
  const [showRegen, setShowRegen] = useState(false);
  const [instruction, setInstruction] = useState('');
  const status = widget.generation_status || 'queued';
  const label = stageLabelForWidget(status);
  const isFailed = FAILED_WIDGET_STATUSES.has(status as 'failed' | 'cancelled');
  const isActive = IN_PROGRESS_WIDGET_STATUSES.has(status as 'queued' | 'running' | 'regenerating');

  return (
    <div
      className="widget-card"
      data-testid="widget-generation-placeholder"
      style={{
        background: '#fff',
        border: `1px solid ${isFailed ? 'rgba(239,68,68,0.25)' : 'rgba(0,0,0,0.08)'}`,
        borderRadius: 0,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 190,
      }}
    >
      <div className="widget-drag-handle" style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(0,0,0,0.05)',
        cursor: 'grab',
      }}>
        <div style={{
          fontFamily: T.fontHead,
          fontWeight: 900,
          fontSize: '1.05rem',
          color: T.text,
          fontStyle: 'italic',
          overflowWrap: 'anywhere',
        }}>
          {widget.title || 'Untitled widget'}
        </div>
        <div style={{
          marginTop: 6,
          fontFamily: T.fontMono,
          fontSize: '0.62rem',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: isFailed ? T.red : T.accent,
          fontWeight: 800,
        }}>
          {label}
        </div>
      </div>

      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 20px',
        gap: 12,
        textAlign: 'center',
      }}>
        {isActive && (
          <div style={{
            width: 28,
            height: 28,
            border: `3px solid ${T.border}`,
            borderTopColor: T.accent,
            borderRadius: '50%',
            animation: 'spin 0.9s linear infinite',
          }} />
        )}
        <div style={{ fontFamily: T.fontBody, fontSize: '0.85rem', color: T.text2, maxWidth: 280, lineHeight: 1.5 }}>
          {widget.generation_error
            || (isActive
              ? 'Building this visualization from your approved plan…'
              : 'Generation stopped before this widget was ready.')}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 4 }}>
          {isFailed && onRetry && (
            <ActionButton onClick={onRetry} disabled={busy}>Retry</ActionButton>
          )}
          {(isFailed || status === 'ready') && onRegenerate && (
            <ActionButton onClick={() => setShowRegen((v) => !v)} disabled={busy}>
              Regenerate
            </ActionButton>
          )}
          {isActive && onStop && (
            <ActionButton onClick={onStop} disabled={busy} danger>Stop</ActionButton>
          )}
        </div>

        {showRegen && onRegenerate && (
          <div style={{ width: '100%', maxWidth: 320, display: 'grid', gap: 8, marginTop: 8 }}>
            <input
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Optional instruction…"
              style={{
                width: '100%',
                padding: '8px 10px',
                border: `1px solid ${T.border}`,
                borderRadius: 8,
                fontFamily: T.fontBody,
                fontSize: '0.8rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <ActionButton
              onClick={() => {
                onRegenerate(instruction.trim() || undefined);
                setShowRegen(false);
                setInstruction('');
              }}
              disabled={busy}
            >
              Run regenerate
            </ActionButton>
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '7px 12px',
        borderRadius: 8,
        border: `1px solid ${danger ? 'rgba(239,68,68,0.35)' : T.border}`,
        background: danger ? T.redDim : T.s2,
        color: danger ? T.red : T.text,
        fontFamily: T.fontMono,
        fontSize: '0.66rem',
        fontWeight: 800,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}
    >
      {children}
    </button>
  );
}
