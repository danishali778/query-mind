import { useState, useEffect, useRef, useCallback } from 'react';
import { Menu, Pin } from 'lucide-react';
import { MainShell } from '../components/common/MainShell';
import { Sidebar as ChatSidebar } from '../components/chat/Sidebar';
import { ChatInput } from '../components/chat/ChatInput';
import { MessageBubble } from '../components/chat/MessageBubble';
import { ConnectionModal } from '../components/chat/ConnectionModal';
import { T } from '../components/dashboard/tokens';
import { BREAKPOINTS, useMediaQuery } from '../hooks/useMediaQuery';
import * as api from '../services/api';
import { useAuth } from '../context/useAuth';
import type { ChatMessageView } from '../types/chat';
import type { ChatResponse, ChatRunEvent, ChatRunSnapshot, DatabaseConnection, SessionMessagesResponse, SessionSummary } from '../types/api';
import { useChatAgentRun } from '../hooks/useChatAgentRun';
import { useLocation, useNavigate } from 'react-router-dom';
import { SuggestionGrid } from '../components/suggestions/SuggestionGrid';
import type { QuestionSuggestion } from '../types/questionSuggestions';
import { isLlmSetupError } from '../services/llmSettings';
import { ApiRequestError } from '../services/http';

type LoadState = 'loading' | 'ready' | 'error';
type MessageLoadState = 'idle' | LoadState;

const CONNECTION_LOAD_ERROR = 'COULD NOT LOAD DATABASE CONNECTIONS';
const SESSION_LOAD_ERROR = 'COULD NOT LOAD CONVERSATIONS';
const MESSAGE_LOAD_ERROR = 'COULD NOT LOAD THIS CONVERSATION';
const SEND_ERROR = 'QUERY REQUEST FAILED. PLEASE TRY AGAIN';

function mapSessionMessages(data: SessionMessagesResponse): ChatMessageView[] {
  return data.messages.map((message) => ({
    id: message.id,
    role: message.role as ChatMessageView['role'],
    content: message.content,
    sql: message.sql || undefined,
    columns: message.columns || message.results?.columns || undefined,
    rows: message.rows || message.results?.rows || undefined,
    row_count: message.row_count ?? message.results?.row_count ?? undefined,
    truncated: message.truncated ?? message.results?.truncated ?? undefined,
    execution_time_ms: message.execution_time_ms ?? message.results?.execution_time_ms ?? undefined,
    chart_recommendation: message.chart_recommendation || undefined,
    column_metadata: message.column_metadata || undefined,
    error: message.error || undefined,
    is_pinned: message.is_pinned ?? false,
    parent_id: message.parent_id || undefined,
    prev_query_id: message.prev_query_id || undefined,
    agent_trace: message.agent_trace || undefined,
    agent_tier: message.agent_tier || undefined,
    agent_run_id: message.agent_run_id || undefined,
    agent_run_status: message.agent_run_status || undefined,
    agent_run_stage: message.agent_run_stage || undefined,
    agent_run_stage_label: message.agent_run_stage_label || undefined,
    semantic_lineage: message.semantic_lineage || undefined,
    response_kind: message.response_kind || 'answer',
    clarification_context: message.clarification_context || undefined,
  }));
}

function applyCompletedResponse(message: ChatMessageView, response: ChatResponse): ChatMessageView {
  return {
    ...message,
    id: response.message_id,
    content: response.message,
    sql: response.sql || undefined,
    columns: response.columns || [],
    rows: response.rows || [],
    row_count: response.row_count,
    truncated: response.truncated,
    execution_time_ms: response.execution_time_ms,
    chart_recommendation: response.chart_recommendation || undefined,
    column_metadata: response.column_metadata || undefined,
    error: response.error || undefined,
    is_pinned: response.is_pinned ?? false,
    prev_query_id: response.prev_query_id || undefined,
    agent_trace: response.agent_trace || undefined,
    agent_tier: response.agent_tier || undefined,
    semantic_lineage: response.semantic_lineage || undefined,
    response_kind: response.response_kind || 'answer',
    clarification_context: response.clarification_context || undefined,
    agent_run_status: 'completed',
    agent_run_stage: 'completed',
    agent_run_stage_label: response.response_kind === 'clarification' ? 'Clarification needed' : 'Answer ready',
    agent_stream_state: 'closed',
  };
}

