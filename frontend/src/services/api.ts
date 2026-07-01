import { jsonRequest, request } from './http';
import type {
  AddDashboardWidgetRequest,
  AnalyticsOverviewResponse,
  ApiMessageResponse,
  ChatRequest,
  ChatResponse,
  ConnectDatabaseRequest,
  ConnectDatabaseResponse,
  CreateDashboardRequest,
  DashboardStats,
  DashboardSummary,
  DashboardWidget,
  DatabaseConnection,
  FolderSummary,
  LibraryStats,
  PublicTemplatesResponse,
  QueryRecord,
  QueryRunHistoryRecord,
  QueryStats,
  RunSavedQueryResponse,
  SaveQueryRequest,
  SaveQueryResponse,
  SavedQuery,
  ScheduleConfig,
  ScheduleStatusResponse,
  SchemaResponse,
  SessionMessagesResponse,
  SessionSummary,
  TestConnectionRequest,
  TestConnectionResponse,
  UpdateDashboardWidgetRequest,
  UpdateDashboardRequest,
  UpdateSavedQueryRequest,
  EditSqlRequest,
  ChatMessageRecord,
} from '../types/api';

export function editSql(sessionId: string, messageId: string, data: EditSqlRequest) {
  return jsonRequest<ChatMessageRecord>(`/chat/${sessionId}/message/${messageId}/edit-sql`, 'POST', data);
}

export function toggleMessagePin(sessionId: string, messageId: string, isPinned: boolean) {
  return request<ApiMessageResponse>(`/chat/${sessionId}/message/${messageId}/pin?is_pinned=${isPinned}`, { method: 'POST' });
}

export function connectDatabase(config: ConnectDatabaseRequest) {
  return jsonRequest<ConnectDatabaseResponse>('/database/connect', 'POST', config);
}

export function testConnection(config: TestConnectionRequest) {
  return jsonRequest<TestConnectionResponse>('/database/test', 'POST', config);
}

export function listConnections() {
  return request<DatabaseConnection[]>('/database/connections');
}

export function disconnectDatabase(connectionId: string) {
  return request<ApiMessageResponse>(`/database/connections/${connectionId}`, { method: 'DELETE' });
}

export function updateConnectionSettings(connectionId: string, data: { ssl_mode?: string }) {
  return jsonRequest<DatabaseConnection>(`/database/connections/${connectionId}`, 'PATCH', data);
}

export function sendMessage(data: ChatRequest) {
  return jsonRequest<ChatResponse>('/chat', 'POST', data);
}

export function listSessions() {
  return request<SessionSummary[]>('/chat/sessions');
}

export function getSessionMessages(sessionId: string) {
  return request<SessionMessagesResponse>(`/chat/sessions/${sessionId}/messages`);
}

