import type { ChartRecommendation, ChatRunEvent, ChatRunStatus, DatabaseConnection, SessionSummary } from './api';
import type { SemanticLineageItem } from './semantics';

export interface ChatMessageView {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  row_count?: number;
  truncated?: boolean;
  execution_time_ms?: number;
  chart_recommendation?: ChartRecommendation;
  column_metadata?: Record<string, string>;
  error?: string;
  is_pinned?: boolean;
  parent_id?: string;
  prev_query_id?: string;
  agent_trace?: Array<{
    tool: string;
    args_summary: string;
    duration_ms: number;
    outcome: string;
    output_summary?: string;
    output_row_count?: number;
    error_class?: string;
    retry_count?: number;
  }>;
  agent_tier?: string;
  agent_run_id?: string;
  agent_run_status?: ChatRunStatus;
  agent_run_stage?: string;
  agent_run_stage_label?: string;
  agent_run_events?: ChatRunEvent[];
  agent_stream_state?: 'connecting' | 'connected' | 'reconnecting' | 'closed';
  semantic_lineage?: SemanticLineageItem[];
  response_kind?: 'answer' | 'clarification';
  clarification_context?: { reason_code: string; expected_input: string };
}

export interface ChatSidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  sessionsState?: 'loading' | 'ready' | 'error';
  sessionsError?: string | null;
  onRetrySessions?: () => void;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  connections: DatabaseConnection[];
  activeConnectionId: string;
  className?: string;
  onNavigate?: () => void;
}

export interface ChatInputProps {
  connections: DatabaseConnection[];
  activeConnectionId: string;
  onConnectionChange: (id: string) => void;
  onSend: (message: string) => void;
  draft: string;
  onDraftChange: (value: string) => void;
  focusRequest?: number;
  loading: boolean;
  disabled?: boolean;
  disabledReason?: string;
  errorMessage?: string | null;
}

export interface AddToDashboardMessage {
  title?: string;
  dbName?: string;
  rowCount?: number;
  sql?: string;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  connectionId?: string;
  chart_recommendation?: ChartRecommendation;
  column_metadata?: Record<string, string>;
}

export interface ChatChartBlockProps {
  recommendation: ChartRecommendation;
  rows: Array<Record<string, unknown>>;
  columns: string[];
  column_metadata?: Record<string, string>;
}

export interface ChatResultsPanelProps {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  rowCount: number;
  truncated?: boolean;
  executionTimeMs?: number;
  chartRecommendation?: ChartRecommendation;
  column_metadata?: Record<string, string>;
  onClose: () => void;
  panelHeight: number;
  onResize: (height: number) => void;
}

export interface ChatResultsTableProps {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  rowCount?: number;
  executionTime?: number;
  truncated?: boolean;
}


export interface AddToDashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
  message: AddToDashboardMessage;
}
