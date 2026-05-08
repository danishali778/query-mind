import type { ConnectionApiRecord, ConnectionListItem } from '../types/connections';

const DB_ICONS: Record<string, { icon: string; color: string }> = {
  postgresql: { icon: '🐘', color: 'rgba(51,103,145,0.2)' },
  mysql: { icon: '🐬', color: 'rgba(0,117,143,0.15)' },
  sqlite: { icon: '🔵', color: 'rgba(59,130,246,0.15)' },
  bigquery: { icon: '🔶', color: 'rgba(255,153,0,0.15)' },
  snowflake: { icon: '❄️', color: 'rgba(41,182,246,0.15)' },
  redshift: { icon: '🟠', color: 'rgba(255,107,53,0.15)' },
};

export function mapConnectionRecord(apiConn: ConnectionApiRecord): ConnectionListItem {
  const dbType = apiConn.db_type.toLowerCase();
  const iconInfo = DB_ICONS[dbType] || { icon: '🗄️', color: 'rgba(100,100,100,0.15)' };

  return {
    id: apiConn.id,
    name: apiConn.name || apiConn.database,
    type: apiConn.db_type,
    status: apiConn.status === 'connected' ? 'live' : 'offline',
    queries: 0,
    latency: 0,
    icon: iconInfo.icon,
    color: iconInfo.color,
    host: apiConn.host ?? undefined,
    port: apiConn.port ?? undefined,
    database: apiConn.database,
    username: apiConn.username ?? undefined,
    tables_count: apiConn.tables_count,
    ssl_mode: apiConn.ssl_mode ?? 'disable',
    readonly: apiConn.readonly ?? true,
  };
}
