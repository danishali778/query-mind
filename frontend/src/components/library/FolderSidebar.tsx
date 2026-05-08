import { useState, useRef } from 'react';
import { 
  Folder, 
  Clock, 
  Calendar, 
  Users, 
  Globe, 
  Search, 
  Plus,
  Hash,
} from 'lucide-react';
import { T } from '../dashboard/tokens';
import { createLibraryFolder } from '../../services/api';
import type { FolderSidebarProps } from '../../types/library';

const TAG_COLORS: Record<string, string> = {
  revenue: T.accent, 
  churn: T.red, 
  users: T.green,
  weekly: T.yellow, 
  critical: T.red, 
  sales: T.accent, 
  funnel: T.purple,
};

export function FolderSidebar({ folders, tags, stats, activeFolder, activeTag, search, onFolderChange, onTagChange, onSearchChange, onFolderCreated }: FolderSidebarProps) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const startCreating = () => {
    setNewName('');
    setCreating(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const commitFolder = async () => {
    const name = newName.trim();
    if (name) {
      await createLibraryFolder(name);
      onFolderCreated();
      onFolderChange(name);
    }
    setCreating(false);
    setNewName('');
  };

  const cancelCreating = () => {
    setCreating(false);
    setNewName('');
  };

  const quickAccess = [
    { id: 'All Queries', icon: <Hash size={14} />, count: stats.total_queries },
    { id: 'Recently Run', icon: <Clock size={14} />, count: stats.recently_run ?? 0 },
    { id: 'Scheduled', icon: <Calendar size={14} />, count: stats.scheduled },
    { id: 'Shared with Me', icon: <Users size={14} />, count: 0 },
    { id: 'Public Library', icon: <Globe size={14} />, count: 0 },
  ];

  return (
    <div style={{
      width: 230, flexShrink: 0, background: T.bg, borderRight: `1px solid rgba(0,0,0,0.08)`,
      display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: T.fontBody
    }}>
      {/* Header & Search */}
      <div style={{ padding: '24px 16px 12px', borderBottom: `1px solid rgba(0,0,0,0.05)` }}>
        <div style={{ 
          fontFamily: T.fontMono, fontWeight: 800, fontSize: '0.62rem', 
          color: T.text3, marginBottom: 16, display: 'flex', alignItems: 'center', 
          justifyContent: 'space-between', textTransform: 'uppercase', letterSpacing: '0.15em'
        }}>
          Navigation
          <span>{folders.length + quickAccess.length}</span>
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: T.text3, pointerEvents: 'none' }} />
          <input placeholder="Filter library..." value={search} onChange={e => onSearchChange(e.target.value)} style={{
            width: '100%', background: '#fff', border: `1px solid rgba(0,0,0,0.08)`, borderRadius: 0, padding: '8px 10px 8px 32px',
            color: T.text, fontFamily: T.fontBody, fontSize: '0.78rem', outline: 'none', transition: 'all 0.2s ease'
          }}
            onFocus={e => e.currentTarget.style.borderColor = T.text}
            onBlur={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'}
          />
        </div>
      </div>

      {/* Body List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 8px', display: 'flex', flexDirection: 'column', gap: 2 }} className="custom-scroll">
        
        {/* Quick Access */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.1em', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, padding: '8px 12px 6px' }}>Main</div>
          {quickAccess.map(f => (
            <FolderItem key={f.id} active={activeFolder === f.id} onClick={() => onFolderChange(f.id)} icon={f.icon} label={f.id} count={f.count} />
          ))}
        </div>

        {/* My Folders */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.1em', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, padding: '8px 12px 6px' }}>Directories</div>
          {folders.map(f => (
            <FolderItem key={f.name} active={activeFolder === f.name} onClick={() => onFolderChange(f.name)} icon={<Folder size={14} />} label={f.name} count={f.count} />
          ))}
        </div>

        {/* Tags */}
        {tags.length > 0 && (
          <div style={{ padding: '12px 4px 0' }}>
            <span style={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.1em', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, padding: '0 0 10px 8px', display: 'block' }}>Taxonomy</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 8px' }}>
              {tags.map(t => {
                const active = activeTag === t;
                return (
                  <span key={t} onClick={() => onTagChange(active ? null : t)} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 0,
                    border: `1px solid ${active ? T.text : 'rgba(0,0,0,0.08)'}`, background: active ? T.text : 'transparent',
                    color: active ? '#fff' : T.text3, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s', fontFamily: T.fontMono,
                    textTransform: 'uppercase', letterSpacing: '0.02em'
                  }}
                    onMouseEnter={e => { if(!active){ e.currentTarget.style.borderColor = T.text; e.currentTarget.style.color = T.text; } }}
                    onMouseLeave={e => { if(!active){ e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'; e.currentTarget.style.color = T.text3; } }}
                  >
                    <div style={{ width: 6, height: 6, borderRadius: 0, background: active ? '#fff' : (TAG_COLORS[t] || T.text3) }}></div>
                    {t}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding: '16px', borderTop: `1px solid rgba(0,0,0,0.05)`, marginTop: 'auto', background: 'rgba(0,0,0,0.01)' }}>
        {creating ? (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              ref={inputRef}
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') commitFolder(); else if (e.key === 'Escape') cancelCreating(); }}
              onBlur={commitFolder}
              placeholder="Folder name..."
              style={{
                flex: 1, background: '#fff', border: `1px solid ${T.text}`, borderRadius: 0,
                padding: '8px 10px', color: T.text, fontFamily: T.fontBody, fontSize: '0.78rem', outline: 'none',
              }}
            />
          </div>
        ) : (
          <button onClick={startCreating} style={{
            width: '100%', padding: '10px 12px', borderRadius: 0, border: `1px dashed rgba(0,0,0,0.15)`, background: 'transparent',
            color: T.text3, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
            transition: 'all 0.2s ease', fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em'
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = T.text; e.currentTarget.style.color = T.text; e.currentTarget.style.background = '#fff'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,0,0,0.15)'; e.currentTarget.style.color = T.text3; e.currentTarget.style.background = 'transparent'; }}
          >
            <Plus size={14} /> New Directory
          </button>
        )}
      </div>

      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 2px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); }
      `}</style>
    </div>
  );
}

function FolderItem({ active, onClick, icon, label, count }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string, count: number }) {
  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 0, cursor: 'pointer',
      transition: 'all 0.15s ease', border: `1px solid ${active ? 'rgba(0,0,0,0.08)' : 'transparent'}`,
      background: active ? '#fff' : 'transparent', marginBottom: 1,
      position: 'relative'
    }}
      onMouseEnter={e => { if(!active) e.currentTarget.style.background = 'rgba(0,0,0,0.02)'; }}
      onMouseLeave={e => { if(!active) e.currentTarget.style.background = 'transparent'; }}
    >
      {active && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: T.text }} />}
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: active ? T.text : T.text3, opacity: active ? 1 : 0.6 }}>{icon}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: active ? 800 : 500, color: active ? T.text : T.text2, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
      {count > 0 && <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{count}</span>}
    </div>
  );
}
