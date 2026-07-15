import type { SemanticLineageItem } from './semantics';

export interface ApiMessageResponse {
  message: string;
  status?: string | null;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Array<Record<string, unknown>>;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export interface AuthCredentialsRequest {
  email: string;
  password: string;
}

export interface AuthUserResponse {
  id: string;
  email?: string | null;
}

export interface AuthSessionResponse {
  authenticated: boolean;
  user: AuthUserResponse | null;
  message?: string | null;
}
export interface ChartRecommendation {
  type: 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'table' | 'kpi';
  x_column: string;
  y_columns: string[];
  color_column?: string | null;
  tooltip_columns?: string[];
  is_grouped?: boolean;
  is_dual_axis?: boolean;
  title: string;
  x_label: string;
  y_label: string;
}

export type SupportedDatabaseType = 'postgresql';
export type ConnectionHealthState = 'live' | 'failed' | 'stale' | 'unknown';

export interface DatabaseConnection {
  id: string;
  name: string;
  db_type: string;
  database: string;
  host?: string | null;
  port?: number | null;
  username?: string | null;
  status: 'live' | 'offline' | 'warning' | string;
  health_state: ConnectionHealthState;
  tables_count: number;
  ssl_mode?: string;
  readonly?: boolean;
  use_ssh?: boolean;
  ssh_host?: string | null;
  last_tested_at?: string | null;
  last_status?: 'unknown' | 'healthy' | 'failed' | string;
  last_error?: string | null;
  latency_ms?: number | null;
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

export interface ConnectDatabaseRequest {
  name?: string;
  input_mode?: 'fields' | 'uri';
  connection_uri?: string | null;
  db_type: SupportedDatabaseType;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  ssl_mode?: string;
  // SSH Tunnel
  use_ssh?: boolean;
  ssh_host?: string;
  ssh_port?: number;
  ssh_username?: string;
  ssh_password?: string;
  ssh_private_key?: string;
  ssl_root_certificate?: string;
  ssl_client_certificate?: string;
  ssl_client_private_key?: string;
  scope_mode?: 'all' | 'allowlist';
  included_schemas?: string[];
  included_tables?: string[];
}

export interface ConnectDatabaseResponse extends DatabaseConnection {
  message: string;
}

export interface TestConnectionRequest {
  input_mode?: 'fields' | 'uri';
  connection_uri?: string | null;
  db_type: SupportedDatabaseType;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  ssl_mode?: string;
  // SSH Tunnel
  use_ssh?: boolean;
  ssh_host?: string;
  ssh_port?: number;
  ssh_username?: string;
  ssh_password?: string;
  ssh_private_key?: string;
  ssl_root_certificate?: string;
  ssl_client_certificate?: string;
  ssl_client_private_key?: string;
}

export interface ConnectionDiagnosticCheck {
  code: string;
  status: 'pending' | 'passed' | 'warning' | 'failed' | 'skipped';
  label: string;
  message?: string | null;
}

export interface ConnectionInventorySchema { name: string; tables: string[] }

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  tables_found?: number | null;
  latency_ms?: number | null;
  diagnostic_id?: string | null;
  code: string;
  category: string;
  suggestions: string[];
  checks: ConnectionDiagnosticCheck[];
  warnings: Array<{ code: string; message: string }>;
  inventory?: ConnectionInventorySchema[] | null;
  inventory_truncated: boolean;
  server_version?: string | null;
  role_has_write_privileges?: boolean | null;
}

export interface ConnectionScope {
  connection_id?: string;
  mode: 'all' | 'allowlist';
  included_schemas: string[];
  included_tables: string[];
  revision?: number;
  updated_at?: string | null;
}

export interface ConnectionScopeImpact {
  code: string;
  consumer_type: string;
  consumer_id: string;
  label: string;
}

export interface ConnectionScopePreview {
  valid: boolean;
  normalized_scope: ConnectionScope;
  errors: Array<{ code: string; message: string }>;
  warnings: Array<{ code: string; message: string }>;
  impacts: ConnectionScopeImpact[];
}

export interface ConnectionAutomation {
  connection_id?: string;
  health_check_enabled: boolean;
  health_check_interval_minutes: 15 | 60 | 360 | 1440;
  next_health_check_at?: string | null;
  schema_refresh_enabled: boolean;
  schema_refresh_interval_hours: 6 | 12 | 24 | 168;
  next_schema_refresh_at?: string | null;
}

export interface ConnectionHealthEvent {
  id: string;
  source: string;
  status: 'healthy' | 'failed';
  diagnostic_code?: string | null;
  message?: string | null;
  latency_ms?: number | null;
  created_at: string;
}

export interface ConnectionHealthHistory {
  connection_id: string;
  items: ConnectionHealthEvent[];
  next_cursor?: string | null;
  success_rate_24h: number;
  success_rate_7d: number;
  p50_latency_ms?: number | null;
  p95_latency_ms?: number | null;
  last_successful_schema_refresh_at?: string | null;
  next_health_check_at?: string | null;
  next_schema_refresh_at?: string | null;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface SchemaForeignKey {
  column: string;
  referred_table: string;
  referred_column: string;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
  foreign_keys: SchemaForeignKey[];
  row_count?: number | null;
}

export interface SchemaResponse {
  connection_id: string;
  database: string;
  tables: SchemaTable[];
}

export interface ChatRequest {
  connection_id: string;
  session_id?: string;
  message: string;
}

export type ChatRunStatus = 'queued' | 'running' | 'cancel_requested' | 'completed' | 'failed' | 'cancelled';

export interface ChatRunRequest extends ChatRequest {
  client_request_id: string;
}

export interface ChatRunAccepted {
  run_id: string;
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  status: ChatRunStatus;
  events_url: string;
}

export interface ChatRunEvent {
  version?: number;
  run_id: string;
  sequence?: number;
  type: string;
  label?: string;
  occurred_at?: string;
  stage?: string;
  duration_ms?: number;
  outcome?: string;
  retry_count?: number;
  metadata?: { row_count?: number; message_id?: string; reason?: string };
}

export interface ChatRunSnapshot {
  run_id: string;
  session_id: string;
  user_message_id: string;
  assistant_message_id?: string | null;
  status: ChatRunStatus;
  current_stage: string;
  current_stage_label: string;
  failure_code?: string | null;
  failure_message?: string | null;
  created_at: string;
  started_at?: string | null;
  heartbeat_at?: string | null;
  cancel_requested_at?: string | null;
  finished_at?: string | null;
  response?: ChatResponse | null;
}

export interface ChatMessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  connection_id?: string | null;
  sql?: string | null;
  columns?: string[] | null;
  results?: { 
    columns?: string[];
    rows?: Array<Record<string, unknown>>;
    row_count?: number | null;
    truncated?: boolean | null;
    execution_time_ms?: number | null;
  } | null;
  rows?: Array<Record<string, unknown>> | null;
  row_count?: number | null;
  truncated?: boolean | null;
  execution_time_ms?: number | null;
  column_metadata?: Record<string, string> | null;
  chart_recommendation?: ChartRecommendation | null;
  error?: string | null;
  is_pinned?: boolean;
  parent_id?: string | null;
  prev_query_id?: string | null;
  agent_trace?: Array<{
    tool: string;
    args_summary: string;
    duration_ms: number;
    outcome: string;
    output_summary?: string;
    output_row_count?: number;
    error_class?: string;
    retry_count?: number;
  }> | null;
  agent_tier?: string | null;
  agent_run_id?: string | null;
  agent_run_status?: ChatRunStatus | null;
  agent_run_stage?: string | null;
  agent_run_stage_label?: string | null;
  semantic_lineage?: SemanticLineageItem[];
  response_kind?: 'answer' | 'clarification' | null;
  clarification_context?: { reason_code: string; expected_input: string } | null;
  timestamp: string;
}

export interface SessionSummary {
  id: string;
  connection_ids: string[];
  last_connection_id: string | null;
  title: string | null;
  message_count: number;
  created_at: string;
}

export interface SessionMessagesResponse {
  session_id: string;
  connection_ids: string[];
  last_connection_id: string | null;
  messages: ChatMessageRecord[];
}

export interface UpdateSessionRequest {
  title?: string;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  user_message_id: string;
  message: string;
  sql?: string | null;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated: boolean;
  execution_time_ms: number;
  chart_recommendation?: ChartRecommendation | null;
  error?: string | null;
  normalized: boolean;
  column_metadata?: Record<string, string>;
  xLabel?: string;
  yLabel?: string;
  is_pinned?: boolean;
  prev_query_id?: string | null;
  agent_trace?: Array<{
    tool: string;
    args_summary: string;
    duration_ms: number;
    outcome: string;
    output_summary?: string;
    output_row_count?: number;
    error_class?: string;
    retry_count?: number;
  }> | null;
  agent_tier?: string | null;
  semantic_lineage?: SemanticLineageItem[];
  response_kind?: 'answer' | 'clarification';
  clarification_context?: { reason_code: string; expected_input: string } | null;
}

export interface ChatUiMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  row_count?: number;
  truncated?: boolean;
  execution_time_ms?: number;
  chart_recommendation?: ChartRecommendation;
  error?: string;
  column_metadata?: Record<string, string>;
  is_pinned?: boolean;
  parent_id?: string;
  prev_query_id?: string;
}

