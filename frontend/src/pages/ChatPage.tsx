import { useState, useEffect, useRef } from 'react';
import { Pin } from 'lucide-react';
import { MainShell } from '../components/common/MainShell';
import { Sidebar as ChatSidebar } from '../components/chat/Sidebar';
import { ChatInput } from '../components/chat/ChatInput';
import { MessageBubble } from '../components/chat/MessageBubble';
import { ConnectionModal } from '../components/chat/ConnectionModal';
import { T } from '../components/dashboard/tokens';
import * as api from '../services/api';
import type { ChatMessageView } from '../types/chat';
import type { DatabaseConnection, SessionSummary } from '../types/api';

export function ChatPage() {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState('');
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [loading, setLoading] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const skipNextFetch = useRef(false);

  useEffect(() => {
    api.listConnections().then(conns => {
      setConnections(conns);
      if (conns.length > 0) setActiveConnectionId(conns[0].id);
    });
    api.listSessions().then(setSessions);
  }, []);

  useEffect(() => {
    if (!activeSessionId) { setMessages([]); return; }
    if (skipNextFetch.current) { skipNextFetch.current = false; return; }
    api.getSessionMessages(activeSessionId).then(data => {
      const msgs: ChatMessageView[] = data.messages.map((message) => ({
        id: message.id,
        role: message.role as any,
        content: message.content,
        sql: message.sql || undefined,
        columns: message.columns || message.results?.columns || undefined,
        rows: message.rows || message.results?.rows || undefined,
        row_count: message.row_count ?? message.results?.row_count ?? undefined,
        execution_time_ms: message.execution_time_ms ?? message.results?.execution_time_ms ?? undefined,
        chart_recommendation: message.chart_recommendation || undefined,
        column_metadata: message.column_metadata || undefined,
        error: message.error || undefined,
        is_pinned: message.is_pinned ?? false,
        parent_id: message.parent_id || undefined,
        prev_query_id: message.prev_query_id || undefined,
      }));
      setMessages(msgs);
      // Auto-switch to the session's last-used connection
      if (data.last_connection_id && connections.some(c => c.id === data.last_connection_id)) {
        setActiveConnectionId(data.last_connection_id);
      }
    });
  }, [activeSessionId, connections]); // Added connections to deps to ensure switch works when conns load

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSqlSave = async (messageId: string, newSql: string) => {
    if (!activeSessionId || !activeConnectionId) return;
    try {
      const updatedMsg = await api.editSql(activeSessionId, messageId, {
        sql: newSql,
        connection_id: activeConnectionId
      });

      setMessages(prev => prev.map(m => m.id === messageId ? {
        ...m,
        sql: (updatedMsg as any).sql || undefined,
        rows: (updatedMsg as any).rows || (updatedMsg as any).results?.rows || undefined,
        columns: (updatedMsg as any).columns || (updatedMsg as any).results?.columns || undefined,
        chart_recommendation: (updatedMsg as any).chart_recommendation || undefined,
        execution_time_ms: (updatedMsg as any).execution_time_ms || (updatedMsg as any).results?.execution_time_ms || undefined,
        error: (updatedMsg as any).error || undefined,
        content: (updatedMsg as any).content || m.content,
        is_pinned: (updatedMsg as any).is_pinned ?? m.is_pinned,
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
    if (!activeConnectionId) return;
    const userMsg: ChatMessageView = { role: 'user', content: message };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    try {
      const r = await api.sendMessage({ connection_id: activeConnectionId, session_id: activeSessionId || undefined, message });
      const assistantMsg: ChatMessageView = {
        id: r.message_id,
        role: 'assistant',
        content: r.message,
        sql: r.sql || undefined,
        columns: r.columns || [],
        rows: r.rows || [],
        row_count: r.row_count,
        execution_time_ms: r.execution_time_ms,
        chart_recommendation: r.chart_recommendation || undefined,
        column_metadata: r.column_metadata || undefined,
        error: r.error || undefined,
        is_pinned: r.is_pinned ?? false,
        parent_id: userMsg.id, // Direct link
        prev_query_id: r.prev_query_id || undefined,
      };
      setMessages(prev => {
        const updated = [...prev];
        // The last message in 'prev' is the user message we just added
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
        api.listSessions().then(setSessions);
      }
    } catch (err: any) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('LIMIT_EXCEEDED') || msg.includes('402')) {
        setShowPaywall(true);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: '', error: msg }]);
      }
    } finally { setLoading(false); }
  };

  const handleNewChat = () => { setActiveSessionId(null); setMessages([]); };
  const handleDeleteSession = async (sid: string) => {
    await api.deleteSession(sid);
    setSessions(prev => prev.filter(s => s.id !== sid));
    if (activeSessionId === sid) { setActiveSessionId(null); setMessages([]); }
  };
  const handleRenameSession = async (sid: string, title: string) => {
    await api.renameSession(sid, title);
    setSessions(prev => prev.map(s => s.id === sid ? { ...s, title } : s));
  };
  const handleRefreshConnections = () => {
    api.listConnections().then(conns => {
      setConnections(conns);
      if (conns.length > 0 && !activeConnectionId) setActiveConnectionId(conns[0].id);
      else if (conns.length > 0) setActiveConnectionId(conns[conns.length - 1].id);
    });
  };

  const activeConn = connections.find(c => c.id === activeConnectionId);
  const activeSession = sessions.find(s => s.id === activeSessionId);

  return (
    <MainShell
      title={activeSession?.title || 'New Chat'}
      subtitle={activeConn ? `${activeConn.db_type} • ${activeConn.database}` : 'Select a connection'}
      hideSidebar={true}
      hideHeader={true}
      activeId="chat"
      badge={activeConn ? {
        text: 'Live',
        color: T.green,
        icon: <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.green }} />
      } : undefined}
      headerActions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => setSchemaOpen(!schemaOpen)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 14px', borderRadius: 8,
              border: `1px solid ${schemaOpen ? T.accent : T.border}`,
              background: schemaOpen ? T.accentDim : 'transparent',
              color: schemaOpen ? T.accent : T.text2,
              fontSize: '0.76rem', cursor: 'pointer', fontFamily: T.fontBody,
              transition: 'all 0.18s ease',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            Schema {schemaOpen ? 'Open' : ''}
          </button>
        </div>
      }
    >
      <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden', position: 'relative' }}>
        <ChatSidebar
          sessions={sessions} activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId} onNewChat={handleNewChat}
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
          {/* Main Stage (Messages + Centering Logic) */}
          <div style={{ flex: 1, display: 'flex', justifyContent: 'center', minWidth: 0, overflow: 'hidden' }}>
            <div
              id="chat-messages-scroll"
              style={{
                width: '100%',
                minWidth: 0,
                maxWidth: 1200,
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: '0 80px 40px', // Increased padding for editorial feel
                scrollBehavior: 'smooth'
              }}
            >
              <div style={{ width: '100%', minWidth: 0, paddingTop: 24 }}>
                {/* Pinned Messages Bar - Editorial Style */}
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
                            {m.rows?.length || 0} ROWS • {m.columns?.length || 0} COLS
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {messages.length === 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '65vh', gap: 20 }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: 0, background: '#1a1a1a',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '1.8rem', fontWeight: 900, color: '#fff',
                      marginBottom: 12, fontFamily: T.fontHead, fontStyle: 'italic'
                    }}>Q</div>
                    <div style={{
                      fontFamily: T.fontHead, fontWeight: 900, fontSize: '2.8rem',
                      color: T.text, letterSpacing: -1.2, fontStyle: 'italic',
                      textAlign: 'center', lineHeight: 1
                    }}>
                      What would you <br />like to know?
                    </div>
                    <div style={{ fontSize: '1rem', color: T.text2, maxWidth: 460, textAlign: 'center', lineHeight: 1.6, fontWeight: 400, opacity: 0.7 }}>
                      query-mind translates your plain English questions into optimized SQL, executing them against your database in real-time.
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 16, justifyContent: 'center' }}>
                      {['Show me all tables', 'Describe the database', 'Who are the top customers?'].map(s => (
                        <button key={s} onClick={() => handleSend(s)} disabled={!activeConnectionId || loading} style={{
                          padding: '10px 20px', borderRadius: 0, border: `1px solid rgba(0,0,0,0.1)`, background: '#fff',
                          color: T.text, fontSize: '0.8rem', cursor: 'pointer', transition: 'all 0.2s', whiteSpace: 'nowrap',
                          fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
                        }}
                          onMouseEnter={e => { e.currentTarget.style.borderColor = '#1a1a1a'; e.currentTarget.style.background = '#fdfcfb'; }}
                          onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'; e.currentTarget.style.background = '#fff'; }}
                        >{s}</button>
                      ))}
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
                  />
                ))}

                {loading && (
                  <div style={{ padding: '24px 12px', display: 'flex', gap: 14 }}>
                    <div style={{ width: 20, height: 20, borderRadius: 0, background: '#1a1a1a', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.7rem', fontWeight: 900, fontStyle: 'italic' }}>Q</div>
                    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                      <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#1a1a1a', animation: 'thinkbounce 1.2s 0s infinite' }} />
                      <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#1a1a1a', animation: 'thinkbounce 1.2s 0.2s infinite' }} />
                      <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#1a1a1a', animation: 'thinkbounce 1.2s 0.4s infinite' }} />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', background: 'transparent', flexShrink: 0, paddingBottom: 24 }}>
            <div style={{ width: '100%', maxWidth: 1200, padding: '0 80px' }}>
              <ChatInput
                connections={connections} activeConnectionId={activeConnectionId}
                onConnectionChange={setActiveConnectionId} onSend={handleSend} loading={loading}
              />
            </div>
          </div>
        </div>
      </div>

      <ConnectionModal isOpen={showConnectModal} onClose={() => setShowConnectModal(false)} onConnected={handleRefreshConnections} />

      {/* Paywall Overlay */}
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
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>⚡</div>
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
