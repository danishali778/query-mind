import React, { useState } from 'react';
import { RefreshCw, Edit3, Share2, Trash2, Database, Shield, Activity, Layout, Terminal } from 'lucide-react';
import { T } from '../dashboard/tokens';
import type { ConnectionListItem, ConnectionDetailProps, ConnectionDetailTab } from '../../types/connections';
import type { QueryRecord, SchemaResponse, SchemaTable, SchemaColumn } from '../../types/api';
import { ErdDiagram } from './ErdDiagram';
import { updateConnectionSettings, testConnection } from '../../services/api';

// ---------------------------------------------------------------------------
// Local type definitions for schema and query data
// ---------------------------------------------------------------------------
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

export function ConnectionDetail({ connection, schema, queryHistory, onDelete, onRefreshSchema }: ConnectionDetailProps) {
  const [activeTab, setActiveTab] = useState<ConnectionDetailTab>('overview');
  
  if (!connection) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: T.bg, color: T.text3, fontFamily: T.fontMono, fontSize: '0.72rem', letterSpacing: '1px' }}>
        SELECT A DATA SOURCE TO VIEW LEDGER
      </div>
    );
  }

  const getStatusColor = () => {
    switch(connection.status) {
      case 'live': return { bg: T.greenDim, text: T.green, border: 'rgba(34,211,165,0.1)' };
      case 'offline': return { bg: T.redDim, text: T.red, border: 'rgba(248,113,113,0.1)' };
      case 'warning': return { bg: T.yellowDim, text: T.yellow, border: 'rgba(245,158,11,0.1)' };
      default: return { bg: T.s3, text: T.text3, border: T.border };
    }
  };
  const sc = getStatusColor();

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: T.bg, fontFamily: T.fontBody }}>
      
      {/* Header Masthead */}
      <div style={{ padding: '24px 32px 20px', background: T.s1, borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ width: 56, height: 56, borderRadius: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.8rem', flexShrink: 0, background: connection.color }}>
          {connection.icon}
        </div>
        
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
             <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.4rem', color: T.text, fontStyle: 'italic' }}>{connection.name}</div>
             <div style={{ fontSize: '0.62rem', background: sc.bg, color: sc.text, padding: '2px 8px', fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase' }}>{connection.status}</div>
          </div>
          <div style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {connection.host || 'localhost'} · {connection.port || 'N/A'} · DB: {connection.database || 'N/A'} · <span style={{ color: T.accent }}>{connection.type}</span>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: 8 }}>
          <HeaderBtn icon={<RefreshCw size={12} />} label="RE-DISCOVER" onClick={onRefreshSchema} />
          <HeaderBtn icon={<Edit3 size={12} />} label="CONFIG" onClick={() => setActiveTab('credentials')} />
          <HeaderBtn icon={<Share2 size={12} />} label="SHARE" />
          <HeaderBtn danger onClick={() => onDelete?.(connection.id)} icon={<Trash2 size={12} />} label="DISCONNECT" />
        </div>
      </div>

      {/* Navigation Ledger */}
      <div style={{ display: 'flex', background: T.s1, borderBottom: `1px solid ${T.border}`, padding: '0 32px' }}>
        <Tab active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} label="OVERVIEW" icon={<Layout size={12} />} />
        <Tab active={activeTab === 'credentials'} onClick={() => setActiveTab('credentials')} label="CREDENTIALS" icon={<Shield size={12} />} />
        <Tab active={activeTab === 'schema'} onClick={() => setActiveTab('schema')} label="SCHEMA" icon={<Database size={12} />} />
        <Tab active={activeTab === 'security'} onClick={() => setActiveTab('security')} label="SECURITY" icon={<Terminal size={12} />} />
        <Tab active={activeTab === 'activity'} onClick={() => setActiveTab('activity')} label="ACTIVITY LOG" icon={<Activity size={12} />} />
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px' }} className="cd-body">
        
        {activeTab === 'overview' && <OverviewTab connection={connection} schema={schema ?? null} queryHistory={queryHistory || []} onTabSwitch={setActiveTab} />}
        {activeTab === 'credentials' && <CredentialsTab connection={connection} />}
        {activeTab === 'schema' && <SchemaTab schema={schema ?? null} onRefresh={onRefreshSchema} />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'activity' && <ActivityTab queryHistory={queryHistory || []} />}

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

function OverviewTab({ connection, schema, queryHistory, onTabSwitch }: { connection: ConnectionListItem, schema: SchemaResponse | null, queryHistory: QueryRecord[], onTabSwitch: (t: ConnectionDetailTab) => void }) {
  const tables = schema?.tables || [];
  const tableCount = tables.length;
  const recentQueries = queryHistory.slice(0, 5);

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <KpiCard val={String(tableCount)} label="TABLES DISCOVERED" sub="SCHEMA MAPPED" valColor={T.accent} />
        <KpiCard val={connection.type} label="ENGINE" sub={connection.host || 'LOCAL'} valColor={T.text} />
        <KpiCard val={connection.status === 'live' ? 'ONLINE' : 'OFFLINE'} label="BRIDGE STATUS" sub={connection.status === 'live' ? 'SYNCED' : 'DISCONNECTED'} valColor={connection.status === 'live' ? T.green : T.red} />
        <KpiCard val={String(connection.port || 'N/A')} label="PORT" sub={connection.database || 'PRIMARY'} valColor={T.purple} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24, marginBottom: 24 }}>
        <SectionCard title="SCHEMA LEDGER" badge={{ text: `${tableCount} TABLES`, color: T.green }} onAction={() => onTabSwitch('schema')}>
          <div style={{ padding: '8px 12px' }}>
            {tables.slice(0, 4).map((t: TableSchema, i: number) => (
              <SchemaTableComponent key={i} name={t.name} rows={t.row_count != null ? `${t.row_count.toLocaleString()} ROWS` : 'N/A'}
                defaultExpanded={i === 0}
                cols={t.columns?.map((c: SchemaColumn) => ({
                  name: c.name,
                  type: c.type?.split('(')[0]?.toUpperCase() || 'UNK',
                  isPk: c.primary_key,
                  isFk: t.foreign_keys.some((fk) => fk.column === c.name),
                })) || []} />
            ))}
            {tables.length === 0 && <div style={{ color: T.text3, fontSize: '0.68rem', padding: 12, fontFamily: T.fontMono }}>NO TABLES DISCOVERED</div>}
          </div>
        </SectionCard>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <SectionCard title="SOURCE TELEMETRY" badge={{ text: 'LIVE', color: T.accent }}>
            <div style={{ padding: '24px 20px', textAlign: 'center', color: T.text3, fontSize: '0.68rem', fontFamily: T.fontMono, letterSpacing: '0.5px' }}>
              SOURCE HEALTH MONITORING ACTIVE
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
      
      <SectionCard title="RECENT QUERY ACTIVITY" onAction={() => onTabSwitch('activity')} actionText="VIEW LOG →">
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