export interface EditSqlRequest {
  sql: string;
  connection_id: string;
}

export interface QueryRecord {
  id: string;
  connection_id: string;
  sql: string;
  success: boolean;
  error?: string | null;
  execution_time_ms?: number | null;
  row_count?: number | null;
  timestamp: string;
}

export interface QueryStats {
  total: number;
  successful: number;
  failed: number;
  avg_time_ms: number;
}

export interface ScheduleConfig {
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'monthly';
  day_of_week: string | null;
  day_of_month: number | null;
  hour: number;
  minute: number;
  timezone: string;
  next_run_at: string | null;
}

export interface ScheduleStatusResponse {
  query_id: string;
  schedule: ScheduleConfig | null;
  schedule_label: string | null;
  message: string;
}

export interface SavedQuery {
  id: string;
  title: string;
  sql: string;
  description: string;
  folder_name: string;
  connection_id: string | null;
  icon: string;
  icon_bg: string;
  tags: string[];
  schedule: ScheduleConfig | null;
  schedule_label: string | null;
  created_at: string;
  updated_at: string;
  run_count: number;
  last_run_at: string | null;
}

export interface SaveQueryRequest {
  title: string;
  sql: string;
  description?: string;
  folder_name?: string;
  connection_id?: string;
  icon?: string;
  icon_bg?: string;
  tags?: string[];
  schedule?: ScheduleConfig;
}

