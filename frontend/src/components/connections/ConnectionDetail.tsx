import React, { useEffect, useState } from 'react';
import { RefreshCw, Edit3, Share2, Trash2, Database, Shield, Activity, Layout, Terminal, BookOpen } from 'lucide-react';
import { T } from '../dashboard/tokens';
import type { ConnectionListItem, ConnectionDetailProps, ConnectionDetailTab, LoadState } from '../../types/connections';
import type { ConnectionHealthHistory, ConnectionScopePreview, QueryRecord, SchemaResponse, SchemaTable, SchemaColumn } from '../../types/api';
import { ErdDiagram } from './ErdDiagram';
import {
  discoverConnectionScope, getConnectionHealth, previewConnectionScope,
  rotateConnectionCredentials, testSavedConnection, updateConnectionAutomation,
  updateConnectionScope,
} from '../../services/api';
import { SemanticsWorkspace } from './SemanticsWorkspace';
import { SuggestionGrid } from '../suggestions/SuggestionGrid';
import { useNavigate } from 'react-router-dom';

interface UiColumnSchema {
  name: string;
  type?: string;
  isPk?: boolean;
  isFk?: boolean;
}

type TableSchema = SchemaTable;

const timeAgo = (dateStr: string) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}S AGO`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}M AGO`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}H AGO`;
  return date.toLocaleDateString();
};

const formatTimestamp = (dateStr?: string | null) => {
  if (!dateStr) return 'NEVER';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return 'UNKNOWN';
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};

const formatLatency = (latency?: number | null) => {
  if (latency == null) return 'N/A';
  return `${Math.round(latency)} MS`;
};

export function ConnectionDetail({ connection, schema, schemaState = 'idle', schemaError, queryHistory, queryHistoryState = 'idle', queryHistoryError, onDelete, onRefreshSchema, onConnectionUpdated }: ConnectionDetailProps) {
  const [activeTab, setActiveTab] = useState<ConnectionDetailTab>('overview');

  if (!connection) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: T.bg, color: T.text3, fontFamily: T.fontMono, fontSize: '0.72rem', letterSpacing: '1px' }}>
        SELECT A DATA SOURCE TO VIEW LEDGER
      </div>
    );
  }

  const getStatusColor = () => {
    switch (connection.status) {
      case 'live': return { bg: T.greenDim, text: T.green, border: 'rgba(34,211,165,0.1)' };
      case 'offline': return { bg: T.redDim, text: T.red, border: 'rgba(248,113,113,0.1)' };
      case 'warning': return { bg: T.yellowDim, text: T.yellow, border: 'rgba(245,158,11,0.1)' };
      default: return { bg: T.s3, text: T.text3, border: T.border };
    }
  };
  const sc = getStatusColor();

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: T.bg, fontFamily: T.fontBody, minWidth: 0 }}>
      <div className="connection-detail-header" style={{ padding: '24px clamp(16px, 3vw, 32px) 20px', background: T.s1, borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
        <div style={{ width: 56, height: 56, borderRadius: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.8rem', flexShrink: 0, background: connection.color }}>
          {connection.icon}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
             <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.4rem', color: T.text, fontStyle: 'italic' }}>{connection.name}</div>
             <div style={{ fontSize: '0.62rem', background: sc.bg, color: sc.text, padding: '2px 8px', fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase' }}>{connection.health_state}</div>
          </div>
          <div style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {connection.host || 'localhost'} - {connection.port || 'N/A'} - DB: {connection.database || 'N/A'} - <span style={{ color: T.accent }}>{connection.type}</span>
          </div>
        </div>

        <div className="connection-detail-actions" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <HeaderBtn icon={<RefreshCw size={12} />} label="RE-DISCOVER" onClick={onRefreshSchema} />
          <HeaderBtn icon={<Edit3 size={12} />} label="CONFIG" onClick={() => setActiveTab('credentials')} />
          <HeaderBtn icon={<Share2 size={12} />} label="SHARE" />
          <HeaderBtn danger onClick={() => onDelete?.(connection.id)} icon={<Trash2 size={12} />} label="DISCONNECT" />
        </div>
      </div>

      <div className="connection-detail-tabs" style={{ display: 'flex', background: T.s1, borderBottom: `1px solid ${T.border}`, padding: '0 clamp(16px, 3vw, 32px)', overflowX: 'auto' }}>
        <Tab active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} label="OVERVIEW" icon={<Layout size={12} />} />
        <Tab active={activeTab === 'credentials'} onClick={() => setActiveTab('credentials')} label="CREDENTIALS" icon={<Shield size={12} />} />
        <Tab active={activeTab === 'schema'} onClick={() => setActiveTab('schema')} label="SCHEMA" icon={<Database size={12} />} />
        <Tab active={activeTab === 'semantics'} onClick={() => setActiveTab('semantics')} label="SEMANTICS" icon={<BookOpen size={12} />} />
        <Tab active={activeTab === 'security'} onClick={() => setActiveTab('security')} label="SECURITY" icon={<Terminal size={12} />} />
        <Tab active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} label="ACTIVITY LOG" icon={<Activity size={12} />} />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 'clamp(20px, 3vw, 32px)' }} className="cd-body">
        {activeTab === 'overview' && <OverviewTab connection={connection} schema={schema ?? null} schemaState={schemaState} queryHistory={queryHistory || []} onTabSwitch={setActiveTab} />}
        {activeTab === 'credentials' && <CredentialsTab connection={connection} onConnectionUpdated={onConnectionUpdated} />}
        {activeTab === 'schema' && <SchemaTab connection={connection} schema={schema ?? null} state={schemaState} error={schemaError} onRefresh={onRefreshSchema} onConnectionUpdated={onConnectionUpdated} />}
        {activeTab === 'semantics' && <SemanticsWorkspace connectionId={connection.id} schema={schema ?? null} />}
        {activeTab === 'security' && <SecurityTab connection={connection} onConnectionUpdated={onConnectionUpdated} />}
        {activeTab === 'activity' && <ActivityTab connection={connection} queryHistory={queryHistory || []} state={queryHistoryState} error={queryHistoryError} />}
      </div>

      <style>{`
        .cd-body::-webkit-scrollbar { width: 4px; }
        .cd-body::-webkit-scrollbar-thumb { background: ${T.s4}; }
      `}</style>
    </div>
  );
}

function HeaderBtn({ icon, label, danger, onClick }: { icon: React.ReactNode, label: string, danger?: boolean, onClick?: () => void }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 0, border: `1px solid ${T.border}`,
      background: 'transparent', color: T.text2, fontSize: '0.68rem', cursor: 'pointer', transition: 'all 0.15s', fontFamily: T.fontMono,
      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px'
    }}
    onMouseOver={e => { e.currentTarget.style.background = danger ? T.redDim : T.s2; e.currentTarget.style.color = danger ? T.red : T.text; }}
    onMouseOut={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = T.text2; }}>
      {icon}
      {label}
    </button>
  );
}

function Tab({ active, onClick, label, icon }: { active: boolean, onClick: () => void, label: string, icon: React.ReactNode }) {
  return (
    <div onClick={onClick} style={{
      padding: '16px 24px', fontSize: '0.68rem', fontFamily: T.fontMono, fontWeight: 700, cursor: 'pointer',
      color: active ? T.accent : T.text3, borderBottom: `2px solid ${active ? T.accent : 'transparent'}`,
      display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s', letterSpacing: '1px',
      background: active ? 'rgba(56,189,248,0.02)' : 'transparent'
    }}>
      {icon}
      {label}
    </div>
  );
}

function OverviewTab({ connection, schema, schemaState = 'idle', queryHistory, onTabSwitch }: { connection: ConnectionListItem, schema: SchemaResponse | null, schemaState?: LoadState, queryHistory: QueryRecord[], onTabSwitch: (t: ConnectionDetailTab) => void }) {
  const navigate = useNavigate();
  const tables = schema?.tables || [];
  const tableCount = schemaState === 'loading' ? '…' : String(tables.length);
  const tableSub = schemaState === 'loading' ? 'LOADING' : 'SCHEMA MAPPED';
  const recentQueries = queryHistory.slice(0, 5);
  const bridgeLabel = connection.health_state.toUpperCase();
  const bridgeColor = connection.status === 'live' ? T.green : connection.status === 'offline' ? T.red : T.yellow;
  const bridgeSub = connection.health_state === 'live'
    ? 'RECENT CHECK PASSED'
    : connection.health_state === 'failed'
      ? 'LATEST CHECK FAILED'
      : connection.health_state === 'stale'
        ? 'CHECK IS OVER 24H OLD'
        : 'NO DURABLE CHECK RECORDED';

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <KpiCard val={tableCount} label="TABLES DISCOVERED" sub={tableSub} valColor={T.accent} />
        <KpiCard val={connection.type} label="ENGINE" sub={connection.host || 'LOCAL'} valColor={T.text} />
        <KpiCard val={bridgeLabel} label="BRIDGE STATUS" sub={bridgeSub} valColor={bridgeColor} />
        <KpiCard val={String(connection.port || 'N/A')} label="PORT" sub={connection.database || 'PRIMARY'} valColor={T.purple} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12, marginBottom: 24 }}>
        <div style={{ padding: 14, border: `1px solid ${T.border}`, background: T.s1 }}><InfoRow label="ACCESS SCOPE" val={connection.scope_mode === 'all' ? 'ALL USER TABLES' : `${connection.included_schemas.length} SCHEMAS + ${connection.included_tables.length} TABLES`} noBorder /></div>
        <div style={{ padding: 14, border: `1px solid ${T.border}`, background: T.s1 }}><InfoRow label="CREDENTIAL REVISION" val={String(connection.credential_revision)} noBorder /></div>
        <div style={{ padding: 14, border: `1px solid ${T.border}`, background: T.s1 }}><InfoRow label="NEXT MAINTENANCE" val={formatTimestamp(connection.next_health_check_at || connection.next_schema_refresh_at)} noBorder /></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24, marginBottom: 24 }}>
        <SectionCard title="SCHEMA LEDGER" badge={{ text: schemaState === 'loading' ? 'LOADING' : `${tables.length} TABLES`, color: T.green }} onAction={() => onTabSwitch('schema')}>
          <div style={{ padding: '8px 12px' }}>
            {schemaState === 'loading' && <div style={{ color: T.text3, fontSize: '0.68rem', padding: 12, fontFamily: T.fontMono }}>LOADING SCHEMA LEDGER...</div>}
            {schemaState !== 'loading' && tables.slice(0, 4).map((t: TableSchema, i: number) => (
              <SchemaTableComponent key={i} name={t.name} rows={t.row_count != null ? `${t.row_count.toLocaleString()} ROWS` : 'N/A'}
                defaultExpanded={i === 0}
                cols={t.columns?.map((c: SchemaColumn) => ({
                  name: c.name,
                  type: c.type?.split('(')[0]?.toUpperCase() || 'UNK',
                  isPk: c.primary_key,
                  isFk: t.foreign_keys.some((fk) => fk.column === c.name),
                })) || []} />
            ))}
            {schemaState !== 'loading' && tables.length === 0 && <div style={{ color: T.text3, fontSize: '0.68rem', padding: 12, fontFamily: T.fontMono }}>NO TABLES DISCOVERED</div>}
          </div>
        </SectionCard>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <SectionCard title="SOURCE TELEMETRY" badge={{ text: bridgeLabel, color: bridgeColor }}>
            <div style={{ padding: '12px 20px' }}>
              <InfoRow label="LAST TESTED" val={formatTimestamp(connection.last_tested_at)} />
              <InfoRow label="LAST STATUS" val={String(connection.last_status || 'unknown').toUpperCase()} />
              <InfoRow label="LATENCY" val={formatLatency(connection.latency)} />
              <InfoRow label="SCHEMA SYNC" val={formatTimestamp(connection.last_schema_sync_at)} />
              <InfoRow label="LATEST ERROR" val={connection.last_error || 'NONE'} noBorder />
            </div>
          </SectionCard>

          <SectionCard title="CONFIG SUMMARY">
            <div style={{ padding: '12px 20px' }}>
              <InfoRow label="TYPE" val={connection.type} />
              <InfoRow label="HOST" val={connection.host || 'localhost'} />
              <InfoRow label="PORT" val={String(connection.port || 'N/A')} />
              <InfoRow label="DB" val={connection.database || 'N/A'} />
              <InfoRow label="USER" val={connection.username || 'N/A'} noBorder />
            </div>
          </SectionCard>
        </div>
      </div>

      <div style={{ marginBottom: 24, padding: 20, border: `1px solid ${T.border}`, background: T.s1 }}>
        <SuggestionGrid
          connectionId={connection.id}
          surface="connection"
          primaryLabel="Ask in Chat"
          secondaryLabel="Build Dashboard"
          onSelect={(suggestion) => navigate('/chat', {
            state: { connectionId: connection.id, prompt: suggestion.prompt, suggestionId: suggestion.id },
          })}
          onSecondarySelect={(suggestion) => navigate('/dashboard', {
            state: { openAiWizard: true, connectionId: connection.id, prompt: suggestion.prompt, suggestionId: suggestion.id },
          })}
        />
      </div>

      <SectionCard title="RECENT QUERY ACTIVITY" onAction={() => onTabSwitch('activity')} actionText="VIEW LOG ->">
         <div style={{ display: 'flex', flexDirection: 'column' }}>
           {recentQueries.map((q: QueryRecord, i: number) => (
             <ActivityRow key={i} ok={q.success} err={!q.success}
               query={q.sql?.substring(0, 80) + (q.sql?.length > 80 ? '...' : '')}
               dur={q.success ? `${((q.execution_time_ms || 0) / 1000).toFixed(3)}S` : 'ERROR'}
               time={timeAgo(q.timestamp)} />
           ))}
           {recentQueries.length === 0 && (
             <div style={{ padding: '24px', color: T.text3, fontSize: '0.68rem', textAlign: 'center', fontFamily: T.fontMono }}>NO RECENT ACTIVITY RECORDED</div>
           )}
         </div>
      </SectionCard>
    </>
  );
}

function CredentialsTab({ connection, onConnectionUpdated }: { connection: ConnectionListItem, onConnectionUpdated?: () => Promise<void> | void }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number | null } | null>(null);
  const [sslMode, setSslMode] = useState(connection.ssl_mode ?? 'disable');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [rootCa, setRootCa] = useState('');
  const [clientCert, setClientCert] = useState('');
  const [clientKey, setClientKey] = useState('');
  const [clearCertificates, setClearCertificates] = useState(false);
  const [sshUsername, setSshUsername] = useState('');
  const [sshPassword, setSshPassword] = useState('');
  const [sshPrivateKey, setSshPrivateKey] = useState('');

  const saveSettings = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      await rotateConnectionCredentials(connection.id, {
        expected_credential_revision: connection.credential_revision,
        ssl_mode: sslMode,
        ...(password ? { password } : {}),
        ...(clearCertificates ? {
          ssl_root_certificate: null,
          ssl_client_certificate: null,
          ssl_client_private_key: null,
        } : {
          ...(rootCa ? { ssl_root_certificate: rootCa } : {}),
          ...(clientCert ? { ssl_client_certificate: clientCert } : {}),
          ...(clientKey ? { ssl_client_private_key: clientKey } : {}),
        }),
        ...(connection.use_ssh ? {
          ...(sshUsername ? { ssh_username: sshUsername } : {}),
          ...(sshPassword ? { ssh_password: sshPassword } : {}),
          ...(sshPrivateKey ? { ssh_private_key: sshPrivateKey } : {}),
        } : {}),
      });
      setPassword(''); setRootCa(''); setClientCert(''); setClientKey(''); setClearCertificates(false);
      setSshUsername(''); setSshPassword(''); setSshPrivateKey('');
      await onConnectionUpdated?.();
      setSaveMsg('SETTINGS SAVED.');
    } catch {
      setSaveMsg('ERROR SAVING SETTINGS.');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testSavedConnection(connection.id);
      setTestResult(result);
      await onConnectionUpdated?.();
    } catch (err: unknown) {
      setTestResult({ success: false, message: (err as Error).message || 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

  const displayedLatency = testResult?.latency_ms ?? connection.latency ?? null;
  const displayedStatus = testResult ? (testResult.success ? 'HEALTHY' : 'FAILED') : String(connection.last_status || 'unknown').toUpperCase();

  return (
    <>
      <div style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: T.accent, fontFamily: T.fontMono, marginBottom: 16 }}>SECURITY & ACCESS</div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0, marginBottom: 20 }}>
        <Shield size={16} color={T.accent} />
        <span style={{ fontSize: '0.7rem', color: T.text2, fontFamily: T.fontMono, fontWeight: 700 }}>
          READ-ONLY MODE ACTIVE BY DEFAULT. YOUR DATA IS SAFE.
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>SSL ENCRYPTION</label>
          <select value={sslMode} onChange={e => setSslMode(e.target.value)} style={{ background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0, padding: '12px 16px', color: T.text, fontFamily: T.fontMono, fontSize: '0.72rem', outline: 'none', cursor: 'pointer', appearance: 'none' }}>
            <option value="disable">DISABLE</option>
            <option value="require">REQUIRE</option>
            <option value="verify-ca">VERIFY-CA</option>
            <option value="verify-full">VERIFY-FULL</option>
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>ACCESS LEVEL</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minHeight: 44, padding: '0 12px', background: T.s2, border: `1px solid ${T.border}` }}>
            <Shield size={14} color={T.accent} />
            <span style={{ fontSize: '0.72rem', color: T.text, fontFamily: T.fontMono, fontWeight: 700 }}>READ-ONLY ENFORCED</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16, marginBottom: 20 }}>
        <CredentialField label="NEW DATABASE PASSWORD" value={password} onChange={setPassword} secret placeholder="Leave blank to keep current" />
        <CredentialField label="ROOT CA CERTIFICATE" value={rootCa} onChange={setRootCa} multiline placeholder={connection.has_ssl_root_certificate ? 'Stored — paste to replace' : '-----BEGIN CERTIFICATE-----'} />
        <CredentialField label="CLIENT CERTIFICATE" value={clientCert} onChange={setClientCert} multiline placeholder={connection.has_ssl_client_certificate ? 'Stored — paste to replace' : 'Optional mTLS certificate'} />
        <CredentialField label="CLIENT PRIVATE KEY" value={clientKey} onChange={setClientKey} multiline placeholder={connection.has_ssl_client_private_key ? 'Stored — paste to replace' : 'Optional matching key'} />
      </div>
      {connection.use_ssh && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16, marginBottom: 20 }}>
        <CredentialField label="SSH USERNAME" value={sshUsername} onChange={setSshUsername} placeholder="Leave blank to keep current" />
        <CredentialField label="NEW SSH PASSWORD" value={sshPassword} onChange={setSshPassword} secret placeholder="Leave blank to keep current" />
        <CredentialField label="NEW SSH PRIVATE KEY" value={sshPrivateKey} onChange={setSshPrivateKey} multiline placeholder="Leave blank to keep current" />
      </div>}
      <label style={{ display: 'flex', gap: 8, color: T.text3, font: `700 .62rem ${T.fontMono}`, marginBottom: 20 }}><input type="checkbox" checked={clearCertificates} onChange={event => setClearCertificates(event.target.checked)} /> CLEAR ALL STORED TLS CERTIFICATES</label>
      <div style={{ color: T.text3, font: `600 .62rem ${T.fontMono}`, marginBottom: 20 }}>CREDENTIAL REVISION {connection.credential_revision} · ROTATION IS TESTED BEFORE THE CURRENT ENGINE IS REPLACED.</div>
      <div style={{ padding: 12, border: `1px solid ${T.border}`, marginBottom: 20 }}><InfoRow label="ROOT CA" val={connection.has_ssl_root_certificate ? 'STORED' : 'NOT SET'} /><InfoRow label="CLIENT CERTIFICATE" val={connection.has_ssl_client_certificate ? 'STORED' : 'NOT SET'} /><InfoRow label="CLIENT PRIVATE KEY" val={connection.has_ssl_client_private_key ? 'STORED' : 'NOT SET'} noBorder /></div>

      <div style={{ padding: '12px 16px', background: T.s1, border: `1px solid ${T.border}`, marginBottom: 20 }}>
        <div style={{ fontSize: '0.62rem', color: T.accent, fontWeight: 700, fontFamily: T.fontMono, letterSpacing: '1px', marginBottom: 8 }}>SAVED CREDENTIAL DIAGNOSTICS</div>
        <div style={{ fontSize: '0.64rem', color: T.text3, fontFamily: T.fontMono, lineHeight: 1.6 }}>
          Diagnostics on this screen use the encrypted credentials already stored on the backend. No password re-entry is required.
        </div>
      </div>

      <div style={{ height: 1, background: T.border, margin: '24px 0' }} />
      <div style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase', color: T.accent, fontFamily: T.fontMono, marginBottom: 16 }}>VALIDATION DISPATCH</div>

      <div style={{ background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0, padding: '20px', marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ fontSize: '0.7rem', fontWeight: 800, color: T.text, fontFamily: T.fontMono }}>HEALTH CHECK RESULTS</span>
          <button onClick={runTest} disabled={testing} style={{ padding: '6px 14px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontSize: '0.62rem', fontFamily: T.fontMono, fontWeight: 700, cursor: testing ? 'not-allowed' : 'pointer', textTransform: 'uppercase' }}>RE-RUN DIAGNOSTICS</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <TestStep label="Saved Credential Check" res={testing ? 'EXECUTING...' : displayedStatus} state={testing ? 'load' : (testResult ? (testResult.success ? 'ok' : 'err') : 'wait')} />
          <TestStep label="Round-trip Latency" res={testing ? 'MEASURING...' : formatLatency(displayedLatency)} state={testing ? 'load' : (displayedLatency != null ? 'ok' : 'wait')} />
          <div style={{ padding: '12px 16px', background: T.s2, border: `1px solid ${T.border}` }}>
            <InfoRow label="LAST TESTED" val={formatTimestamp(connection.last_tested_at)} />
            <InfoRow label="LAST STATUS" val={String(connection.last_status || 'unknown').toUpperCase()} />
            <InfoRow label="SCHEMA SYNC" val={formatTimestamp(connection.last_schema_sync_at)} />
            <InfoRow label="LATEST ERROR" val={connection.last_error || 'NONE'} noBorder />
          </div>
          {testResult && (
            <div style={{ padding: '12px 16px', borderRadius: 0, marginTop: 10, background: testResult.success ? T.greenDim : T.redDim, border: `1px solid ${testResult.success ? T.green : T.red}`, color: testResult.success ? T.green : T.red, fontSize: '0.68rem', fontFamily: T.fontMono, fontWeight: 700 }}>
              {testResult.message.toUpperCase()}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
         <button onClick={saveSettings} disabled={saving} style={{ padding: '12px 28px', borderRadius: 0, border: 'none', background: T.accent, color: '#000', fontSize: '0.7rem', fontWeight: 900, cursor: saving ? 'not-allowed' : 'pointer', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>
           {saving ? 'SAVING...' : 'COMMIT CHANGES'}
         </button>
         <button onClick={runTest} disabled={testing} style={{ padding: '12px 24px', borderRadius: 0, border: `1px solid ${T.accent}`, background: 'transparent', color: T.accent, fontSize: '0.7rem', fontWeight: 900, cursor: testing ? 'not-allowed' : 'pointer', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>{testing ? 'TESTING...' : 'RUN TEST'}</button>
         {saveMsg && <span style={{ fontSize: '0.62rem', color: saveMsg.includes('ERROR') ? T.red : T.green, fontFamily: T.fontMono, fontWeight: 700, letterSpacing: '1px' }}>{saveMsg}</span>}
      </div>
    </>
  );
}

function SchemaTab({ connection, schema, state = 'idle', error, onRefresh, onConnectionUpdated }: { connection: ConnectionListItem, schema?: SchemaResponse | null, state?: LoadState, error?: string | null, onRefresh?: () => Promise<void> | void, onConnectionUpdated?: () => Promise<void> | void }) {
  const tables = schema?.tables || [];
  const [viewMode, setViewMode] = useState<'table' | 'erd'>('table');
  const [healthEnabled, setHealthEnabled] = useState(connection.health_check_enabled);
  const [healthInterval, setHealthInterval] = useState(connection.health_check_interval_minutes);
  const [refreshEnabled, setRefreshEnabled] = useState(connection.schema_refresh_enabled);
  const [refreshInterval, setRefreshInterval] = useState(connection.schema_refresh_interval_hours);
  const [automationMessage, setAutomationMessage] = useState<string | null>(null);
  const saveAutomation = async () => {
    try {
      await updateConnectionAutomation(connection.id, {
        health_check_enabled: healthEnabled, health_check_interval_minutes: healthInterval,
        schema_refresh_enabled: refreshEnabled, schema_refresh_interval_hours: refreshInterval,
      });
      setAutomationMessage('AUTOMATION SETTINGS SAVED.'); await onConnectionUpdated?.();
    } catch (reason) { setAutomationMessage(reason instanceof Error ? reason.message : 'AUTOMATION UPDATE FAILED.'); }
  };

  const toggleBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 16px', borderRadius: 0, border: `1px solid ${active ? T.accent : T.border}`,
    background: active ? T.s2 : 'transparent', color: active ? T.accent : T.text3,
    fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 800,
    transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '1px'
  });

  return (
    <>
      <SectionCard title="OPT-IN MAINTENANCE" badge={{ text: refreshEnabled || healthEnabled ? 'ENABLED' : 'DISABLED', color: refreshEnabled || healthEnabled ? T.green : T.text3 }}>
        <div style={{ padding: 18, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16 }}>
          <label style={{ color: T.text2, font: `700 .66rem ${T.fontMono}` }}><input type="checkbox" checked={healthEnabled} onChange={event => setHealthEnabled(event.target.checked)} /> HEALTH CHECKS<select value={healthInterval} onChange={event => setHealthInterval(Number(event.target.value) as 15 | 60 | 360 | 1440)} style={{ display: 'block', marginTop: 8, width: '100%' }}><option value={15}>15 MINUTES</option><option value={60}>HOURLY</option><option value={360}>6 HOURS</option><option value={1440}>DAILY</option></select></label>
          <label style={{ color: T.text2, font: `700 .66rem ${T.fontMono}` }}><input type="checkbox" checked={refreshEnabled} onChange={event => setRefreshEnabled(event.target.checked)} /> AUTOMATIC SCHEMA REFRESH<select value={refreshInterval} onChange={event => setRefreshInterval(Number(event.target.value) as 6 | 12 | 24 | 168)} style={{ display: 'block', marginTop: 8, width: '100%' }}><option value={6}>6 HOURS</option><option value={12}>12 HOURS</option><option value={24}>DAILY</option><option value={168}>WEEKLY</option></select></label>
        </div>
        <div style={{ padding: '0 18px 18px', color: T.text3, font: `600 .62rem ${T.fontMono}` }}>NEXT HEALTH: {formatTimestamp(connection.next_health_check_at)} · NEXT REFRESH: {formatTimestamp(connection.next_schema_refresh_at)} <button onClick={saveAutomation} style={{ marginLeft: 12 }}>SAVE AUTOMATION</button> {automationMessage}</div>
      </SectionCard>
      <div style={{ height: 20 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div style={{ fontSize: '0.62rem', color: T.accent, fontFamily: T.fontMono, fontWeight: 800, letterSpacing: '1.5px' }}>{tables.length} TABLES DISCOVERED</div>
        <div style={{ display: 'flex', gap: 0, marginLeft: 12 }}>
          <button onClick={() => setViewMode('table')} style={{ ...toggleBtnStyle(viewMode === 'table'), borderRight: 'none' }}>LEDGER</button>
          <button onClick={() => setViewMode('erd')} style={toggleBtnStyle(viewMode === 'erd')}>RELATIONS</button>
        </div>
        {onRefresh && <button onClick={onRefresh} style={{ marginLeft: 'auto', padding: '6px 16px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase' }}>SYNC SCHEMA</button>}
      </div>

      {state === 'loading' && <StateBlock title="SCHEMA SYNC IN PROGRESS" body="Reading table and relationship metadata from the source." />}
      {state === 'error' && <StateBlock title="SCHEMA SYNC FAILED" body={error || 'Schema metadata could not be loaded.'} tone="error" actionLabel="RETRY SYNC" onAction={onRefresh} />}
      {state === 'empty' && <StateBlock title="NO ENTITIES DISCOVERED" body="The schema sync completed, but no tables were returned for this connection." actionLabel="SYNC AGAIN" onAction={onRefresh} />}

      {state !== 'loading' && state !== 'error' && state !== 'empty' && viewMode === 'table' && (
        <SectionCard title="ENTITY DEFINITIONS" badge={{ text: `${tables.length} ENTITIES`, color: T.accent }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr style={{ background: T.s3 }}>
                {['entity name', 'row count', 'attr count'].map(h => (
                  <th key={h} style={{ padding: '12px 20px', textAlign: 'left', fontFamily: T.fontMono, fontSize: '0.6rem', color: T.text3, textTransform: 'uppercase', borderBottom: `1px solid ${T.border}`, letterSpacing: '1px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tables.map((t: TableSchema, i: number) => (
                <tr key={i} style={{ borderBottom: `1px solid ${T.border}`, transition: 'all 0.1s' }} className="schema-row">
                  <td style={{ padding: '12px 20px', color: T.text, fontFamily: T.fontMono, fontWeight: 700 }}>{t.name}</td>
                  <td style={{ padding: '12px 20px', color: T.text2, fontFamily: T.fontMono }}>{t.row_count?.toLocaleString() || 'N/A'}</td>
                  <td style={{ padding: '12px 20px', color: T.text2, fontFamily: T.fontMono }}>{t.columns?.length || 0}</td>
                </tr>
              ))}
              {tables.length === 0 && (
                <tr><td colSpan={3} style={{ padding: '32px', color: T.text3, textAlign: 'center', fontFamily: T.fontMono, fontSize: '0.68rem' }}>NO ENTITIES DISCOVERED - VERIFY SOURCE CONNECTION</td></tr>
              )}
            </tbody>
          </table>
        </SectionCard>
      )}

      {state !== 'loading' && state !== 'error' && state !== 'empty' && viewMode === 'erd' && (
        <div style={{ height: 'calc(100vh - 340px)', minHeight: 450, border: `1px solid ${T.border}` }}>
          <ErdDiagram tables={tables} />
        </div>
      )}
    </>
  );
}

function StateBlock({ title, body, actionLabel, onAction, tone = 'neutral' }: { title: string; body: string; actionLabel?: string; onAction?: () => Promise<void> | void; tone?: 'neutral' | 'error' }) {
  const color = tone === 'error' ? T.red : T.text3;
  return (
    <div style={{ padding: '34px 24px', border: `1px solid ${tone === 'error' ? T.red : T.border}`, background: tone === 'error' ? T.redDim : T.s1, color: T.text3, textAlign: 'center', fontFamily: T.fontMono }}>
      <div style={{ color, fontSize: '0.72rem', fontWeight: 900, letterSpacing: '1px', marginBottom: 10 }}>{title}</div>
      <div style={{ fontSize: '0.68rem', lineHeight: 1.7, maxWidth: 520, margin: '0 auto' }}>{body}</div>
      {actionLabel && onAction && (
        <button onClick={onAction} style={{ marginTop: 18, padding: '8px 16px', border: `1px solid ${tone === 'error' ? T.red : T.accent}`, background: 'transparent', color: tone === 'error' ? T.red : T.accent, fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 900, cursor: 'pointer' }}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
function SecurityTab({ connection, onConnectionUpdated }: { connection: ConnectionListItem; onConnectionUpdated?: () => Promise<void> | void }) {
  const [mode, setMode] = useState<'all' | 'allowlist'>(connection.scope_mode);
  const [schemas, setSchemas] = useState<string[]>(connection.included_schemas);
  const [tables, setTables] = useState<string[]>(connection.included_tables);
  const [inventory, setInventory] = useState<Array<{ name: string; tables: string[] }>>([]);
  const [preview, setPreview] = useState<ConnectionScopePreview | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => { let active = true; discoverConnectionScope(connection.id).then(result => { if (active) setInventory(result.inventory); }).catch(reason => { if (active) setMessage(reason instanceof Error ? reason.message : 'Scope discovery failed.'); }); return () => { active = false; }; }, [connection.id]);
  const toggle = (values: string[], value: string, update: (next: string[]) => void) => update(values.includes(value) ? values.filter(item => item !== value) : [...values, value]);
  const runPreview = async () => { setMessage(null); try { setPreview(await previewConnectionScope(connection.id, { mode, included_schemas: schemas, included_tables: tables })); setAcknowledged(false); } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Scope preview failed.'); } };
  const apply = async () => { if (!preview?.valid) return; try { await updateConnectionScope(connection.id, { mode, included_schemas: schemas, included_tables: tables, expected_scope_revision: connection.scope_revision, acknowledged_impact_codes: acknowledged ? preview.impacts.map(item => item.code) : [] }); setMessage('SCOPE UPDATED.'); setPreview(null); await onConnectionUpdated?.(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'Scope update failed.'); } };
  return <>
    <SectionCard title="DATABASE ROLE GUIDANCE" badge={{ text: 'SELECT ONLY RECOMMENDED', color: T.green }}><div style={{ padding: 18, color: T.text2, font: `600 .68rem/1.7 ${T.fontMono}` }}>Create a dedicated PostgreSQL role with CONNECT on the database, USAGE on allowed schemas, and SELECT on allowed tables. QueryMind scope is an application policy; database grants remain the final authorization boundary.</div></SectionCard>
    <div style={{ height: 20 }} />
    <SectionCard title="QUERYMIND ACCESS SCOPE" badge={{ text: `REVISION ${connection.scope_revision}`, color: T.accent }}><div style={{ padding: 18 }}>
      <label style={{ color: T.text3, font: `700 .62rem ${T.fontMono}` }}>MODE<select value={mode} onChange={event => { setMode(event.target.value as 'all' | 'allowlist'); setPreview(null); }} style={{ display: 'block', width: '100%', margin: '8px 0 16px' }}><option value="all">ALL ACCESSIBLE USER TABLES</option><option value="allowlist">ALLOWLIST</option></select></label>
      {mode === 'allowlist' && <div style={{ maxHeight: 320, overflowY: 'auto', border: `1px solid ${T.border}`, padding: 12 }}>{inventory.map(schema => <div key={schema.name}><label style={{ display: 'block', color: T.text, font: `700 .66rem ${T.fontMono}`, padding: 5 }}><input type="checkbox" checked={schemas.includes(schema.name)} onChange={() => { toggle(schemas, schema.name, setSchemas); setPreview(null); }} /> {schema.name}</label>{schema.tables.map(table => { const value = `${schema.name}.${table}`; return <label key={value} style={{ display: 'block', color: T.text3, font: `600 .64rem ${T.fontMono}`, padding: '4px 24px' }}><input type="checkbox" checked={tables.includes(value)} disabled={schemas.includes(schema.name)} onChange={() => { toggle(tables, value, setTables); setPreview(null); }} /> {table}</label>; })}</div>)}</div>}
      <button onClick={runPreview} style={{ marginTop: 16 }}>PREVIEW IMPACT</button>
      {preview && <div aria-live="polite" style={{ marginTop: 16, padding: 12, background: T.s2, border: `1px solid ${preview.valid ? T.green : T.red}`, color: T.text2, fontFamily: T.fontMono }}><div>{preview.valid ? 'SCOPE IS VALID' : preview.errors.map(item => item.message).join(' ')}</div>{preview.impacts.map(item => <div key={`${item.consumer_type}-${item.consumer_id}`} style={{ marginTop: 6, color: T.yellow }}>{item.consumer_type}: {item.label}</div>)}{preview.impacts.length > 0 && <label style={{ display: 'block', marginTop: 12 }}><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} /> I ACKNOWLEDGE THESE IMPACTS</label>}<button onClick={apply} disabled={!preview.valid || (preview.impacts.length > 0 && !acknowledged)} style={{ marginTop: 12 }}>APPLY SCOPE</button></div>}
      {message && <div aria-live="polite" style={{ marginTop: 12, color: T.accent, fontFamily: T.fontMono }}>{message}</div>}
    </div></SectionCard>
  </>;
}

function ActivityTab({ connection, queryHistory, state = 'idle', error }: { connection: ConnectionListItem; queryHistory?: QueryRecord[], state?: LoadState, error?: string | null }) {
  const records = queryHistory || [];
  const [view, setView] = useState<'query' | 'health'>('query');
  const [health, setHealth] = useState<ConnectionHealthHistory | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const loadHealth = async (cursor?: string | null) => { try { const result = await getConnectionHealth(connection.id, cursor); setHealth(current => cursor && current ? { ...result, items: [...current.items, ...result.items] } : result); setHealthError(null); } catch (reason) { setHealthError(reason instanceof Error ? reason.message : 'Health history failed.'); } };
  return (
    <SectionCard title="ACTIVITY LOG" badge={{ text: view === 'query' ? `${records.length} QUERIES` : `${health?.items.length ?? 0} HEALTH EVENTS`, color: T.accent }}>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', gap: 8, padding: 12 }}><button onClick={() => setView('query')}>QUERY ACTIVITY</button><button onClick={() => { setView('health'); void loadHealth(); }}>CONNECTION HEALTH</button></div>
        {view === 'query' && <>
        {state === 'loading' && <StateBlock title="LOADING QUERY ACTIVITY" body="Retrieving recent runs for this source." />}
        {state === 'error' && <StateBlock title="QUERY ACTIVITY FAILED" body={error || 'Recent query activity could not be loaded.'} tone="error" />}
        {state !== 'loading' && state !== 'error' && records.map((q: QueryRecord, i: number) => (
          <ActivityRow key={i} ok={q.success} err={!q.success}
            query={q.sql?.substring(0, 100) + (q.sql?.length > 100 ? '...' : '')}
            dur={q.success ? `${((q.execution_time_ms || 0) / 1000).toFixed(2)}s` : 'Error'}
            time={timeAgo(q.timestamp)} />
        ))}
        {state !== 'loading' && state !== 'error' && records.length === 0 && (
          <div style={{ padding: '24px', color: T.text3, fontSize: '0.82rem', textAlign: 'center' }}>No queries have been executed yet. Run a query from the Chat page and it will appear here.</div>
        )}
        </>}
        {view === 'health' && <>{healthError && <StateBlock title="HEALTH HISTORY FAILED" body={healthError} tone="error" />}{health && <div style={{ padding: '0 18px 12px', color: T.text3, font: `600 .62rem ${T.fontMono}` }}>24H SUCCESS {health.success_rate_24h}% · 7D SUCCESS {health.success_rate_7d}% · P50 {formatLatency(health.p50_latency_ms)} · P95 {formatLatency(health.p95_latency_ms)}</div>}{health?.items.map(item => <ActivityRow key={item.id} ok={item.status === 'healthy'} err={item.status === 'failed'} query={`${item.source}: ${item.message ?? item.diagnostic_code ?? item.status}`} dur={formatLatency(item.latency_ms)} time={timeAgo(item.created_at)} />)}{health?.next_cursor && <button onClick={() => loadHealth(health.next_cursor)} style={{ margin: 12 }}>LOAD MORE</button>}</>}
      </div>
    </SectionCard>
  );
}

function CredentialField({ label, value, onChange, secret, multiline, placeholder }: { label: string; value: string; onChange: (value: string) => void; secret?: boolean; multiline?: boolean; placeholder?: string }) {
  const style: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: 10, background: T.s2, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.fontMono };
  return <label style={{ color: T.text3, font: `700 .62rem ${T.fontMono}` }}>{label}{multiline ? <textarea rows={4} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} style={{ ...style, display: 'block', marginTop: 8 }} /> : <input type={secret ? 'password' : 'text'} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} style={{ ...style, display: 'block', marginTop: 8 }} />}</label>;
}

function KpiCard({ val, label, sub, valColor }: { val: string, label: string, sub: string, valColor: string }) {
  return (
    <div style={{ background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0, padding: '20px 24px', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: 2, height: '100%', background: valColor }} />
      <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.8rem', letterSpacing: '-1px', marginBottom: 4, color: valColor, fontStyle: 'italic' }}>{val}</div>
      <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 700, letterSpacing: '1px' }}>{label}</div>
      <div style={{ fontSize: '0.62rem', fontFamily: T.fontMono, marginTop: 4, color: T.text3, opacity: 0.7 }}>{sub}</div>
    </div>
  );
}

function SectionCard({ title, badge, onAction, actionText, children }: { title: string, badge?: { text: string, color: string }, onAction?: () => void, actionText?: string, children: React.ReactNode }) {
  return (
    <div style={{ background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: `1px solid ${T.border}`, background: T.s2 }}>
        <span style={{ fontFamily: T.fontMono, fontWeight: 700, fontSize: '0.7rem', color: T.text, letterSpacing: '1px' }}>{title}</span>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {badge && <span style={{ fontSize: '0.58rem', fontFamily: T.fontMono, padding: '2px 8px', borderRadius: 0, background: `${badge.color}15`, color: badge.color, border: `1px solid ${badge.color}33`, fontWeight: 700 }}>{badge.text}</span>}
          {onAction && <button onClick={onAction} style={{ padding: '4px 12px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text3, fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 700 }}>{actionText || 'VIEW ALL ->'}</button>}
        </div>
      </div>
      {children}
    </div>
  );
}

function SchemaTableComponent({ name, rows, defaultExpanded, cols }: { name: string, rows: string, defaultExpanded?: boolean, cols: UiColumnSchema[] }) {
  const [isOpen, setIsOpen] = useState(defaultExpanded || false);
  return (
    <div style={{ marginBottom: 2 }}>
      <div onClick={() => setIsOpen(!isOpen)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', cursor: 'pointer', background: isOpen ? T.s2 : 'transparent', borderBottom: `1px solid ${T.border}` }}>
        <div style={{ width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem', color: T.text3, flexShrink: 0 }}>{isOpen ? '-' : '+'}</div>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: T.text2, flex: 1, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{name}</span>
        <span style={{ fontSize: '0.58rem', fontFamily: T.fontMono, color: T.text3 }}>{rows}</span>
      </div>
      {isOpen && cols.length > 0 && (
         <div style={{ paddingLeft: 26, background: T.s1 }}>
           {cols.map((c, i) => (
             <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 12px', borderBottom: `1px solid ${T.s2}` }}>
               <span style={{ fontSize: '0.55rem', fontFamily: T.fontMono, padding: '1px 6px', background: T.s3, color: T.text3, fontWeight: 700 }}>{c.type}</span>
               <span style={{ fontSize: '0.7rem', color: T.text2, fontFamily: T.fontMono }}>{c.name}</span>
               {c.isPk && <span style={{ fontSize: '0.55rem', color: T.accent, marginLeft: 'auto', fontWeight: 800, fontFamily: T.fontMono }}>PRI</span>}
               {c.isFk && <span style={{ fontSize: '0.55rem', color: T.text3, marginLeft: 'auto', fontWeight: 800, fontFamily: T.fontMono }}>EXT</span>}
             </div>
           ))}
         </div>
      )}
    </div>
  );
}

function InfoRow({ label, val, noBorder }: { label: string, val: React.ReactNode, noBorder?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: noBorder ? 'none' : `1px solid ${T.border}`, fontSize: '0.68rem', gap: 16 }}>
      <span style={{ color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{label}</span>
      <span style={{ color: T.text2, fontFamily: T.fontMono, fontWeight: 700, textAlign: 'right', wordBreak: 'break-word' }}>{val}</span>
    </div>
  );
}

function ActivityRow({ ok, err, query, dur, time }: { ok?: boolean, err?: boolean, query: string, dur: string, time: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 20px', borderBottom: `1px solid ${T.border}`, transition: 'all 0.15s' }} className="activity-row">
      <div style={{ width: 8, height: 8, borderRadius: 0, flexShrink: 0, background: err ? T.red : T.green }} />
      <span style={{ fontSize: '0.72rem', color: err ? T.red : T.text2, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: T.fontMono }}>{query}</span>
      <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: err ? T.red : (ok ? T.green : T.yellow), flexShrink: 0, fontWeight: 700 }}>{dur}</span>
      <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, flexShrink: 0 }}>{time}</span>
    </div>
  );
}

function TestStep({ label, res, state }: { label: string, res: string, state: 'wait'|'load'|'ok'|'err' }) {
  const st = {
    wait: { icon: '...', bg: T.s3, col: T.text3 },
    load: { icon: 'REF', bg: T.accentDim, col: T.accent },
    ok: { icon: 'OK', bg: T.greenDim, col: T.green },
    err: { icon: 'ERR', bg: T.redDim, col: T.red },
  }[state];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderRadius: 0, background: T.s2, border: `1px solid ${T.border}` }}>
       <div style={{ width: 32, height: 20, borderRadius: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.55rem', flexShrink: 0, background: st.bg, color: st.col, fontWeight: 900, fontFamily: T.fontMono }}>
         {st.icon}
       </div>
       <span style={{ fontSize: '0.68rem', color: T.text2, flex: 1, fontFamily: T.fontMono, textTransform: 'uppercase', fontWeight: 700 }}>{label}</span>
       <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: state === 'wait' ? T.text3 : st.col, fontWeight: 700 }}>{res}</span>
    </div>
  );
}
