import { useState } from 'react';
import { T } from '../dashboard/tokens';
import { SqlBlock } from './SqlBlock';
import { ResultsTable } from './ResultsTable';
import { BaseChartContainer } from '../charts/BaseChartContainer';
import { AddToDashboardModal } from './AddToDashboardModal';
import { SaveQueryModal } from './SaveQueryModal';
import { useSmartSave } from '../../hooks/useSmartSave';
import { Pin, Plus, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react';
import type { ChatMessageView } from '../../types/chat';

export function MessageBubble({
  message,
  connectionId,
  onSqlSave,
  onTogglePin
}: {
  message: ChatMessageView,
  connectionId?: string,
  onSqlSave?: (messageId: string, newSql: string) => Promise<void>,
  onTogglePin?: (messageId: string, isPinned: boolean) => Promise<void>
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveLabel, setSaveLabel] = useState<string | null>(null);
  const [isSavingSql, setIsSavingSql] = useState(false);
  const [isPinning, setIsPinning] = useState(false);

  const { smartAddToDashboard, smartSaveToLibrary, isSaving: isSmartSaving } = useSmartSave();

  const handleSaved = (created: boolean) => {
    setSaveLabel(created ? '✅ Saved!' : '📌 Already saved');
    setTimeout(() => setSaveLabel(null), 3000);
  };

  const handleDashboardClick = () => {
    if (!connectionId) return;
    smartAddToDashboard(message, connectionId, () => setModalOpen(true));
  };

  const handleLibraryClick = () => {
    if (!message.sql || !connectionId) return;
    smartSaveToLibrary(
      message.sql,
      connectionId,
      message.chart_recommendation?.title || 'Saved from Chat',
      () => setSaveModalOpen(true),
      () => {
        setSaveLabel('✅ Saved!');
        setTimeout(() => setSaveLabel(null), 3000);
      }
    );
  };

  if (message.role === 'user') {
    return (
      <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginBottom: 20 }}>
        <div style={{
          maxWidth: '75%', background: '#fff', border: `1.5px solid rgba(0,0,0,0.1)`,
          borderRadius: 0, padding: '14px 20px',
          fontSize: '0.95rem', lineHeight: 1.6, color: T.text,
          boxShadow: 'none',
        }}>
          {message.content}
        </div>
      </div>
    );
  }
  // Assistant
  return (
    <div id={message.id ? `msg-${message.id}` : undefined} style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', alignItems: 'stretch', width: '100%', minWidth: 0, maxWidth: '100%' }}>
      {/* AI Header & Content */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', padding: '0 0 24px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 24, height: 24, background: '#1a1a1a', borderRadius: 4,
          color: '#fff', fontSize: '0.8rem', fontWeight: 900, fontStyle: 'italic',
          flexShrink: 0, marginTop: 4
        }}>
          Q
        </div>

        <div style={{ fontSize: '1rem', lineHeight: 1.6, color: T.text, fontWeight: 450, flex: 1 }}>
          {message.error ? (
            <div style={{ color: T.red, background: 'rgba(239, 68, 68, 0.05)', padding: '12px 16px', borderRadius: 12, border: `1px solid ${T.red}20` }}>
              <span style={{ fontWeight: 700, marginRight: 8 }}>Error</span>
              {message.error}
            </div>
          ) : (
            message.content
          )}
        </div>
      </div>

      {/* Technical Result Box (SQL, Table, Charts) */}
      {(message.sql || message.rows) && !message.error && (
        <div style={{
          width: '100%', minWidth: 0, marginLeft: 0,
          background: '#fff',
          border: `1px solid rgba(0,0,0,0.08)`,
          borderRadius: 0,
          overflow: 'hidden',
          boxShadow: 'none',
          marginBottom: 12
        }}>
          {/* Metadata Header */}
          <div style={{
            padding: '12px 20px',
            background: 'rgba(0,0,0,0.02)',
            borderBottom: `1px solid rgba(0,0,0,0.05)`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#1a1a1a' }} />
              {message.sql ? `SQL GENERATED — ${message.sql.length} CHARS` : 'DATA OBSERVATIONS'}
            </div>
            <button
              onClick={() => message.sql && navigator.clipboard.writeText(message.sql)}
              style={{ background: 'none', border: 'none', color: T.text, fontSize: '0.65rem', fontWeight: 800, cursor: 'pointer', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              COPY LINK
            </button>
          </div>

          {/* SQL Block */}
          {message.sql && (
            <SqlBlock
              sql={message.sql}
              defaultOpen={false} // Match the reference: collapsed by default or integrated
              onSave={onSqlSave && message.id ? async (newSql) => {
                setIsSavingSql(true);
                try { await onSqlSave(message.id!, newSql); } finally { setIsSavingSql(false); }
              } : undefined}
              isSaving={isSavingSql}
            />
          )}

          {/* Results Table */}
          {message.columns && message.rows && message.rows.length > 0 && (
            <div style={{ width: '100%', minWidth: 0, overflowX: 'auto' }}>
              <ResultsTable
                columns={message.columns}
                rows={message.rows}
                rowCount={message.row_count}
                executionTime={message.execution_time_ms}
              />
            </div>
          )}

          {/* Chart Section */}
          {message.chart_recommendation && message.chart_recommendation.type !== 'table' && message.rows && message.columns && (
            <BaseChartContainer
              recommendation={message.chart_recommendation}
              rows={message.rows}
              columns={message.columns}
              column_metadata={message.column_metadata}
            />
          )}

          {/* Assistant Action Bar (Inside Box) */}
          <div style={{ padding: '16px 20px', borderTop: `1px solid rgba(0,0,0,0.05)`, display: 'flex', alignItems: 'center', gap: 12, background: '#fff' }}>
            <button
              onClick={handleLibraryClick}
              disabled={!!saveLabel || !message.sql || isSmartSaving}
              style={{
                padding: '8px 16px', borderRadius: 0, border: `1.5px solid #1a1a1a`,
                background: '#fff', color: '#1a1a1a',
                fontSize: '0.7rem', fontWeight: 900, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
              }}
            >
              {saveLabel ? 'SAVED' : 'SAVE TO LIBRARY'}
            </button>

            <button
              onClick={handleDashboardClick}
              disabled={isSmartSaving}
              style={{
                padding: '8px 16px', borderRadius: 0, border: `1.5px solid #1a1a1a`,
                background: isSmartSaving ? 'rgba(0,0,0,0.05)' : '#fff',
                color: '#1a1a1a',
                fontSize: '0.7rem', fontWeight: 900, cursor: isSmartSaving ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                transition: 'all 0.2s', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
              }}
            >
              {isSmartSaving ? '⏳...' : (
                <>
                  <Plus size={12} strokeWidth={3} />
                  ADD TO DASHBOARD
                </>
              )}
            </button>

            {onTogglePin && message.id && (
              <button
                onClick={async () => {
                  if (onTogglePin && message.id) {
                    setIsPinning(true);
                    try { await onTogglePin(message.id, !message.is_pinned); } finally { setIsPinning(false); }
                  }
                }}
                disabled={isPinning}
                style={{
                  padding: '8px 16px', borderRadius: 0,
                  border: `1.5px solid #1a1a1a`,
                  background: message.is_pinned ? '#1a1a1a' : '#fff',
                  color: message.is_pinned ? '#fff' : '#1a1a1a',
                  fontSize: '0.7rem', fontWeight: 900, cursor: isPinning ? 'default' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
                  fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
                }}
              >
                <Pin size={12} strokeWidth={3} style={{ transform: message.is_pinned ? 'rotate(45deg)' : 'none', transition: 'transform 0.3s' }} />
                {message.is_pinned ? 'PINNED' : 'PIN RESULT'}
              </button>
            )}

            <button
              style={{
                padding: '8px 16px', borderRadius: 0, border: `1.5px solid rgba(0,0,0,0.1)`,
                background: 'transparent', color: T.text3,
                fontSize: '0.7rem', fontWeight: 900, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s',
                fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#1a1a1a'; e.currentTarget.style.color = '#1a1a1a'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'; e.currentTarget.style.color = T.text3; }}
            >
              <RotateCcw size={12} strokeWidth={3} />
              REGENERATE
            </button>

            <div style={{ flex: 1 }} />

            <div style={{ display: 'flex', gap: 14, color: T.text3 }}>
              <ThumbsUp size={16} strokeWidth={2} style={{ cursor: 'pointer', opacity: 0.5 }} />
              <ThumbsDown size={16} strokeWidth={2} style={{ cursor: 'pointer', opacity: 0.5 }} />
            </div>
          </div>
        </div>
      )}

      <SaveQueryModal
        isOpen={saveModalOpen}
        onClose={() => setSaveModalOpen(false)}
        sql={message.sql || ''}
        defaultTitle={message.chart_recommendation?.title || 'Saved from Chat'}
        connectionId={connectionId}
        onSaved={handleSaved}
      />
      <AddToDashboardModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        message={{
          title: message.chart_recommendation?.title || 'Data Query',
          dbName: 'database',
          rowCount: message.row_count || message.rows?.length,
          sql: message.sql,
          columns: message.columns,
          rows: message.rows,
          connectionId: connectionId,
          chart_recommendation: message.chart_recommendation,
          column_metadata: message.column_metadata,
        }}
      />
    </div>
  );
}
