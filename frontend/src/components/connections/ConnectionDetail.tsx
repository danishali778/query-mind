import { useState, type ReactNode } from 'react';
import { Activity, Database, Layout, Settings2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import type { ConnectionDetailProps, ConnectionDetailTab } from '../../types/connections';
import { T } from '../dashboard/tokens';
import { ConnectionActivityTab } from './ConnectionActivityTab';
import { ConnectionOverviewTab } from './ConnectionOverviewTab';
import { ConnectionSchemaTab } from './ConnectionSchemaTab';
import { ConnectionSettingsTab } from './ConnectionSettingsTab';

const tabs: Array<{ id: ConnectionDetailTab; label: string; icon: ReactNode }> = [
  { id: 'overview', label: 'OVERVIEW', icon: <Layout size={13} /> },
  { id: 'schema', label: 'SCHEMA', icon: <Database size={13} /> },
  { id: 'activity', label: 'ACTIVITY', icon: <Activity size={13} /> },
  { id: 'settings', label: 'SETTINGS', icon: <Settings2 size={13} /> },
];

export function ConnectionDetail({ connection, schema, schemaState = 'idle', schemaError, queryHistory = [], queryHistoryState = 'idle', queryHistoryError, onDelete, onRefreshSchema, onConnectionUpdated }: ConnectionDetailProps) {
  const [activeTab, setActiveTab] = useState<ConnectionDetailTab>('overview');
  const navigate = useNavigate();

  if (!connection) {
    return <div style={{ flex: 1, display: 'grid', placeItems: 'center', background: T.bg, color: T.text3, font: `700 .72rem ${T.fontMono}`, letterSpacing: 1 }}>SELECT A DATA SOURCE</div>;
  }

  const statusColor = connection.status === 'live' ? T.green : connection.status === 'offline' ? T.red : T.yellow;

  return <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: T.bg, fontFamily: T.fontBody }}>
    <header className="connection-detail-header" style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap', padding: '22px clamp(16px,3vw,30px)', background: T.s1, borderBottom: `1px solid ${T.border}` }}>
      <div aria-hidden="true" style={{ width: 50, height: 50, display: 'grid', placeItems: 'center', flexShrink: 0, background: connection.color, font: `900 1.3rem ${T.fontHead}`, color: '#000' }}>{connection.icon}</div>
      <div style={{ minWidth: 180, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}><h2 style={{ margin: 0, color: T.text, font: `900 1.3rem ${T.fontHead}` }}>{connection.name}</h2><span style={{ padding: '3px 8px', color: statusColor, background: `${statusColor}18`, border: `1px solid ${statusColor}44`, font: `800 .58rem ${T.fontMono}` }}>{connection.health_state.toUpperCase()}</span></div>
        <div style={{ marginTop: 5, color: T.text3, font: `600 .66rem ${T.fontMono}`, wordBreak: 'break-word' }}>{connection.host || 'localhost'}:{connection.port || 'N/A'}/{connection.database || 'N/A'}</div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <HeaderAction label="ASK IN CHAT" onClick={() => navigate('/chat', { state: { connectionId: connection.id } })} primary />
        <HeaderAction label="BUILD DASHBOARD" onClick={() => navigate('/dashboard', { state: { openAiWizard: true, connectionId: connection.id } })} />
      </div>
    </header>

    <div role="tablist" aria-label="Connection sections" style={{ display: 'flex', overflowX: 'auto', padding: '0 clamp(16px,3vw,30px)', background: T.s1, borderBottom: `1px solid ${T.border}` }}>
      {tabs.map(tab => <button key={tab.id} id={`connection-${tab.id}-tab`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`connection-${tab.id}-panel`} onClick={() => setActiveTab(tab.id)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '15px 20px', background: activeTab === tab.id ? 'rgba(56,189,248,.03)' : 'transparent', border: 0, borderBottom: `2px solid ${activeTab === tab.id ? T.accent : 'transparent'}`, color: activeTab === tab.id ? T.accent : T.text3, cursor: 'pointer', font: `800 .66rem ${T.fontMono}`, letterSpacing: 1 }}>{tab.icon}{tab.label}</button>)}
    </div>

    <main id={`connection-${activeTab}-panel`} role="tabpanel" aria-labelledby={`connection-${activeTab}-tab`} tabIndex={0} className="cd-body" style={{ flex: 1, overflowY: 'auto', padding: 'clamp(18px,3vw,30px)' }}>
      {activeTab === 'overview' && <ConnectionOverviewTab connection={connection} schema={schema ?? null} schemaState={schemaState} queryHistory={queryHistory} onTabSwitch={setActiveTab} onConnectionUpdated={onConnectionUpdated} />}
      {activeTab === 'schema' && <ConnectionSchemaTab connection={connection} schema={schema ?? null} state={schemaState} error={schemaError} onRefresh={onRefreshSchema} />}
      {activeTab === 'activity' && <ConnectionActivityTab queryHistory={queryHistory} state={queryHistoryState} error={queryHistoryError} />}
      {activeTab === 'settings' && <ConnectionSettingsTab connection={connection} onConnectionUpdated={onConnectionUpdated} onDelete={onDelete} />}
    </main>
  </div>;
}

function HeaderAction({ label, onClick, primary }: { label: string; onClick: () => void; primary?: boolean }) {
  return <button type="button" onClick={onClick} style={{ padding: '9px 14px', background: primary ? T.accent : 'transparent', border: `1px solid ${primary ? T.accent : T.border}`, color: primary ? '#000' : T.text2, cursor: 'pointer', font: `900 .62rem ${T.fontMono}` }}>{label}</button>;
}