export interface SaveQueryResponse extends SavedQuery {
  created: boolean;
}

export type UpdateSavedQueryRequest = Partial<SaveQueryRequest>;

export interface RunSavedQueryResponse {
  query_id: string;
  success: boolean;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  execution_time_ms: number;
  error?: string | null;
  error_code?: string | null;
}

export interface QueryRunHistoryRecord {
  id: string;
  query_id: string;
  success: boolean;
  row_count: number;
  execution_time_ms: number;
  error?: string | null;
  triggered_by: 'manual' | 'schedule';
  ran_at: string;
}

export interface FolderSummary {
  name: string;
  count: number;
}

export interface LibraryStats {
  total_queries: number;
  scheduled: number;
  total_runs: number;
  recently_run: number;
  folders: number;
}

export interface PublicTemplate {
  id: string;
  connection_id: string;
  title: string;
  description: string;
  sql: string;
  category: string;
  category_color: string;
  tags: string[];
  icon: string;
  icon_bg: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
}

export interface PublicTemplatesResponse {
  status: 'not_started' | 'generating' | 'ready' | 'error';
  connection_id: string | null;
  templates: PublicTemplate[];
}

export interface CreateDashboardRequest {
  name: string;
  icon?: string;
}

export type DashboardCreationMode = 'manual' | 'ai';
export type DashboardLifecycleStatus = 'draft' | 'ready';
export type WidgetGenerationStatus =
  | 'ready'
  | 'queued'
  | 'running'
  | 'failed'
  | 'cancelled'
  | 'regenerating';
export type WidgetSourceType = 'manual' | 'chat' | 'ai';

export interface DashboardSummary {
  id: string;
  owner_id?: string;
  name: string;
  icon: string;
  filters: Record<string, unknown>;
  is_public?: boolean;
  share_token?: string | null;
  creation_mode?: DashboardCreationMode;
  lifecycle_status?: DashboardLifecycleStatus;
  created_at: string;
  widget_count: number;
}

export interface UpdateDashboardRequest {
  name?: string;
  icon?: string;
  filters?: Record<string, unknown>;
  is_public?: boolean;
  lifecycle_status?: DashboardLifecycleStatus;
}

export interface DashboardChartConfig {
  x_column?: string;
  y_columns?: string[];
  color_column?: string | null;
  is_grouped?: boolean;
  title?: string;
  x_label?: string;
  y_label?: string;
}

export interface DashboardWidget {
  id: string;
  dashboard_id: string;
  title: string;
  viz_type: string;
  size: string;
  connection_id?: string | null;
  sql?: string | null;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  chart_config?: DashboardChartConfig | null;
  cadence: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW: number;
  minH: number;
  bar_orientation: 'horizontal' | 'vertical';
  order_index: number;
  source_type?: WidgetSourceType;
  source_prompt?: string | null;
  generation_item_id?: string | null;
  generation_status?: WidgetGenerationStatus;
  generation_error?: string | null;
  assumptions?: string[];
  semantic_lineage?: SemanticLineageItem[];
  created_at: string;
}

export interface AddDashboardWidgetRequest {
  dashboard_id: string;
  title: string;
  viz_type: string;
  size: string;
  connection_id?: string;
  sql?: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  chart_config?: DashboardChartConfig;
  cadence?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  minW?: number;
  minH?: number;
  bar_orientation?: 'horizontal' | 'vertical';
  order_index?: number;
}

