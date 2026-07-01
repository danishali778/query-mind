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

export interface DatabaseConnection {
  id: string;
  name: string;
  db_type: string;
  database: string;
  host: string;
  port?: number | null;
  username?: string | null;
  status: string;
  tables_count: number;
  ssl_mode?: string;
  readonly?: boolean;
}

export interface ConnectDatabaseRequest {
  name?: string;
  db_type: string;
  host: string;
  port?: number;
  database: string;
  username: string;
  password: string;
  ssl_mode?: string;
  // SSH Tunnel
  use_ssh?: boolean;
  ssh_host?: string;
  ssh_port?: number;
  ssh_username?: string;
  ssh_password?: string;
  ssh_private_key?: string;
}

export interface ConnectDatabaseResponse extends DatabaseConnection {
  message: string;
}

export interface TestConnectionRequest {
  db_type: string;
  host: string;
  port?: number;
  database: string;
  username: string;
  password?: string;
  ssl_mode?: string;
  // SSH Tunnel
  use_ssh?: boolean;
  ssh_host?: string;
  ssh_port?: number;
  ssh_username?: string;
  ssh_password?: string;
  ssh_private_key?: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  tables_found?: number | null;
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
    execution_time_ms?: number | null;
  } | null;
  rows?: Array<Record<string, unknown>> | null;
  row_count?: number | null;
  execution_time_ms?: number | null;
  column_metadata?: Record<string, string> | null;
  chart_recommendation?: ChartRecommendation | null;
  error?: string | null;
  is_pinned?: boolean;
  parent_id?: string | null;
  prev_query_id?: string | null;
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
  execution_time_ms: number;
  chart_recommendation?: ChartRecommendation | null;
  error?: string | null;
  normalized: boolean;
  column_metadata?: Record<string, string>;
  xLabel?: string;
  yLabel?: string;
  is_pinned?: boolean;
  prev_query_id?: string | null;
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

export interface UpdateSavedQueryRequest extends Partial<SaveQueryRequest> {}

export interface RunSavedQueryResponse {
  query_id: string;
  success: boolean;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  execution_time_ms: number;
  error?: string | null;
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

export interface DashboardSummary {
  id: string;
  owner_id?: string;
  name: string;
  icon: string;
  filters: Record<string, any>;
  is_public?: boolean;
  share_token?: string | null;
  created_at: string;
  widget_count: number;
}

export interface UpdateDashboardRequest {
  name?: string;
  icon?: string;
  filters?: Record<string, any>;
  is_public?: boolean;
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
