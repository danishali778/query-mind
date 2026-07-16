import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { testSavedConnection } from '../../services/api';
import type { QueryRecord, SchemaResponse } from '../../types/api';
import type { ConnectionDetailTab, ConnectionListItem, LoadState } from '../../types/connections';
import { SuggestionGrid } from '../suggestions/SuggestionGrid';
import { T } from '../dashboard/tokens';
import { ActivityRow, InfoRow, SectionCard, SummaryCard } from './ConnectionDetailShared';
import { formatLatency, formatTimestamp, primaryButtonStyle, secondaryButtonStyle } from './connectionDetailUtils';

export function ConnectionOverviewTab({ connection, schema, schemaState, queryHistory, onTabSwitch, onConnectionUpdated }: { connection: ConnectionListItem; schema: SchemaResponse | null; schemaState: LoadState; queryHistory: QueryRecord[]; onTabSwitch: (tab: ConnectionDetailTab) => void; onConnectionUpdated?: () => Promise<void> | void }) {
  const navigate = useNavigate();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number | null } | null>(null);
  const tables = schema?.tables ?? [];
  const recentQueries = queryHistory.slice(0, 3);
  const healthColor = connection.status === 'live' ? T.green : connection.status === 'offline' ? T.red : T.yellow;

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testSavedConnection(connection.id);
      setTestResult(result);
      await onConnectionUpdated?.();
    } catch (error) {
      setTestResult({ success: false, message: error instanceof Error ? error.message : 'Connection test failed.' });
    } finally {
      setTesting(false);
    }
  };

  return <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
    <div className="connection-summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 14 }}>
      <SummaryCard value={connection.health_state.toUpperCase()} label="CONNECTION HEALTH" detail={`Latest latency ${formatLatency(testResult?.latency_ms ?? connection.latency)}`} color={healthColor} />
      <SummaryCard value={schemaState === 'loading' ? '…' : String(tables.length)} label="TABLES DISCOVERED" detail={schemaState === 'error' ? 'Schema unavailable' : 'Available to QueryMind'} />
      <SummaryCard value={formatTimestamp(connection.last_schema_sync_at)} label="LAST SCHEMA REFRESH" detail={connection.schema_refresh_enabled ? 'Automatic refresh enabled' : 'Manual refresh'} color={T.purple} />
    </div>

    <SectionCard title="CONNECTION" badge={connection.readonly ? 'READ ONLY' : undefined} action={<button type="button" onClick={runTest} disabled={testing} style={{ ...primaryButtonStyle, opacity: testing ? .6 : 1 }}>{testing ? 'TESTING…' : 'TEST CONNECTION'}</button>}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: '0 24px', padding: '10px 18px' }}>
        <InfoRow label="ENGINE" value={connection.type} />
        <InfoRow label="HOST" value={connection.host || 'localhost'} />
        <InfoRow label="DATABASE" value={connection.database || 'N/A'} />
        <InfoRow label="USER" value={connection.username || 'N/A'} />
        <InfoRow label="TLS" value={(connection.ssl_mode || 'disable').toUpperCase()} />
        <InfoRow label="ACCESS" value={connection.scope_mode === 'all' ? 'All accessible tables' : `${connection.included_schemas.length} schemas + ${connection.included_tables.length} tables`} />
      </div>
      {testResult && <div aria-live="polite" style={{ margin: '0 18px 18px', padding: 12, color: testResult.success ? T.green : T.red, background: testResult.success ? T.greenDim : T.redDim, border: `1px solid ${testResult.success ? T.green : T.red}`, font: `700 .66rem ${T.fontMono}` }}>{testResult.message}</div>}
    </SectionCard>

    <div style={{ padding: 18, background: T.s1, border: `1px solid ${T.border}` }}>
      <SuggestionGrid
        connectionId={connection.id}
        surface="connection"
        primaryLabel="Ask in Chat"
        secondaryLabel="Build Dashboard"
        onSelect={(suggestion) => navigate('/chat', { state: { connectionId: connection.id, prompt: suggestion.prompt, suggestionId: suggestion.id } })}
        onSecondarySelect={(suggestion) => navigate('/dashboard', { state: { openAiWizard: true, connectionId: connection.id, prompt: suggestion.prompt, suggestionId: suggestion.id } })}
      />
    </div>

    <SectionCard title="RECENT QUERY ACTIVITY" badge={`${recentQueries.length} RECENT`} action={<button type="button" onClick={() => onTabSwitch('activity')} style={secondaryButtonStyle}>VIEW ACTIVITY</button>}>
      {recentQueries.map((query, index) => <ActivityRow key={`${query.timestamp}-${index}`} success={query.success} query={query.sql || 'Query text unavailable'} duration={query.success ? `${((query.execution_time_ms || 0) / 1000).toFixed(2)}s` : 'Error'} timestamp={query.timestamp} />)}
      {recentQueries.length === 0 && <div style={{ padding: 24, textAlign: 'center', color: T.text3, font: `600 .68rem ${T.fontMono}` }}>No queries yet. Ask a question in Chat to get started.</div>}
    </SectionCard>
  </div>;
}
