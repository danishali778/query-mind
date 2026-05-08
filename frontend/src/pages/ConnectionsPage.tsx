import { useState, useEffect } from 'react';
import { MainShell } from '../components/common/MainShell';
import { HeaderIcons } from '../components/common/AppHeader';
import { ConnectionListPanel } from '../components/connections/ConnectionListPanel';
import { ConnectionDetail } from '../components/connections/ConnectionDetail';
import { NewConnectionModal } from '../components/connections/NewConnectionModal';
import { T } from '../components/dashboard/tokens';
import { listConnections, disconnectDatabase, getSchema, getQueryHistory } from '../services/api';
import type { QueryRecord, SchemaResponse } from '../types/api';
import type { ConnectionListItem } from '../types/connections';
import { mapConnectionRecord } from '../mappers/connections';

export function ConnectionsPage() {
  const [connections, setConnections] = useState<ConnectionListItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [queryHistory, setQueryHistory] = useState<QueryRecord[]>([]);

  const fetchConnections = async () => {
    try {
      const data = await listConnections();
      const mapped = data.map(mapConnectionRecord);
      setConnections(mapped);
      if (mapped.length > 0 && !activeId) {
        setActiveId(mapped[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch connections:', err);
    }
  };

  useEffect(() => {
    fetchConnections();
  }, []);

  useEffect(() => {
    if (!activeId) { setSchema(null); return; }
    getSchema(activeId)
      .then(setSchema)
      .catch(() => setSchema(null));
    getQueryHistory(activeId, 20)
      .then(setQueryHistory)
      .catch(() => setQueryHistory([]));
  }, [activeId]);

  const handleDelete = async (connId: string) => {
    try {
      await disconnectDatabase(connId);
      setConnections(prev => prev.filter(c => c.id !== connId));
      if (activeId === connId) {
        setActiveId(connections.find(c => c.id !== connId)?.id || null);
      }
    } catch (err) {
      console.error('Failed to disconnect:', err);
    }
  };

  const handleConnectionAdded = () => {
    setIsModalOpen(false);
    fetchConnections();
  };

  const activeConnection = connections.find(c => c.id === activeId) || null;

  return (
    <MainShell
      title="Connection Ledger"
      subtitle="Source distribution and technical bridge telemetry"
      badge={{
        text: 'Live',
        color: T.accent,
        icon: <div className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: T.accent }} />
      }}
      headerActions={
        <button 
          onClick={() => setIsModalOpen(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 18px', borderRadius: 0,
            border: `1px solid ${T.accent}`, background: T.accent,
            color: '#000', fontSize: '0.72rem', cursor: 'pointer', fontFamily: T.fontMono,
            transition: 'all 0.15s ease', fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.5px'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#fff';
            e.currentTarget.style.borderColor = '#fff';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = T.accent;
            e.currentTarget.style.borderColor = T.accent;
          }}
        >
          <HeaderIcons.Plus width={14} height={14} strokeWidth={3} /> New Connection
        </button>
      }
    >
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <ConnectionListPanel
          connections={connections}
          activeId={activeId}
          onSelect={setActiveId}
          onAdd={() => setIsModalOpen(true)}
        />
        <ConnectionDetail
          connection={activeConnection}
          schema={schema}
          queryHistory={queryHistory}
          onDelete={handleDelete}
          onRefreshSchema={() => {
            if (activeId) getSchema(activeId).then(setSchema).catch(() => setSchema(null));
          }}
        />
      </div>

      <NewConnectionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSaved={handleConnectionAdded}
      />
      <style>{`
        .pulse-dot { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .4; } }
      `}</style>
    </MainShell>
  );
}