function CredentialsTab({ connection }: { connection: ConnectionListItem }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; tables_found?: number | null } | null>(null);
  const [sslMode, setSslMode] = useState(connection.ssl_mode ?? 'disable');
  const [readonly, setReadonly] = useState(connection.readonly ?? true);
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const saveSettings = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      await updateConnectionSettings(connection.id, { ssl_mode: sslMode, readonly });
      setSaveMsg('SETTINGS SAVED.');
    } catch {
      setSaveMsg('ERROR SAVING SETTINGS.');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  };

  const runTest = async () => {
    if (!password.trim()) {
      setTestResult({
        success: false,
        message: 'Re-enter the database password to validate the saved connection credentials.',
      });
      return;
    }

    setTesting(true);
    setTestResult(null);
    try {
      const result = await testConnection({
        db_type: connection.type,
        host: connection.host || 'localhost',
        port: connection.port || 5432,
        database: connection.database || '',
        username: connection.username || '',
        password,
      });
      setTestResult(result);
    } catch (err: unknown) {
      setTestResult({ success: false, message: (err as Error).message || 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

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
            <option value="verify-full">VERIFY-FULL</option>
          </select>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>ACCESS LEVEL</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 44 }}>
            <button type="button" onClick={() => setReadonly(r => !r)} style={{ width: 44, height: 22, borderRadius: 0, border: `1px solid ${T.border}`, cursor: 'pointer', background: readonly ? T.accent : T.s4, position: 'relative', transition: 'all 0.2s', flexShrink: 0 }}>
              <div style={{ position: 'absolute', top: 2, left: readonly ? 24 : 2, width: 16, height: 16, borderRadius: 0, background: '#000', transition: 'left 0.2s' }} />
            </button>
            <span style={{ fontSize: '0.72rem', color: readonly ? T.text : T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{readonly ? 'READ-ONLY' : 'READ / WRITE'}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
        <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>RE-ENTER PASSWORD FOR TEST</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="••••••••"
          style={{
            background: T.s2,
            border: `1px solid ${T.border}`,
            borderRadius: 0,
            padding: '12px 16px',
            color: T.text,
            fontFamily: T.fontMono,
            fontSize: '0.72rem',
            outline: 'none',
            width: '100%',
            transition: 'all 0.15s',
            letterSpacing: '0.5px'
          }}
        />
        <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, lineHeight: 1.6 }}>
          This is used only for validation. It is not saved from this screen.
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
          <TestStep label="Establishing Bridge" res={testing ? 'EXECUTING...' : (testResult ? (testResult.success ? 'BRIDGE SECURE' : 'BRIDGE FAILED') : 'AWAITING DISPATCH')} state={testing ? 'load' : (testResult ? (testResult.success ? 'ok' : 'err') : 'wait')} />
          <TestStep label="Schema Discovery" res={testing ? 'WAITING...' : (testResult?.success ? `${testResult.tables_found || 0} TABLES DISCOVERED` : (testResult ? 'N/A' : 'AWAITING DISPATCH'))} state={testing ? 'wait' : (testResult ? (testResult.success ? 'ok' : 'err') : 'wait')} />
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

function SchemaTab({ schema, onRefresh }: { schema?: SchemaResponse | null, onRefresh?: () => void }) {
  const tables = schema?.tables || [];
  const [viewMode, setViewMode] = useState<'table' | 'erd'>('table');

  const toggleBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 16px', borderRadius: 0, border: `1px solid ${active ? T.accent : T.border}`,
    background: active ? T.s2 : 'transparent', color: active ? T.accent : T.text3,
    fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 800,
    transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '1px'
  });

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div style={{ fontSize: '0.62rem', color: T.accent, fontFamily: T.fontMono, fontWeight: 800, letterSpacing: '1.5px' }}>{tables.length} TABLES DISCOVERED</div>
        <div style={{ display: 'flex', gap: 0, marginLeft: 12 }}>
          <button onClick={() => setViewMode('table')} style={{ ...toggleBtnStyle(viewMode === 'table'), borderRight: 'none' }}>LEDGER</button>
          <button onClick={() => setViewMode('erd')} style={toggleBtnStyle(viewMode === 'erd')}>RELATIONS</button>
        </div>
        {onRefresh && <button onClick={onRefresh} style={{ marginLeft: 'auto', padding: '6px 16px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase' }}>SYNC SCHEMA</button>}
      </div>

      {viewMode === 'table' && (
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
                <tr><td colSpan={3} style={{ padding: '32px', color: T.text3, textAlign: 'center', fontFamily: T.fontMono, fontSize: '0.68rem' }}>NO ENTITIES DISCOVERED — VERIFY SOURCE CONNECTION</td></tr>
              )}
            </tbody>
          </table>
        </SectionCard>
      )}

      {viewMode === 'erd' && (
        <div style={{ height: 'calc(100vh - 340px)', minHeight: 450, border: `1px solid ${T.border}` }}>
          <ErdDiagram tables={tables} />
        </div>
      )}
    </>
  );
}

