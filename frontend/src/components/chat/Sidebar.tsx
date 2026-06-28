import { useState } from 'react';
import { T } from '../dashboard/tokens';
import type { ChatSidebarProps } from '../../types/chat';
import { DeleteSessionModal } from './DeleteSessionModal';

export function Sidebar({ sessions, activeSessionId, onSelectSession, onNewChat, onDeleteSession, onRenameSession, connections, activeConnectionId }: ChatSidebarProps) {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  const weekAgo = Date.now() - 7 * 86400000;

  const grouped: { label: string; items: ChatSidebarProps['sessions'] }[] = [];
  const todayItems: ChatSidebarProps['sessions'] = [], yesterdayItems: ChatSidebarProps['sessions'] = [], weekItems: ChatSidebarProps['sessions'] = [], olderItems: ChatSidebarProps['sessions'] = [];

  sessions.forEach(s => {
    const d = new Date(s.created_at);
    const ds = d.toDateString();
    if (ds === today) todayItems.push(s);
    else if (ds === yesterday) yesterdayItems.push(s);
    else if (d.getTime() > weekAgo) weekItems.push(s);
    else olderItems.push(s);
  });

  if (todayItems.length) grouped.push({ label: 'Today', items: todayItems });
  if (yesterdayItems.length) grouped.push({ label: 'Yesterday', items: yesterdayItems });
  if (weekItems.length) grouped.push({ label: 'Last 7 Days', items: weekItems });
  if (olderItems.length) grouped.push({ label: 'Older', items: olderItems });

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  };

  const dbTypeLabel = (t: string) => {
    const m: Record<string, string> = { postgresql: 'PG', mysql: 'MY', sqlite: 'SL' };
    return m[t?.toLowerCase()] || t?.slice(0, 2).toUpperCase() || '??';
  };
  const activeConn = connections.find(c => c.id === activeConnectionId);

  return (
    <aside style={{ 
      width: 280, 
      flexShrink: 0, 
      background: '#fdfcfb', 
      borderRight: `1px solid rgba(0,0,0,0.08)`, 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%', 
      overflow: 'hidden' 
    }}>
      {/* Logo + Active Connection */}
      <div style={{ padding: '24px 20px 10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.4rem', letterSpacing: -0.8, marginBottom: 20, color: '#1a1a1a' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 24, background: '#1a1a1a', borderRadius: 4, color: '#fff', fontSize: '0.9rem', fontWeight: 900, fontStyle: 'italic' }}>
            Q
          </div>
          <div style={{ fontStyle: 'italic' }}>
            query-mind
          </div>
        </div>

        {/* Active Connection Pill - White Border Style */}
        <div style={{ 
          display: 'inline-flex', alignItems: 'center', gap: 8, 
          padding: '5px 12px', borderRadius: 0, 
          background: '#fff', border: `1px solid rgba(0,0,0,0.1)`, 
          marginBottom: 24
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: activeConn ? '#1a1a1a' : '#ef4444' }} />
          <span style={{ fontSize: '0.68rem', color: T.text, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
            {activeConn?.database || 'NOT CONNECTED'}
            <span style={{ color: T.text3, marginLeft: 6, fontWeight: 500 }}>{dbTypeLabel(activeConn?.db_type || 'pg')}</span>
          </span>
        </div>

        <button onClick={onNewChat} style={{
          width: '100%', padding: '12px 14px',
          background: '#fff',
          border: `1.5px solid #1a1a1a`, borderRadius: 0, color: '#1a1a1a',
          fontFamily: T.fontBody, fontSize: '0.85rem', fontWeight: 800,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, transition: 'all 0.2s',
          textTransform: 'uppercase', letterSpacing: '0.05em'
        }}>
          <span style={{ fontSize: '1.2rem', fontWeight: 300, transform: 'translateY(-1px)' }}>+</span> New conversation
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '0 20px 6px' }}>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: T.text3 }}>🔍</span>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search conversations..."
            style={{
              width: '100%', background: 'transparent', border: 'none',
              borderBottom: `1px solid rgba(0,0,0,0.1)`,
              borderRadius: 0, padding: '10px 10px 10px 30px',
              color: T.text, fontFamily: T.fontBody, fontSize: '0.8rem', outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Conversations */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 20px 10px' }}>
        {grouped.map(group => (
          <div key={group.label}>
            <div style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: 1.5, color: T.text3, textTransform: 'uppercase', padding: '12px 6px 6px', fontFamily: T.fontMono }}>{group.label}</div>
            {group.items
              .filter(s => !search || s.id.toLowerCase().includes(search.toLowerCase()) || (s.title || '').toLowerCase().includes(search.toLowerCase()))
              .map(s => {
                const isActive = s.id === activeSessionId;
                return (
                  <div key={s.id} onClick={() => onSelectSession(s.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '12px 12px',
                      cursor: 'pointer', marginBottom: 2, 
                      background: isActive ? '#fff' : hoveredId === s.id ? 'rgba(0,0,0,0.02)' : 'transparent', 
                      position: 'relative', transition: 'background 0.15s',
                      border: isActive ? `1px solid rgba(0,0,0,0.08)` : '1px solid transparent'
                    }}
                    onMouseEnter={() => setHoveredId(s.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    {isActive && <div style={{ position: 'absolute', left: -1, top: 0, bottom: 0, width: 2, background: '#1a1a1a' }} />}
                    <div style={{ width: 4, height: 4, borderRadius: '50%', background: isActive ? '#1a1a1a' : 'rgba(0,0,0,0.1)', flexShrink: 0 }} />
                    {editingId === s.id ? (
                      <input
                        autoFocus
                        value={editText}
                        onChange={e => setEditText(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') { onRenameSession(s.id, editText.trim() || s.title || `Session ${s.id.slice(0, 6)}`); setEditingId(null); }
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        onBlur={() => { onRenameSession(s.id, editText.trim() || s.title || `Session ${s.id.slice(0, 6)}`); setEditingId(null); }}
                        onClick={e => e.stopPropagation()}
                        style={{
                          flex: 1, fontSize: '0.8rem', color: T.text, background: T.s2,
                          border: `1px solid ${T.accent}`, borderRadius: 4, padding: '1px 4px',
                          outline: 'none', fontFamily: T.fontBody, minWidth: 0,
                        }}
                      />
                    ) : (
                      <span
                        onDoubleClick={e => { e.stopPropagation(); setEditingId(s.id); setEditText(s.title || `Session ${s.id.slice(0, 6)}`); }}
                        style={{ fontSize: '0.8rem', color: isActive ? T.text : T.text2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}
                      >
                        {s.title || `Session ${s.id.slice(0, 6)}`}
                      </span>
                    )}
                    <span style={{ fontSize: '0.65rem', color: T.text3, fontFamily: T.fontMono, flexShrink: 0 }}>{timeAgo(s.created_at)}</span>
                    <button
                      onClick={e => {
                        e.stopPropagation();
                        setDeleteId(s.id);
                      }}
                      title="Delete chat"
                      style={{
                        background: 'none', border: 'none', color: T.text3, cursor: 'pointer',
                        fontSize: '0.9rem', padding: '2px 6px',
                        opacity: hoveredId === s.id ? 1 : 0,
                        transition: 'all 0.2s', flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        borderRadius: 4,
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = T.red; e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'; }}
                      onMouseLeave={e => { e.currentTarget.style.color = T.text3; e.currentTarget.style.background = 'none'; }}
                    >
                      <span style={{ transform: 'translateY(-1px)' }}>×</span>
                    </button>
                  </div>
                );
              })}
          </div>
        ))}
        {sessions.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 20px', color: T.text3, fontSize: '0.8rem', lineHeight: 1.7 }}>
            No conversations yet.<br />Start a new chat!
          </div>
        )}
      </div>

      <DeleteSessionModal
        isOpen={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={() => {
          if (deleteId) onDeleteSession(deleteId);
        }}
        sessionTitle={sessions.find(s => s.id === deleteId)?.title || undefined}
      />


      {/* User Footer - Premium Image 2 Style */}
      <div style={{ 
        padding: '16px 20px', 
        borderTop: `1px solid rgba(0,0,0,0.08)`, 
        display: 'flex', 
        alignItems: 'center', 
        gap: 12, 
        background: '#fff'
      }}>
        <div style={{ 
          width: 34, height: 34, borderRadius: 0, background: '#1a1a1a', 
          display: 'flex', alignItems: 'center', justifyContent: 'center', 
          fontSize: '0.85rem', fontWeight: 900, color: '#fff', flexShrink: 0,
          fontStyle: 'italic'
        }}>U</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1a1a1a' }}>User Account</div>
          <div style={{ fontSize: '0.68rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pro Member</div>
        </div>
      </div>
    </aside>
  );
}
