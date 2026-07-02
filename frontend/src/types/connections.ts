import type { ConnectionHealthState, DatabaseConnection, QueryRecord, SchemaResponse } from './api';

export type ConnectionStatus = 'live' | 'offline' | 'warning';
export type LoadState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';

export interface ConnectionListItem {
  id: string;
  name: string;
  type: string;
  version?: string;
  status: ConnectionStatus;
  health_state: ConnectionHealthState;
  latency?: number | null;
  queries: number;
  icon: string;
  color: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  tables_count?: number;
  ssl_mode?: string;
  readonly?: boolean;
  use_ssh?: boolean;
  ssh_host?: string;
  last_tested_at?: string | null;
  last_status?: 'unknown' | 'healthy' | 'failed' | string;
  last_error?: string | null;
  last_schema_sync_at?: string | null;
}

export interface ConnectionDetailData {
  connection: ConnectionListItem | null;
  schema?: SchemaResponse | null;
  schemaState?: LoadState;
  schemaError?: string | null;
  queryHistory?: QueryRecord[];
  queryHistoryState?: LoadState;
  queryHistoryError?: string | null;
  onDelete?: (id: string) => void;
  onRefreshSchema?: () => Promise<void> | void;
  onConnectionUpdated?: () => Promise<void> | void;
}

export type ConnectionApiRecord = DatabaseConnection;

export interface ConnectionDetailProps extends ConnectionDetailData {}

export type ConnectionDetailTab = 'overview' | 'credentials' | 'schema' | 'security' | 'activity';
