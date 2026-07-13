import { useState } from 'react';
import { T } from '../dashboard/tokens';
import { SqlBlock } from './SqlBlock';
import { ResultsTable } from './ResultsTable';
import { BaseChartContainer } from '../charts/BaseChartContainer';
import { AddToDashboardModal } from './AddToDashboardModal';
import { SaveQueryModal } from './SaveQueryModal';
import { useSmartSave } from '../../hooks/useSmartSave';
import { Pin, Plus } from 'lucide-react';
import type { ChatMessageView } from '../../types/chat';
import { AgentActivity } from './AgentActivity';

export function MessageBubble({
  message,
  connectionId,
  onSqlSave,
  onTogglePin,
  onCancelRun,
}: {
  message: ChatMessageView,
  connectionId?: string,
  onSqlSave?: (messageId: string, newSql: string) => Promise<void>,
  onTogglePin?: (messageId: string, isPinned: boolean) => Promise<void>,
  onCancelRun?: (runId: string) => Promise<void>
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveLabel, setSaveLabel] = useState<string | null>(null);
  const [isSavingSql, setIsSavingSql] = useState(false);
  const [isPinning, setIsPinning] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [definitionsOpen, setDefinitionsOpen] = useState(false);

  const { smartAddToDashboard, smartSaveToLibrary, isSaving: isSmartSaving } = useSmartSave();

  const handleSaved = (created: boolean) => {
    setSaveLabel(created ? 'Saved!' : 'Already saved');
    setTimeout(() => setSaveLabel(null), 3000);
  };

  const handleDashboardClick = () => {
    if (!connectionId || !message.sql) return;
    smartAddToDashboard(message, connectionId, () => setModalOpen(true));
  };

  const handleLibraryClick = () => {
    if (!message.sql || !connectionId) return;
    smartSaveToLibrary(
      message.sql,
      connectionId,
      message.chart_recommendation?.title || message.content?.slice(0, 80) || 'Saved from Chat',
      () => setSaveModalOpen(true),
      () => {
        setSaveLabel('Saved!');
        setTimeout(() => setSaveLabel(null), 3000);
      }
    );
  };

  const canSaveSql = Boolean(message.sql && connectionId);
  const actionBtnStyle = (enabled: boolean): React.CSSProperties => ({
    padding: '8px 16px', borderRadius: 0, border: `1.5px solid ${enabled ? '#1a1a1a' : 'rgba(0,0,0,0.12)'}`,
    background: enabled ? '#fff' : 'rgba(0,0,0,0.03)', color: enabled ? '#1a1a1a' : T.text3,
    fontSize: '0.7rem', fontWeight: 900,
    cursor: enabled ? 'pointer' : 'not-allowed',
    display: 'flex', alignItems: 'center', gap: 8,
    fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em',
    opacity: enabled ? 1 : 0.65,
  });

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
  const hasRunActivity = Boolean(message.agent_run_id && message.agent_run_status);
  return (
    <div id={message.id ? `msg-${message.id}` : undefined} style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', alignItems: 'stretch', width: '100%', minWidth: 0, maxWidth: '100%' }}>
      {hasRunActivity && message.agent_run_status && (
        <div style={{ marginBottom: message.agent_run_status === 'completed' ? 12 : 20 }}>
          <AgentActivity
            status={message.agent_run_status}
            label={message.agent_run_stage_label}
            events={message.agent_run_events}
            streamState={message.agent_stream_state}
            onStop={message.agent_run_id && onCancelRun ? () => { void onCancelRun(message.agent_run_id!); } : undefined}
          />
        </div>
      )}

      {/* AI Header & Content */}
      {(message.content || message.error) && (
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
      )}

      {message.agent_trace && message.agent_trace.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => setTraceOpen((open) => !open)}
            style={{
              background: 'transparent',
              border: `1px solid ${T.border}`,
              color: T.text3,
              fontFamily: T.fontMono,
              fontSize: '0.62rem',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              padding: '8px 12px',
              cursor: 'pointer',
            }}
          >
            {traceOpen ? 'Hide' : 'Show'} agent steps ({message.agent_trace.length})
          </button>
          {traceOpen && (
            <div style={{
              marginTop: 8,
              border: `1px solid ${T.border}`,
              background: T.s1,
              padding: '12px 16px',
              fontFamily: T.fontMono,
              fontSize: '0.72rem',
              color: T.text2,
            }}>
              {message.agent_trace.map((step, index) => (
                <div key={`${step.tool}-${index}`} style={{ marginBottom: 8 }}>
                  <div><strong>{step.tool}</strong> - {step.outcome} - {step.duration_ms}ms</div>
                  <div style={{ color: T.text3, marginTop: 2 }}>Input: {step.args_summary || '{}'}</div>
                  {step.output_summary && (
                    <div style={{ color: T.text3, marginTop: 2 }}>Output: {step.output_summary}</div>
                  )}
                  {typeof step.output_row_count === 'number' && (
                    <div style={{ color: T.text3, marginTop: 2 }}>Rows: {step.output_row_count}</div>
                  )}
                  {step.error_class && (
                    <div style={{ color: T.text3, marginTop: 2 }}>Error class: {step.error_class}</div>
                  )}
                  {typeof step.retry_count === 'number' && step.retry_count > 0 && (
                    <div style={{ color: T.text3, marginTop: 2 }}>Retry: {step.retry_count}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {message.semantic_lineage && message.semantic_lineage.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <button type="button" onClick={() => setDefinitionsOpen((open) => !open)} style={{ background: 'transparent', border: `1px solid ${T.border}`, color: T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', letterSpacing: '0.08em', textTransform: 'uppercase', padding: '8px 12px', cursor: 'pointer' }}>
            {definitionsOpen ? 'Hide' : 'Show'} definitions used ({message.semantic_lineage.length})
          </button>
          {definitionsOpen && (
            <div style={{ marginTop: 8, border: `1px solid ${T.border}`, background: T.s1, padding: '10px 14px' }}>
              {message.semantic_lineage.map((item) => (
                <div key={`${item.version_id}-${item.usage_role}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '6px 0', borderBottom: `1px solid ${T.border}`, color: T.text2, fontSize: '0.7rem' }}>
                  <span>{item.display_name} <span style={{ color: T.text3 }}>· {item.kind.replace('_', ' ')}</span></span>
                  <span style={{ color: item.usage_role === 'policy_enforced' ? T.yellow : T.green, fontFamily: T.fontMono, fontSize: '0.6rem' }}>V{item.version} · {item.usage_role.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

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
              {message.sql ? `SQL GENERATED - ${message.sql.length} CHARS` : 'DATA OBSERVATIONS'}
            </div>
            <button
              onClick={() => message.sql && navigator.clipboard.writeText(message.sql)}
              disabled={!message.sql}
              style={{ background: 'none', border: 'none', color: message.sql ? T.text : T.text3, fontSize: '0.65rem', fontWeight: 800, cursor: message.sql ? 'pointer' : 'not-allowed', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em', opacity: message.sql ? 1 : 0.5 }}
            >
              COPY SQL
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
                truncated={message.truncated}
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
          <div style={{ padding: '16px 20px', borderTop: `1px solid rgba(0,0,0,0.05)`, display: 'flex', alignItems: 'center', gap: 12, background: '#fff', flexWrap: 'wrap' }}>
            {canSaveSql ? (
              <button
                onClick={handleLibraryClick}
                disabled={!!saveLabel || isSmartSaving}
                style={actionBtnStyle(!saveLabel && !isSmartSaving)}
                title="Save this SQL query to your library"
              >
                {saveLabel ? 'SAVED' : isSmartSaving ? 'SAVING…' : 'SAVE TO LIBRARY'}
              </button>
            ) : (
              <span style={{ fontSize: '0.65rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Schema listings cannot be saved to Library
              </span>
            )}

            <button
              onClick={handleDashboardClick}
              disabled={!canSaveSql || isSmartSaving}
              style={actionBtnStyle(canSaveSql && !isSmartSaving)}
              title={canSaveSql ? 'Add this query result to a dashboard' : 'Run a SQL query first to add results to a dashboard'}
            >
              {isSmartSaving ? 'Saving...' : (
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