function isUsageLimitError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes('LIMIT_EXCEEDED') || message.includes('402');
}

function StatePanel({
  title,
  body,
  tone = 'neutral',
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  tone?: 'neutral' | 'error';
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 18, textAlign: 'center' }}>
      <div style={{
        width: 56,
        height: 56,
        borderRadius: 0,
        background: tone === 'error' ? '#fee2e2' : '#1a1a1a',
        border: tone === 'error' ? '1px solid #fecaca' : 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '1.4rem',
        fontWeight: 900,
        color: tone === 'error' ? T.red : '#fff',
        fontFamily: T.fontHead,
        fontStyle: 'italic'
      }}>Q</div>
      <div style={{ fontFamily: T.fontMono, fontWeight: 900, fontSize: '0.8rem', color: tone === 'error' ? T.red : T.text, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        {title}
      </div>
      <div style={{ fontSize: '0.95rem', color: T.text2, maxWidth: 430, lineHeight: 1.6 }}>
        {body}
      </div>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: '11px 18px',
            borderRadius: 0,
            border: `1px solid ${tone === 'error' ? '#fecaca' : 'rgba(0,0,0,0.12)'}`,
            background: '#fff',
            color: T.text,
            cursor: 'pointer',
            fontFamily: T.fontMono,
            fontSize: '0.7rem',
            fontWeight: 900,
            letterSpacing: '0.06em',
            textTransform: 'uppercase'
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function ChatPage() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [connectionsState, setConnectionsState] = useState<LoadState>('loading');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [activeConnectionId, setActiveConnectionId] = useState('');
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsState, setSessionsState] = useState<LoadState>('loading');
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [messagesState, setMessagesState] = useState<MessageLoadState>('idle');
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const skipNextFetch = useRef(false);
  const messageLoadRequestRef = useRef(0);
  const pendingRequestRef = useRef<string | null>(null);
  const attachedRunRef = useRef<string | null>(null);
  const isMobile = useMediaQuery(BREAKPOINTS.lg);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [focusRequest, setFocusRequest] = useState(0);
  const [composerError, setComposerError] = useState<string | null>(null);
  const suggestionDraftRef = useRef(false);

  useEffect(() => {
    const state = location.state as { connectionId?: string; prompt?: string; suggestionId?: string } | null;
    if (!state?.prompt || connectionsState !== 'ready') return;
    if (state.connectionId) {
      if (!connections.some((item) => item.id === state.connectionId)) {
        navigate(location.pathname, { replace: true, state: null });
        return;
      }
      setActiveConnectionId(state.connectionId);
    }
    setDraft(state.prompt.slice(0, 2048));
    suggestionDraftRef.current = true;
    setFocusRequest((value) => value + 1);
    navigate(location.pathname, { replace: true, state: null });
  }, [connections, connectionsState, location.pathname, location.state, navigate]);

  const fillSuggestion = useCallback((suggestion: QuestionSuggestion) => {
    setDraft(suggestion.prompt);
    suggestionDraftRef.current = true;
    setFocusRequest((value) => value + 1);
  }, []);

  const changeComposerConnection = useCallback((connectionId: string) => {
    if (suggestionDraftRef.current) setDraft('');
    suggestionDraftRef.current = false;
    setActiveConnectionId(connectionId);
  }, []);

  const loadConnections = useCallback(async (options: { preferLast?: boolean; preferredId?: string } = {}) => {
    setConnectionsState('loading');
    setConnectionError(null);
    try {
      const conns = await api.listConnections();
      setConnections(conns);
      setConnectionsState('ready');
      setActiveConnectionId(current => {
        if (options.preferredId && conns.some(c => c.id === options.preferredId)) return options.preferredId;
        if (options.preferLast) return conns[conns.length - 1]?.id || '';
        if (current && conns.some(c => c.id === current)) return current;
        return conns[0]?.id || '';
      });
      return conns;
    } catch (error) {
      console.error('Failed to load connections:', error);
      setConnectionsState('error');
      setConnectionError(CONNECTION_LOAD_ERROR);
      return [];
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setSessionsState('loading');
    setSessionsError(null);
    try {
      const nextSessions = await api.listSessions();
      setSessions(nextSessions);
      setSessionsState('ready');
      return nextSessions;
    } catch (error) {
      console.error('Failed to load conversations:', error);
      setSessionsState('error');
      setSessionsError(SESSION_LOAD_ERROR);
      return [];
    }
  }, []);

  const updateRunSnapshot = useCallback((snapshot: ChatRunSnapshot) => {
    setMessages(prev => prev.map(message => {
      if (message.agent_run_id !== snapshot.run_id) return message;
      const updated: ChatMessageView = {
        ...message,
        agent_run_status: snapshot.status,
        agent_run_stage: snapshot.current_stage,
        agent_run_stage_label: snapshot.current_stage_label,
        agent_stream_state: ['completed', 'failed', 'cancelled'].includes(snapshot.status) ? 'closed' : 'connected',
        error: snapshot.status === 'failed' || snapshot.status === 'cancelled'
          ? snapshot.failure_message || message.error
          : message.error,
      };
      return snapshot.response ? applyCompletedResponse(updated, snapshot.response) : updated;
    }));
    if (['completed', 'failed', 'cancelled'].includes(snapshot.status)) {
      attachedRunRef.current = null;
      setLoading(false);
      void loadSessions();
    }
  }, [loadSessions]);

  const agentRun = useChatAgentRun({
    onAccepted: accepted => {
      const pendingId = pendingRequestRef.current;
      setMessages(prev => {
        const next = prev.map(message => message.id === pendingId ? { ...message, id: accepted.user_message_id } : message);
        if (next.some(message => message.agent_run_id === accepted.run_id)) return next;
        return [...next, {
          id: accepted.assistant_message_id,
          role: 'assistant',
          content: '',
          parent_id: accepted.user_message_id,
          agent_run_id: accepted.run_id,
          agent_run_status: accepted.status,
          agent_run_stage: 'preparing',
          agent_run_stage_label: accepted.status === 'completed' ? 'Clarification needed' : 'Response queued',
          agent_run_events: [],
          agent_stream_state: accepted.status === 'completed' ? 'closed' : 'connecting',
        }];
      });
      attachedRunRef.current = accepted.run_id;
      if (!activeSessionId) {
        skipNextFetch.current = true;
        setActiveSessionId(accepted.session_id);
        void loadSessions();
      }
    },
    onEvent: (event: ChatRunEvent) => {
      setMessages(prev => prev.map(message => {
        if (message.agent_run_id !== event.run_id) return message;
        const events = message.agent_run_events || [];
        const duplicate = events.some(item => item.sequence === event.sequence && item.type === event.type);
        const status = event.type === 'run.cancel_requested' ? 'cancel_requested'
          : event.type === 'run.completed' ? 'completed'
            : event.type === 'run.failed' ? 'failed'
              : event.type === 'run.cancelled' ? 'cancelled'
                : event.type === 'run.started' ? 'running'
                  : message.agent_run_status;
        return {
          ...message,
          agent_run_events: duplicate ? events : [...events, event],
          agent_run_status: status,
          agent_run_stage: event.stage || message.agent_run_stage,
          agent_run_stage_label: event.label || message.agent_run_stage_label,
          agent_stream_state: 'connected',
        };
      }));
    },
    onSnapshot: updateRunSnapshot,
    onError: error => {
      console.error('Agent stream failed:', error);
      setMessages(prev => prev.map(message => message.agent_run_id === attachedRunRef.current
        ? { ...message, agent_stream_state: 'reconnecting' }
        : message));
    },
  });
  const {
    start: startAgentRun,
    attach: attachAgentRun,
    cancel: cancelAgentRun,
    disconnect: disconnectAgentRun,
  } = agentRun;

  const loadMessages = useCallback(async (sessionId: string) => {
    const requestId = messageLoadRequestRef.current + 1;
    messageLoadRequestRef.current = requestId;
    setMessagesState('loading');
    setMessagesError(null);
    setMessages([]);

    try {
      const data = await api.getSessionMessages(sessionId);
      if (messageLoadRequestRef.current !== requestId) return;
      setMessages(mapSessionMessages(data));
      setMessagesState('ready');
      if (data.last_connection_id && connections.some(c => c.id === data.last_connection_id)) {
        setActiveConnectionId(data.last_connection_id);
      }
    } catch (error) {
      if (messageLoadRequestRef.current !== requestId) return;
      console.error('Failed to load conversation messages:', error);
      setMessages([]);
      setMessagesState('error');
      setMessagesError(MESSAGE_LOAD_ERROR);
    }
  }, [connections]);

  useEffect(() => {
    if (!isMobile) setSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen && isMobile ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [sidebarOpen, isMobile]);

  useEffect(() => {
    if (!user?.id) {
      setConnections([]);
      setConnectionsState('loading');
      setConnectionError(null);
      setActiveConnectionId('');
      setSessions([]);
      setSessionsState('loading');
      setSessionsError(null);
      setActiveSessionId(null);
      setMessages([]);
      setMessagesState('idle');
      setMessagesError(null);
      return;
    }
    void loadConnections();
    void loadSessions();
    void api.getSettings()
      .then(settings => setStreamingEnabled(settings.stream_responses !== false))
      .catch(() => setStreamingEnabled(true));
  }, [user?.id, loadConnections, loadSessions]);

  useEffect(() => {
    if (!activeSessionId) {
      messageLoadRequestRef.current += 1;
      setMessages([]);
      setMessagesState('idle');
      setMessagesError(null);
      return;
    }
    if (skipNextFetch.current) {
      skipNextFetch.current = false;
      setMessagesState('ready');
      setMessagesError(null);
      return;
    }
    void loadMessages(activeSessionId);
  }, [activeSessionId, loadMessages]);

  useEffect(() => {
    const activeRun = messages.find(message => message.agent_run_id && ['queued', 'running', 'cancel_requested'].includes(message.agent_run_status || ''));
    if (activeRun?.agent_run_id && attachedRunRef.current !== activeRun.agent_run_id) {
      attachedRunRef.current = activeRun.agent_run_id;
      void attachAgentRun(activeRun.agent_run_id).catch(error => console.error('Failed to restore agent run:', error));
    }
  }, [messages, attachAgentRun]);

  useEffect(() => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSqlSave = async (messageId: string, newSql: string) => {
    if (!activeSessionId || !activeConnectionId) return;
    try {
      const updatedMsg = await api.editSql(activeSessionId, messageId, {
        sql: newSql,
        connection_id: activeConnectionId
      });

      setMessages(prev => prev.map(m => m.id === messageId ? {
        ...m,
        sql: updatedMsg.sql || undefined,
        rows: updatedMsg.rows || updatedMsg.results?.rows || undefined,
        columns: updatedMsg.columns || updatedMsg.results?.columns || undefined,
        chart_recommendation: updatedMsg.chart_recommendation || undefined,
        truncated: updatedMsg.truncated ?? updatedMsg.results?.truncated ?? undefined,
        execution_time_ms: updatedMsg.execution_time_ms || updatedMsg.results?.execution_time_ms || undefined,
        error: updatedMsg.error || undefined,
        content: updatedMsg.content || m.content,
        is_pinned: updatedMsg.is_pinned ?? m.is_pinned,
      } : m));
    } catch (err) {
      console.error('Failed to save SQL:', err);
    }
  };

  const handleTogglePin = async (messageId: string, isPinned: boolean) => {
    if (!activeSessionId) return;
    try {
      await api.toggleMessagePin(activeSessionId, messageId, isPinned);
      setMessages(prev => prev.map(m => m.id === messageId ? { ...m, is_pinned: isPinned } : m));
    } catch (err) {
      console.error('Failed to toggle pin:', err);
    }
  };

  const handleSend = async (message: string) => {
    if (!activeConnectionId) {
      setMessagesState('ready');
      setMessages(prev => [...prev, { role: 'assistant', content: '', error: connectionsState === 'error' ? CONNECTION_LOAD_ERROR : 'CONNECT A DATABASE BEFORE CHATTING' }]);
      return;
    }

    const clientRequestId = crypto.randomUUID();
    const userMsg: ChatMessageView = { id: clientRequestId, role: 'user', content: message };
    pendingRequestRef.current = clientRequestId;
    setMessagesState('ready');
    setComposerError(null);
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    try {
      if (streamingEnabled) {
        await startAgentRun({
          connection_id: activeConnectionId,
          session_id: activeSessionId || undefined,
          message,
          client_request_id: clientRequestId,
        });
        setDraft('');
        setLoading(false);
        return;
      }
      const r = await api.sendMessage({ connection_id: activeConnectionId, session_id: activeSessionId || undefined, message });
      setDraft('');
      const assistantMsg: ChatMessageView = {
        id: r.message_id,
        role: 'assistant',
        content: r.message,
        sql: r.sql || undefined,
        columns: r.columns || [],
        rows: r.rows || [],
        row_count: r.row_count,
        truncated: r.truncated,
        execution_time_ms: r.execution_time_ms,
        chart_recommendation: r.chart_recommendation || undefined,
        column_metadata: r.column_metadata || undefined,
        error: r.error || undefined,
        is_pinned: r.is_pinned ?? false,
        parent_id: userMsg.id,
        prev_query_id: r.prev_query_id || undefined,
        agent_trace: r.agent_trace || undefined,
        agent_tier: r.agent_tier || undefined,
        semantic_lineage: r.semantic_lineage || undefined,
        response_kind: r.response_kind || 'answer',
        clarification_context: r.clarification_context || undefined,
      };
      setMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0 && updated[updated.length - 1].role === 'user') {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            id: r.user_message_id,
            prev_query_id: r.prev_query_id || undefined
          };
        }
        return [...updated, assistantMsg];
      });

      if (!activeSessionId && r.session_id) {
        skipNextFetch.current = true;
        setActiveSessionId(r.session_id);
        void loadSessions();
      }
    } catch (err) {
      if (err instanceof ApiRequestError && ['chat_sensitive_input_detected', 'chat_input_unintelligible'].includes(err.code)) {
        setMessages(prev => prev.filter(item => item.id !== clientRequestId));
        setDraft(message);
        setFocusRequest(value => value + 1);
        setComposerError(
          err.code === 'chat_sensitive_input_detected'
            ? 'Remove the credential from this message and rotate it before continuing.'
            : 'Enter a database question using a metric, table, or business outcome.'
        );
      } else if (isLlmSetupError(err)) {
        setMessages(prev => [...prev, { role: 'assistant', content: '', error: 'AI PROVIDER SETUP REQUIRED. ADD A PERSONAL KEY IN SETTINGS > AI PROVIDERS, THEN RETRY THIS QUESTION.' }]);
        navigate('/settings', {
          state: {
            section: 'ai',
            returnTo: '/chat',
            connectionId: activeConnectionId,
            prompt: message,
          },
        });
      } else if (isUsageLimitError(err)) {
        setShowPaywall(true);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: '', error: SEND_ERROR }]);
      }
    } finally { setLoading(false); pendingRequestRef.current = null; }
  };

  const handleNewChat = () => {
    disconnectAgentRun();
    setActiveSessionId(null);
    setMessages([]);
    setMessagesState('idle');
    setMessagesError(null);
  };

  const handleDeleteSession = async (sid: string) => {
    await api.deleteSession(sid);
    setSessions(prev => prev.filter(s => s.id !== sid));
    if (activeSessionId === sid) handleNewChat();
  };

  const handleRenameSession = async (sid: string, title: string) => {
    await api.renameSession(sid, title);
    setSessions(prev => prev.map(s => s.id === sid ? { ...s, title } : s));
  };

  const handleRefreshConnections = () => {
    void loadConnections({ preferLast: true });
  };

  const activeConn = connections.find(c => c.id === activeConnectionId);
  const activeSession = sessions.find(s => s.id === activeSessionId);
  const hasActiveRun = messages.some(message => ['queued', 'running', 'cancel_requested'].includes(message.agent_run_status || ''));
  const chatInputDisabled = loading || hasActiveRun || connectionsState !== 'ready' || !activeConnectionId;
  const chatInputDisabledReason = connectionsState === 'loading'
    ? 'LOADING SOURCES'
    : connectionsState === 'error'
      ? 'SOURCE LOAD FAILED'
      : connections.length === 0
        ? 'CONNECT A DATABASE'
        : !activeConnectionId
          ? 'SELECT DATABASE'
          : undefined;
  const showConnectionLoading = connectionsState === 'loading' && connections.length === 0;
  const showConnectionError = connectionsState === 'error' && connections.length === 0;
  const showNoConnections = connectionsState === 'ready' && connections.length === 0;
  const showMessageLoading = connectionsState === 'ready' && connections.length > 0 && messagesState === 'loading';
  const showMessageError = connectionsState === 'ready' && connections.length > 0 && messagesState === 'error';
  const showEmptyPrompt = connectionsState === 'ready' && connections.length > 0 && messagesState !== 'loading' && messagesState !== 'error' && messages.length === 0;

  return (
    <MainShell
      title={activeSession?.title || 'New Chat'}
      subtitle={activeConn ? `${activeConn.db_type} - ${activeConn.database}` : 'Select a connection'}
      hideSidebar={true}
      hideHeader={true}
      activeId="chat"
      badge={activeConn ? {
        text: 'Live',
        color: T.green,
        icon: <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.green }} />
      } : undefined}
    >
      <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden', position: 'relative' }}>
        {isMobile && sidebarOpen && (
          <button
            type="button"
            className="app-shell-backdrop"
            aria-label="Close conversations"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <ChatSidebar
          className={sidebarOpen ? 'drawer-panel drawer-panel--open responsive-panel responsive-panel--overlay' : 'drawer-panel responsive-panel responsive-panel--overlay'}
          onNavigate={() => setSidebarOpen(false)}
          sessions={sessions} activeSessionId={activeSessionId}
          sessionsState={sessionsState} sessionsError={sessionsError} onRetrySessions={() => { void loadSessions(); }}
          onSelectSession={(id) => { disconnectAgentRun(); attachedRunRef.current = null; setActiveSessionId(id); }} onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession} onRenameSession={handleRenameSession}
          connections={connections} activeConnectionId={activeConnectionId}
        />

        <div style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: 'transparent',
          position: 'relative'
        }}>
          {isMobile && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px clamp(16px, 4vw, 24px)',
              borderBottom: '1px solid rgba(0,0,0,0.08)',
              background: T.bg,
              flexShrink: 0,
            }}>
              <button
                type="button"
                className="mobile-menu-btn"
                aria-label="Open conversations"
                onClick={() => setSidebarOpen(true)}
                style={{ display: 'inline-flex' }}
              >
                <Menu size={18} />
              </button>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {activeSession?.title || 'New Chat'}
                </div>
                <div style={{ fontFamily: T.fontMono, fontSize: '0.62rem', color: T.text3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {activeConn ? `${activeConn.db_type} · ${activeConn.database}` : 'Select a connection'}
                </div>
              </div>
            </div>
          )}
          <div style={{ flex: 1, display: 'flex', justifyContent: 'center', minWidth: 0, overflow: 'hidden' }}>
            <div
              id="chat-messages-scroll"
              className="responsive-inset"
              style={{
                width: '100%',
                minWidth: 0,
                maxWidth: 1200,
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                overflowX: 'hidden',
                paddingTop: 0,
                paddingBottom: 40,
                scrollBehavior: 'smooth'
              }}
            >
              <div style={{ width: '100%', minWidth: 0, paddingTop: 24 }}>
                {messages.filter(m => m.is_pinned).length > 0 && (
                  <div style={{ padding: '0 0 24px', borderBottom: `1px solid rgba(0,0,0,0.05)`, marginBottom: 32 }}>
                    <div style={{ fontSize: '0.62rem', fontWeight: 700, color: T.text3, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontFamily: T.fontMono }}>
                      <Pin size={10} strokeWidth={3} /> PINNED OBSERVATIONS
                    </div>
                    <div style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8, scrollbarWidth: 'none' }}>
                      {messages.filter(m => m.is_pinned).map(m => (
                        <div
                          key={m.id}
                          onClick={() => {
                            const el = document.getElementById(`msg-${m.id}`);
                            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          }}
                          style={{
                            minWidth: 200, maxWidth: 260, background: '#fff', border: `1px solid rgba(0,0,0,0.08)`,
                            borderRadius: 0, padding: '12px 16px', cursor: 'pointer', transition: 'all 0.2s',
                            display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0,
                          }}
                        >
                          <div style={{ fontSize: '0.9rem', fontWeight: 800, color: T.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: T.fontHead, fontStyle: 'italic' }}>
                            {m.content.length > 30 ? m.content.substring(0, 30) + '...' : m.content}
                          </div>
                          <div style={{ fontSize: '0.6rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {m.rows?.length || 0} ROWS - {m.columns?.length || 0} COLS
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {showConnectionLoading && (
                  <StatePanel title="LOADING DATABASE CONNECTIONS" body="Preparing your available data sources before chat starts." />
                )}

                {showConnectionError && (
                  <StatePanel title="SOURCE LOAD FAILED" body={connectionError || CONNECTION_LOAD_ERROR} tone="error" actionLabel="RETRY LOAD" onAction={() => { void loadConnections(); }} />
                )}

                {showNoConnections && (
                  <StatePanel title="NO DATABASE CONNECTIONS" body="Connect a PostgreSQL database before starting a chat." actionLabel="CONNECT DATABASE" onAction={() => setShowConnectModal(true)} />
                )}

                {showMessageLoading && (
                  <StatePanel title="LOADING CONVERSATION" body="Restoring the selected conversation and its saved results." />
                )}

                {showMessageError && (
                  <StatePanel title="CONVERSATION LOAD FAILED" body={messagesError || MESSAGE_LOAD_ERROR} tone="error" actionLabel="RETRY MESSAGE LOAD" onAction={() => { if (activeSessionId) void loadMessages(activeSessionId); }} />
                )}

                {showEmptyPrompt && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 20 }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: 0, background: '#1a1a1a',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '1.8rem', fontWeight: 900, color: '#fff',
                      marginBottom: 12, fontFamily: T.fontHead, fontStyle: 'italic'
                    }}>Q</div>
                    <div style={{
                      fontFamily: T.fontHead, fontWeight: 900, fontSize: 'clamp(1.8rem, 6vw, 2.8rem)',
                      color: T.text, letterSpacing: -1.2, fontStyle: 'italic',
                      textAlign: 'center', lineHeight: 1
                    }}>
                      What would you <br />like to know?
                    </div>
                    <div style={{ fontSize: '1rem', color: T.text2, maxWidth: 460, textAlign: 'center', lineHeight: 1.6, fontWeight: 400, opacity: 0.7 }}>
                      query-mind translates your plain English questions into optimized SQL, executing them against your database in real-time.
                    </div>
                    <div style={{ width: 'min(900px, 100%)', marginTop: 16 }}>
                      <SuggestionGrid
                        connectionId={activeConnectionId}
                        surface="chat"
                        onSelect={fillSuggestion}
                        primaryLabel="Fill composer"
                        compact
                      />
                    </div>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <MessageBubble
                    key={msg.id || i}
                    message={msg}
                    connectionId={activeConnectionId}
                    onSqlSave={handleSqlSave}
                    onTogglePin={handleTogglePin}
                    onCancelRun={async (runId) => { await cancelAgentRun(runId); }}
                  />
                ))}

                {loading && (
                  <div style={{ padding: '24px 12px', display: 'flex', gap: 14, alignItems: 'center' }}>
                    <div style={{ width: 20, height: 20, borderRadius: 0, background: '#1a1a1a', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.7rem', fontWeight: 900, fontStyle: 'italic' }}>Q</div>
                    <div style={{ fontFamily: T.fontMono, fontSize: '0.72rem', color: T.text3, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                      Starting response…
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', background: 'transparent', flexShrink: 0, paddingBottom: 24 }}>
            <div className="responsive-inset" style={{ width: '100%', maxWidth: 1200 }}>
              <ChatInput
                connections={connections} activeConnectionId={activeConnectionId}
                onConnectionChange={changeComposerConnection} onSend={handleSend} loading={loading}
                draft={draft} onDraftChange={(value) => { suggestionDraftRef.current = false; setDraft(value); setComposerError(null); }} focusRequest={focusRequest}
                disabled={chatInputDisabled} disabledReason={chatInputDisabledReason}
                errorMessage={composerError}
              />
            </div>
          </div>
        </div>
      </div>

      <ConnectionModal isOpen={showConnectModal} onClose={() => setShowConnectModal(false)} onConnected={handleRefreshConnections} />

      {showPaywall && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(5,5,5,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          animation: 'fadeIn 0.3s ease-out'
        }}>
          <div style={{
            background: T.s1, border: `1px solid ${T.border}`, borderRadius: 24,
            padding: '40px 40px', maxWidth: 440, width: '100%', textAlign: 'center',
            boxShadow: '0 24px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(124,58,255,0.1) inset'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>!</div>
            <h2 style={{ fontFamily: T.fontHead, fontWeight: 800, fontSize: '1.8rem', color: T.text, margin: '0 0 12px 0' }}>Usage Limit Reached</h2>
            <p style={{ fontSize: '0.95rem', color: T.text3, lineHeight: 1.6, margin: '0 0 32px 0' }}>
              You have hit your free tier limit for AI requests. Upgrade to Pro for unlimited AI analytics, background sync, and more.
            </p>
            <button
              onClick={() => { window.location.href = '/upgrade'; }}
              style={{
                width: '100%', padding: '14px 0', borderRadius: 12, border: 'none', cursor: 'pointer',
                background: `linear-gradient(135deg, ${T.accent}, ${T.purple})`,
                color: '#fff', fontSize: '1rem', fontWeight: 700, fontFamily: T.fontBody,
                boxShadow: '0 8px 24px rgba(124,58,255,0.25)', marginBottom: 12, transition: 'transform 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
            >
              Upgrade to PRO
            </button>
            <button
              onClick={() => setShowPaywall(false)}
              style={{
                width: '100%', padding: '12px 0', borderRadius: 12, border: 'none', cursor: 'pointer',
                background: 'transparent', color: T.text3, fontSize: '0.9rem', fontWeight: 600, transition: 'color 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.color = T.text2}
              onMouseLeave={e => e.currentTarget.style.color = T.text3}
            >
              Maybe Later
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes thinkbounce { 0%,60%,100%{transform:translateY(0);opacity:0.4} 30%{transform:translateY(-5px);opacity:1} }
      `}</style>
    </MainShell>
  );
}