export function deleteSession(sessionId: string) {
  return request<ApiMessageResponse>(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

export function createSession(connectionId?: string) {
  const params = connectionId ? `?connection_id=${connectionId}` : '';
  return request<SessionSummary>(`/chat/sessions${params}`, { method: 'POST' });
}

export function renameSession(sessionId: string, title: string) {
  return jsonRequest<SessionSummary>(`/chat/sessions/${sessionId}`, 'PATCH', { title });
}

export function getSchema(connectionId: string) {
  return request<SchemaResponse>(`/database/connections/${connectionId}/schema`);
}

export async function getQueryHistory(connectionId?: string, limit: number = 20) {
  const params = new URLSearchParams();
  if (connectionId) params.set('connection_id', connectionId);
  params.set('limit', String(limit));
  return request<QueryRecord[]>(`/query-history?${params.toString()}`);
}

export function getQueryStats(connectionId: string) {
  return request<QueryStats>(`/query-history/stats?connection_id=${connectionId}`);
}

export async function listSavedQueries(folder?: string, tag?: string, connectionId?: string) {
  const params = new URLSearchParams();
  if (folder) params.set('folder', folder);
  if (tag) params.set('tag', tag);
  if (connectionId) params.set('connection_id', connectionId);
  return request<SavedQuery[]>(`/library/queries?${params.toString()}`);
}

export function saveQuery(data: SaveQueryRequest) {
  return jsonRequest<SaveQueryResponse>('/library/queries', 'POST', data);
}

export function getSavedQuery(queryId: string) {
  return request<SavedQuery>(`/library/queries/${queryId}`);
}

export function updateSavedQuery(queryId: string, data: UpdateSavedQueryRequest) {
  return jsonRequest<SavedQuery>(`/library/queries/${queryId}`, 'PUT', data);
}

export function deleteSavedQuery(queryId: string) {
  return request<ApiMessageResponse>(`/library/queries/${queryId}`, { method: 'DELETE' });
}

export function runSavedQuery(queryId: string) {
  return request<RunSavedQueryResponse>(`/library/queries/${queryId}/run`, { method: 'POST' });
}

export function getQueryRunHistory(queryId: string, limit: number = 20) {
  return request<QueryRunHistoryRecord[]>(`/library/queries/${queryId}/runs?limit=${limit}`);
}

export function getQuerySchedule(queryId: string) {
  return request<ScheduleStatusResponse>(`/library/queries/${queryId}/schedule`);
}

export function setQuerySchedule(queryId: string, config: ScheduleConfig) {
  return jsonRequest<ScheduleStatusResponse>(`/library/queries/${queryId}/schedule`, 'PUT', config);
}

export function removeQuerySchedule(queryId: string) {
  return request<ScheduleStatusResponse>(`/library/queries/${queryId}/schedule`, { method: 'DELETE' });
}

export function listLibraryFolders() {
  return request<FolderSummary[]>('/library/folders');
}

export function createLibraryFolder(name: string) {
  return request<{ name: string }>('/library/folders', { method: 'POST', body: JSON.stringify({ name }) });
}

export function listLibraryTags() {
  return request<string[]>('/library/tags');
}

export function getLibraryStats() {
  return request<LibraryStats>('/library/stats');
}

export function listPublicTemplates(connectionId?: string) {
  const params = connectionId ? `?connection_id=${encodeURIComponent(connectionId)}` : '';
  return request<PublicTemplatesResponse>(`/library/public${params}`);
}

export function triggerTemplateGeneration(connectionId: string) {
  return jsonRequest<{ message: string; connection_id: string }>(
    `/library/public/generate?connection_id=${encodeURIComponent(connectionId)}`,
    'POST',
    {}
  );
}

export function cloneTemplate(templateId: string, connectionId?: string) {
  const params = connectionId ? `?connection_id=${encodeURIComponent(connectionId)}` : '';
  return jsonRequest<SaveQueryResponse>(`/library/public/${templateId}/clone${params}`, 'POST', {});
}

export function listDashboards() {
  return request<DashboardSummary[]>('/dashboard/dashboards');
}

export function createDashboard(data: CreateDashboardRequest) {
  return jsonRequest<Omit<DashboardSummary, 'widget_count'>>('/dashboard/dashboards', 'POST', data);
}

export function deleteDashboard(dashboardId: string) {
  return request<ApiMessageResponse>(`/dashboard/dashboards/${dashboardId}`, { method: 'DELETE' });
}

export function renameDashboard(dashboardId: string, name: string) {
  return jsonRequest<DashboardSummary>(`/dashboard/dashboards/${dashboardId}`, 'PATCH', { name });
}

export function updateDashboard(dashboardId: string, data: UpdateDashboardRequest) {
  return jsonRequest<DashboardSummary>(`/dashboard/dashboards/${dashboardId}/update`, 'PATCH', data);
}

export function refreshDashboardWidget(widgetId: string) {
  return request<DashboardWidget>(`/dashboard/widgets/${widgetId}/refresh`, { method: 'POST' });
}

export function listDashboardWidgets(dashboardId?: string) {
  const params = dashboardId ? `?dashboard_id=${dashboardId}` : '';
  return request<DashboardWidget[]>(`/dashboard/widgets${params}`);
}

export function addDashboardWidget(data: AddDashboardWidgetRequest) {
  return jsonRequest<DashboardWidget>('/dashboard/widgets', 'POST', data);
}

export function deleteDashboardWidget(widgetId: string) {
  return request<ApiMessageResponse>(`/dashboard/widgets/${widgetId}`, { method: 'DELETE' });
}

export function updateDashboardWidget(widgetId: string, data: UpdateDashboardWidgetRequest) {
  return jsonRequest<DashboardWidget>(`/dashboard/widgets/${widgetId}`, 'PATCH', data);
}

export function getWidgetInsight(widgetId: string) {
  return request<{ insight: string }>(`/dashboard/widgets/${widgetId}/insight`, { method: 'POST' });
}

export function getDashboardStats(dashboardId?: string) {
  const params = dashboardId ? `?dashboard_id=${dashboardId}` : '';
  return request<DashboardStats>(`/dashboard/stats${params}`);
}

export function getSharedDashboard(token: string) {
  return request<DashboardSummary>(`/dashboard/shared/${token}`);
}

export function getSharedDashboardWidgets(token: string) {
  return request<DashboardWidget[]>(`/dashboard/shared/${token}/widgets`);
}

export function getAnalyticsOverview() {
  return request<AnalyticsOverviewResponse>('/analytics/overview');
}

// --- Settings ---

export interface UserSettings {
  full_name: string | null;
  job_title: string | null;
  timezone: string;
  theme: string;
  accent_color: string;
  density: string;
  show_run_counts: boolean;
  animate_charts: boolean;
  syntax_highlighting: boolean;
  ai_model: string;
  stream_responses: boolean;
  default_row_limit: number;
  auto_save_queries: boolean;
  system_prompt: string;
  email_scheduled: boolean;
  email_failed: boolean;
  email_alerts: boolean;
  delivery_format: string;
  slack_enabled: boolean;
  slack_webhook: string | null;
  slack_channel: string | null;
  owner_id: string;
}

export function getSettings() {
  return request<UserSettings>('/settings');
}

export function updateSettings(data: Partial<UserSettings>) {
  return jsonRequest<UserSettings>('/settings', 'PUT', data);
}

// --- Billing ---

export interface UserSubscription {
  owner_id: string;
  plan_type: string;
  queries_used: number;
  queries_limit: number;
  ai_used: number;
  ai_limit: number;
  next_reset_date: string;
}

export function getBillingInfo() {
  return request<UserSubscription>('/settings/billing');
}

export function upgradePlan() {
  return request<UserSubscription>('/settings/billing/upgrade', { method: 'POST' });
}