function SecurityTab() {
  return (
    <div style={{ color: T.text2 }}>Security settings coming soon...</div>
  )
}
function ActivityTab({ queryHistory }: { queryHistory?: QueryRecord[] }) {
  const records = queryHistory || [];
  return (
    <SectionCard title="All Query Activity" badge={{ text: `${records.length} queries`, color: T.accent }}>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {records.map((q: QueryRecord, i: number) => (
          <ActivityRow key={i} ok={q.success} err={!q.success}
            query={q.sql?.substring(0, 100) + (q.sql?.length > 100 ? '...' : '')}
            dur={q.success ? `${((q.execution_time_ms || 0) / 1000).toFixed(2)}s` : 'Error'}
            time={timeAgo(q.timestamp)} />
        ))}
        {records.length === 0 && (
          <div style={{ padding: '24px', color: T.text3, fontSize: '0.82rem', textAlign: 'center' }}>No queries have been executed yet. Run a query from the Chat page and it will appear here.</div>
        )}
      </div>
    </SectionCard>
  )
}


// ------------------------
// Helpers
// ------------------------

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
          {onAction && <button onClick={onAction} style={{ padding: '4px 12px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text3, fontSize: '0.62rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 700 }}>{actionText || 'VIEW ALL →'}</button>}
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
        <div style={{ width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem', color: T.text3, flexShrink: 0 }}>{isOpen ? '—' : '+'}</div>
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
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: noBorder ? 'none' : `1px solid ${T.border}`, fontSize: '0.68rem' }}>
      <span style={{ color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{label}</span>
      <span style={{ color: T.text2, fontFamily: T.fontMono, fontWeight: 700 }}>{val}</span>
    </div>
  )
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
    wait: { icon: '···', bg: T.s3, col: T.text3, spin: false },
    load: { icon: 'REF', bg: T.accentDim, col: T.accent, spin: true },
    ok: { icon: 'OK!', bg: T.greenDim, col: T.green, spin: false },
    err: { icon: 'ERR', bg: T.redDim, col: T.red, spin: false },
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

