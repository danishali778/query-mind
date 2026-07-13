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
  credential_revision: number;
  credentials_updated_at?: string | null;
  has_ssl_root_certificate: boolean;
  has_ssl_client_certificate: boolean;
  has_ssl_client_private_key: boolean;
  scope_mode: 'all' | 'allowlist';
  included_schemas: string[];
  included_tables: string[];
  scope_revision: number;
  scope_updated_at?: string | null;
  health_check_enabled: boolean;
  health_check_interval_minutes: 15 | 60 | 360 | 1440;
  next_health_check_at?: string | null;
  schema_refresh_enabled: boolean;
  schema_refresh_interval_hours: 6 | 12 | 24 | 168;
  next_schema_refresh_at?: string | null;
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

export type ConnectionDetailProps = ConnectionDetailData;

export type ConnectionDetailTab = 'overview' | 'credentials' | 'schema' | 'semantics' | 'security' | 'activity';