export interface UpdateDashboardWidgetRequest {
  title?: string;
  size?: string;
  viz_type?: string;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  minW?: number;
  minH?: number;
  bar_orientation?: 'horizontal' | 'vertical';
  order_index?: number;
}

export interface DashboardStats {
  total_widgets: number;
  viz_breakdown: Record<string, number>;
}

/* ── AI dashboard generation ─────────────────────────────────── */

export type DashboardGenerationRunStatus =
  | 'planning'
  | 'awaiting_approval'
  | 'queued'
  | 'running'
  | 'partial'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type DashboardPlanVisualization =
  | 'auto'
  | 'kpi'
  | 'bar'
  | 'line'
  | 'area'
  | 'pie'
  | 'donut'
  | 'table';

export type DashboardPlanSize = 'quarter' | 'half' | 'three-quarter' | 'full';

export interface WidgetPlan {
  client_key: string;
  title: string;
  question: string;
  purpose?: string;
  visualization: DashboardPlanVisualization;
  size: DashboardPlanSize;
  time_range?: string | null;
  semantic_refs?: string[];
}

export interface DashboardPlan {
  version: 1;
  title: string;
  description?: string;
  assumptions?: string[];
  warnings?: string[];
  widgets: WidgetPlan[];
}

export interface CreateDashboardGenerationRequest {
  connection_id: string;
  prompt: string;
  requested_widget_count?: number;
  default_time_range?: string | null;
  extra_instructions?: string | null;
  client_request_id: string;
}

export interface CreateDashboardGenerationResponse {
  run_id: string;
  status: string;
  events_url: string;
}

export interface UpdateDashboardPlanRequest {
  expected_revision: number;
  plan: DashboardPlan;
}

export interface ApproveDashboardPlanRequest {
  expected_revision: number;
}

export interface ApproveDashboardPlanResponse {
  run_id: string;
  dashboard_id?: string | null;
  status: string;
  events_url?: string | null;
}

export interface RegenerateWidgetRequest {
  instruction?: string | null;
  use_latest_definitions?: boolean;
}

export interface DashboardGenerationItem {
  id: string;
  run_id: string;
  client_key: string;
  dashboard_widget_id?: string | null;
  order_index: number;
  plan_json: Record<string, unknown>;
  status: string;
  attempt_count: number;
  last_error_code?: string | null;
  last_error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DashboardGenerationRun {
  id: string;
  owner_id: string;
  connection_id: string;
  dashboard_id?: string | null;
  client_request_id: string;
  prompt: string;
  requested_widget_count: number;
  default_time_range?: string | null;
  extra_instructions?: string | null;
  plan_json?: DashboardPlan | null;
  semantic_context_json?: Record<string, unknown> | null;
  plan_revision: number;
  status: DashboardGenerationRunStatus | string;
  current_stage: string;
  current_stage_label: string;
  celery_task_id?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  items: DashboardGenerationItem[];
  events_url?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  heartbeat_at?: string | null;
  cancel_requested_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
}

export interface DashboardGenerationEvent {
  version?: number;
  run_id: string;
  sequence?: number;
  type: string;
  label?: string;
  occurred_at?: string;
  stage?: string;
  duration_ms?: number;
  outcome?: string;
  retry_count?: number;
  metadata?: {
    dashboard_id?: string;
    item_id?: string;
    widget_id?: string;
    plan_revision?: number;
    reason?: string;
    failure_code?: string;
  };
}

export interface AnalyticsOverview {
  active_connections: number;
  total_queries: number;
  successful_queries: number;
  failed_queries: number;
  success_rate: number;
  avg_time_ms: number;
  saved_queries: number;
  scheduled_queries: number;
  dashboards: number;
  total_widgets: number;
}

export interface AnalyticsTopConnection {
  connection_id: string;
  name: string;
  database: string;
  db_type: string;
  query_count: number;
}

export interface AnalyticsRecentQuery {
  id: string;
  connection_id: string;
  connection_name: string;
  sql: string;
  success: boolean;
  error?: string | null;
  execution_time_ms?: number | null;
  row_count?: number | null;
  timestamp: string;
}

export interface AnalyticsDashboardSummary {
  id: string;
  name: string;
  icon: string;
  created_at: string;
  widget_count: number;
}

export interface AnalyticsDashboardSection {
  total_dashboards: number;
  total_widgets: number;
  viz_breakdown: Record<string, number>;
  items: AnalyticsDashboardSummary[];
}

export interface AnalyticsQueryHealth {
  successful: number;
  failed: number;
}

export interface AnalyticsOverviewResponse {
  overview: AnalyticsOverview;
  library: LibraryStats;
  dashboards: AnalyticsDashboardSection;
  query_health: AnalyticsQueryHealth;
  top_connections: AnalyticsTopConnection[];
  recent_queries: AnalyticsRecentQuery[];
}
