import { useCallback, useEffect, useMemo, useState } from 'react';
import { MainShell } from '../components/common/MainShell';
import { HeaderIcons } from '../components/common/AppHeader';
import { ConnectionListPanel } from '../components/connections/ConnectionListPanel';
import { ConnectionDetail } from '../components/connections/ConnectionDetail';
import { DisconnectConnectionModal } from '../components/connections/DisconnectConnectionModal';
import { NewConnectionWizard } from '../components/connections/NewConnectionWizard';
import { T } from '../components/dashboard/tokens';
import { listConnections, disconnectDatabase, getSchema, refreshSchema, getQueryHistory } from '../services/api';
import { ApiRequestError } from '../services/http';
import type { QueryRecord, SchemaResponse } from '../types/api';
import type { ConnectionListItem, LoadState } from '../types/connections';
import { mapConnectionRecord } from '../mappers/connections';
import { useAuth } from '../context/useAuth';

function stableMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) {
    if (error.status === 401) return 'Session expired. Sign in again to continue.';
    if (error.status === 404) return 'The selected connection no longer exists.';
    if (error.status === 429) return 'Too many connection requests. Try again shortly.';
    if (error.status === 503 || error.status === 0) return 'Connection service is temporarily unavailable.';
  }
  return fallback;
}

export function ConnectionsPage() {
  const { user } = useAuth();
  const [connections, setConnections] = useState<ConnectionListItem[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<LoadState>('loading');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [schemaStatus, setSchemaStatus] = useState<LoadState>('idle');
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [queryHistory, setQueryHistory] = useState<QueryRecord[]>([]);
  const [queryHistoryStatus, setQueryHistoryStatus] = useState<LoadState>('idle');
  const [queryHistoryError, setQueryHistoryError] = useState<string | null>(null);
  const [pendingDisconnect, setPendingDisconnect] = useState<ConnectionListItem | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnectError, setDisconnectError] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    setConnectionStatus(prev => prev === 'ready' ? 'ready' : 'loading');
    setConnectionError(null);
    try {
      const data = await listConnections();
      const mapped = data.map(mapConnectionRecord);
      setConnections(mapped);
      setConnectionStatus(mapped.length > 0 ? 'ready' : 'empty');
      setActiveId(currentActiveId => {
        if (currentActiveId && mapped.some(connection => connection.id === currentActiveId)) {
          return currentActiveId;
        }
        return mapped[0]?.id || null;
      });
    } catch (err) {
      setConnectionStatus('error');
      setConnectionError(stableMessage(err, 'Connection records could not be loaded.'));
    }
  }, []);

  useEffect(() => {
    if (!user?.id) {
      setConnections([]);
      setConnectionStatus('loading');
      setConnectionError(null);
      setActiveId(null);
      return;
    }
    void fetchConnections();
  }, [user?.id, fetchConnections]);

  useEffect(() => {
    let cancelled = false;

    if (!activeId) {
      setSchema(null);
      setSchemaStatus('idle');
      setSchemaError(null);
      setQueryHistory([]);
      setQueryHistoryStatus('idle');
      setQueryHistoryError(null);
      return;
    }

    setSchema(null);
    setSchemaStatus('loading');
    setSchemaError(null);
    getSchema(activeId)
      .then(nextSchema => {
        if (cancelled) return;
        setSchema(nextSchema);
        setSchemaStatus(nextSchema.tables.length > 0 ? 'ready' : 'empty');
      })
      .catch(err => {
        if (cancelled) return;
        setSchema(null);
        setSchemaStatus('error');
        setSchemaError(stableMessage(err, 'Schema sync failed for this connection.'));
      });

    setQueryHistory([]);
    setQueryHistoryStatus('loading');
    setQueryHistoryError(null);
    getQueryHistory(activeId, 20)
      .then(records => {
        if (cancelled) return;
        setQueryHistory(records);
        setQueryHistoryStatus(records.length > 0 ? 'ready' : 'empty');
      })
      .catch(err => {
        if (cancelled) return;
        setQueryHistory([]);
        setQueryHistoryStatus('error');
        setQueryHistoryError(stableMessage(err, 'Query activity could not be loaded.'));
      });

    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const handleRefreshSchema = async () => {
    if (!activeId) {
      return;
    }
    setSchemaStatus('loading');
    setSchemaError(null);
    try {
      const refreshedSchema = await refreshSchema(activeId);
      setSchema(refreshedSchema);
      setSchemaStatus(refreshedSchema.tables.length > 0 ? 'ready' : 'empty');
    } catch (err) {
      setSchema(null);
      setSchemaStatus('error');
      setSchemaError(stableMessage(err, 'Schema sync failed for this connection.'));
    }
    await fetchConnections();
  };

  const handleRequestDelete = (connId: string) => {
    const conn = connections.find(c => c.id === connId) || null;
    setPendingDisconnect(conn);
    setDisconnectError(null);
  };

  const handleConfirmDisconnect = async () => {
    if (!pendingDisconnect) return;
    setDisconnecting(true);
    setDisconnectError(null);
    try {
      await disconnectDatabase(pendingDisconnect.id);
      if (activeId === pendingDisconnect.id) {
        setSchema(null);
        setSchemaStatus('idle');
        setQueryHistory([]);
        setQueryHistoryStatus('idle');
      }
      setPendingDisconnect(null);
      await fetchConnections();
    } catch (err) {
      setDisconnectError(stableMessage(err, 'Connection could not be disconnected.'));
    } finally {
      setDisconnecting(false);
    }
  };

  const handleConnectionAdded = async () => {
    setIsModalOpen(false);
    await fetchConnections();
  };

  const activeConnection = connections.find(c => c.id === activeId) || null;
  const pageBadge = useMemo(() => {
    if (!activeConnection) {
      const idleText = connectionStatus === 'loading' ? 'Loading' : 'Idle';
      return {
        text: idleText,
        color: T.accent,
        icon: <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.accent }} />,
      };
    }

    const color = activeConnection.status === 'live'
      ? T.green
      : activeConnection.status === 'offline'
        ? T.red
        : T.yellow;

    return {
      text: activeConnection.health_state.toUpperCase(),
      color,
      icon: <div style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />,
    };
  }, [activeConnection, connectionStatus]);

  return (
    <MainShell
      title="Connection Ledger"
      subtitle="Source distribution and technical bridge telemetry"
      badge={pageBadge}
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
          <HeaderIcons.Plus width={14} height={14} strokeWidth={3} /> <span className="header-action-label">New Connection</span>
        </button>
      }
    >
      <div className="responsive-split responsive-split-stack-detail">
        <ConnectionListPanel
          connections={connections}
          activeId={activeId}
          status={connectionStatus}
          error={connectionError}
          onSelect={setActiveId}
          onAdd={() => setIsModalOpen(true)}
          onRetry={fetchConnections}
        />
        <ConnectionDetail
          connection={activeConnection}
          schema={schema}
          schemaState={schemaStatus}
          schemaError={schemaError}
          queryHistory={queryHistory}
          queryHistoryState={queryHistoryStatus}
          queryHistoryError={queryHistoryError}
          onDelete={handleRequestDelete}
          onRefreshSchema={handleRefreshSchema}
          onConnectionUpdated={fetchConnections}
        />
      </div>

      <NewConnectionWizard
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSaved={handleConnectionAdded}
      />
      <DisconnectConnectionModal
        connection={pendingDisconnect}
        isDisconnecting={disconnecting}
        error={disconnectError}
        onCancel={() => {
          if (!disconnecting) setPendingDisconnect(null);
        }}
        onConfirm={handleConfirmDisconnect}
      />
    </MainShell>
  );
}
