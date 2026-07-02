import type { ConnectionApiRecord, ConnectionListItem } from '../types/connections';

const DB_ICONS: Record<string, { icon: string; color: string }> = {
  postgresql: { icon: 'PG', color: 'rgba(51,103,145,0.2)' },
};

function deriveStatus(apiConn: ConnectionApiRecord): ConnectionListItem['status'] {
  if (apiConn.status === 'live' || apiConn.status === 'offline' || apiConn.status === 'warning') {
    return apiConn.status;
  }
  if (apiConn.health_state === 'failed') {
    return 'offline';
  }
  if (apiConn.health_state === 'live') {
    return 'live';
  }
  return 'warning';
}

export function mapConnectionRecord(apiConn: ConnectionApiRecord): ConnectionListItem {
  const dbType = apiConn.db_type.toLowerCase();
  const iconInfo = DB_ICONS[dbType] || { icon: 'UN', color: 'rgba(100,100,100,0.15)' };

  return {
    id: apiConn.id,
    name: apiConn.name || apiConn.database,
    type: apiConn.db_type,
    status: deriveStatus(apiConn),
    health_state: apiConn.health_state || 'unknown',
    queries: 0,
    latency: apiConn.latency_ms ?? null,
    icon: iconInfo.icon,
    color: iconInfo.color,
    host: apiConn.host ?? undefined,
    port: apiConn.port ?? undefined,
    database: apiConn.database,
    username: apiConn.username ?? undefined,
    tables_count: apiConn.tables_count,
    ssl_mode: apiConn.ssl_mode ?? 'disable',
    readonly: apiConn.readonly ?? true,
    use_ssh: apiConn.use_ssh ?? false,
    ssh_host: apiConn.ssh_host ?? undefined,
    last_tested_at: apiConn.last_tested_at ?? null,
    last_status: apiConn.last_status ?? 'unknown',
    last_error: apiConn.last_error ?? null,
    last_schema_sync_at: apiConn.last_schema_sync_at ?? null,
  };
}
