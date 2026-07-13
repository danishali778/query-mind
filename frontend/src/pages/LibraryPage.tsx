import { useState, useEffect, useCallback } from 'react';
import { MainShell } from '../components/common/MainShell';
import { HeaderIcons } from '../components/common/AppHeader';
import { FolderSidebar } from '../components/library/FolderSidebar';
import { QueryList } from '../components/library/QueryList';
import { T } from '../components/dashboard/tokens';
import { listSavedQueries, listLibraryFolders, listLibraryTags, getLibraryStats, deleteSavedQuery } from '../services/api';
import type { FolderSummary, LibraryStats } from '../types/api';
import type { LibraryQuery } from '../types/library';

export function LibraryPage() {
  const [queries, setQueries] = useState<LibraryQuery[]>([]);
  const [folders, setFolders] = useState<FolderSummary[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [stats, setStats] = useState<LibraryStats>({ total_queries: 0, scheduled: 0, total_runs: 0, recently_run: 0, folders: 0 });
  const [activeFolder, setActiveFolder] = useState('All Queries');
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const [q, f, t, s] = await Promise.all([
        listSavedQueries(activeFolder !== 'All Queries' ? activeFolder : undefined, activeTag || undefined),
        listLibraryFolders(),
        listLibraryTags(),
        getLibraryStats(),
      ]);
      setQueries(q);
      setFolders(f);
      setTags(t);
      setStats(s);
    } catch {
      // silently handle for now
    }
  }, [activeFolder, activeTag]);

  useEffect(() => {
    const timer = window.setTimeout(() => void fetchAll(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchAll]);

  const filteredQueries = search.trim()
    ? queries.filter(q => q.title.toLowerCase().includes(search.toLowerCase()) || q.sql.toLowerCase().includes(search.toLowerCase()))
    : queries;

  const handleDelete = async (id: string) => {
    await deleteSavedQuery(id);
    if (selectedId === id) setSelectedId(null);
    fetchAll();
  };

  return (
    <MainShell
      title={activeFolder}
      subtitle={activeTag ? `Filtered by ${activeTag}` : `${stats.total_queries} items in library`}
      badge={{
        text: 'Library',
        color: T.text,
        icon: <div style={{ width: 6, height: 6, borderRadius: 0, background: T.text }} />
      }}
      headerActions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Universal Search in Header */}
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: T.text3 }}>
              <HeaderIcons.Search />
            </div>
            <input 
              type="text"
              placeholder="Search library..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: 'min(220px, 36vw)', padding: '8px 12px 8px 32px', borderRadius: 0,
                background: '#fff', border: `1px solid rgba(0,0,0,0.1)`,
                fontSize: '0.78rem', outline: 'none', fontFamily: T.fontBody, color: T.text,
                transition: 'all 0.2s ease',
              }}
              onFocus={e => e.currentTarget.style.borderColor = T.text}
              onBlur={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'}
            />
          </div>
          <button 
            style={{...headerIconBtnStyle, borderRadius: 0}} 
            title="New Folder"
          >
            <HeaderIcons.Plus />
          </button>
          <button 
            style={{...headerActionBtnStyle, borderRadius: 0, background: T.text, color: '#fff', border: 'none'}} 
            title="Import"
          >
            <HeaderIcons.Download /> <span className="header-action-label">Import</span>
          </button>
        </div>
      }
    >
      <div className="responsive-split">
        <FolderSidebar
          folders={folders}
          tags={tags}
          stats={stats}
          activeFolder={activeFolder}
          activeTag={activeTag}
          search={search}
          onFolderChange={(f: string) => { setActiveFolder(f); setSelectedId(null); }}
          onTagChange={(t: string | null) => { setActiveTag(t); setSelectedId(null); }}
          onSearchChange={setSearch}
          onFolderCreated={fetchAll}
        />
        <QueryList
          queries={filteredQueries}
          stats={stats}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={handleDelete}
          onRefresh={fetchAll}
          activeFolder={activeFolder}
        />
      </div>
    </MainShell>
  );
}

const headerActionBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '8px 16px', borderRadius: 0,
  border: `1px solid rgba(0,0,0,0.1)`,
  background: 'transparent',
  color: T.text, fontSize: '0.72rem', fontWeight: 800,
  cursor: 'pointer', fontFamily: T.fontMono,
  textTransform: 'uppercase', letterSpacing: '0.05em',
  transition: 'all 0.2s ease',
};

const headerIconBtnStyle: React.CSSProperties = {
  width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center',
  borderRadius: 0, border: `1px solid rgba(0,0,0,0.1)`, background: '#fff',
  color: T.text2, cursor: 'pointer', transition: 'all 0.2s ease',
};
