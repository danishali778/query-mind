import { useState } from 'react';
import { ChevronDown, Book, SortAsc, Filter } from 'lucide-react';
import { T } from '../dashboard/tokens';
import { QueryCard } from './QueryCard';
import { QueryDetailPanel } from './QueryDetailPanel';
import { PublicLibraryPanel } from './PublicLibraryPanel';
import type { QueryListProps } from '../../types/library';

type SortKey = 'last_run' | 'name_az' | 'most_run' | 'newest' | 'oldest';

function sortQueries(queries: QueryListProps['queries'], key: SortKey) {
  return [...queries].sort((a, b) => {
    switch (key) {
      case 'last_run': return (b.last_run_at ?? '').localeCompare(a.last_run_at ?? '');
      case 'name_az': return a.title.localeCompare(b.title);
      case 'most_run': return (b.run_count ?? 0) - (a.run_count ?? 0);
      case 'newest': return (b.created_at ?? '').localeCompare(a.created_at ?? '');
      case 'oldest': return (a.created_at ?? '').localeCompare(b.created_at ?? '');
      default: return 0;
    }
  });
}

export function QueryList({ queries, stats, selectedId, onSelect, onDelete, onRefresh, activeFolder }: QueryListProps & { activeFolder: string }) {
  const selectedQuery = queries.find(q => q.id === selectedId) || null;
  const [detailTab, setDetailTab] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState<SortKey>('last_run');

  if (activeFolder === 'Public Library') {
    return <PublicLibraryPanel onCloned={onRefresh} />;
  }

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: T.bg }}>

        {/* Toolbar */}
        <div style={{ 
          padding: '16px 24px', 
          background: '#fff', 
          borderBottom: `1px solid rgba(0,0,0,0.08)`, 
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.7rem', color: T.text3, fontFamily: T.fontMono, flex: 1, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <Book size={14} style={{ opacity: 0.5 }} />
            <span>Library</span> 
            <span style={{ opacity: 0.3 }}>/</span> 
            <span style={{ color: T.text, fontWeight: 700 }}>{activeFolder}</span>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <div style={{ position: 'absolute', left: 10, color: T.text3, display: 'flex' }}><SortAsc size={12} /></div>
              <select 
                value={sortBy} 
                onChange={e => setSortBy(e.target.value as SortKey)} 
                style={{ 
                  background: 'transparent', border: `1px solid rgba(0,0,0,0.1)`, borderRadius: 0, 
                  padding: '6px 24px 6px 28px', color: T.text, fontSize: '0.7rem', 
                  fontFamily: T.fontMono, fontWeight: 700, outline: 'none', cursor: 'pointer', 
                  appearance: 'none', textTransform: 'uppercase', letterSpacing: '0.02em'
                }}
              >
                <option value="last_run">Recent</option>
                <option value="name_az">Name A–Z</option>
                <option value="most_run">Popular</option>
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
              </select>
              <div style={{ position: 'absolute', right: 8, color: T.text3, pointerEvents: 'none', display: 'flex' }}><ChevronDown size={12} /></div>
            </div>
            
            <button style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
              borderRadius: 0, border: `1px solid rgba(0,0,0,0.1)`, background: 'transparent',
              color: T.text2, fontSize: '0.7rem', fontWeight: 700, fontFamily: T.fontMono,
              textTransform: 'uppercase'
            }}>
              <Filter size={12} /> Filter
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }} className="custom-scroll">
          {/* Stats Bar */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
            {[
              { val: String(stats.total_queries), label: 'QUERIES' },
              { val: String(stats.scheduled), label: 'ACTIVE TASKS' },
              { val: String(stats.total_runs), label: 'EXECUTIONS' },
            ].map((s, i) => (
              <div key={i} style={{ 
                display: 'flex', flexDirection: 'column', gap: 2, 
                background: '#fff', border: `1px solid rgba(0,0,0,0.08)`, 
                borderRadius: 0, padding: '10px 16px', minWidth: 100 
              }}>
                <span style={{ color: T.text3, fontSize: '0.58rem', fontWeight: 800, fontFamily: T.fontMono, letterSpacing: '0.1em' }}>{s.label}</span>
                <span style={{ color: T.text, fontWeight: 900, fontSize: '1.1rem', fontFamily: T.fontHead, fontStyle: 'italic' }}>{s.val}</span>
              </div>
            ))}
          </div>

          {/* Grid / Empty State */}
          {queries.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {sortQueries(queries, sortBy).map((q, index) => (
                <QueryCard
                  key={q.id}
                  data={q}
                  isSelected={selectedId === q.id}
                  onClick={() => { setDetailTab(undefined); onSelect(q.id); }}
                  onScheduleClick={() => { setDetailTab('schedule'); onSelect(q.id); }}
                  index={index}
                />
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '100px 20px', background: 'rgba(0,0,0,0.01)', border: `1px dashed rgba(0,0,0,0.08)` }}>
              <div style={{ fontSize: '2.5rem', marginBottom: 16, opacity: 0.3 }}>📖</div>
              <div style={{ 
                fontSize: '1.2rem', fontWeight: 900, color: T.text, marginBottom: 8,
                fontFamily: T.fontHead, fontStyle: 'italic'
              }}>Archive is Empty</div>
              <div style={{ fontSize: '0.85rem', lineHeight: 1.7, color: T.text3, maxWidth: 400, margin: '0 auto' }}>
                Your saved queries and automated tasks will appear here. Start an investigation in Chat to populate your archive.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail Panel */}
      <QueryDetailPanel
        query={selectedQuery}
        onClose={() => { setDetailTab(undefined); onSelect(null); }}
        onDelete={onDelete}
        onRefresh={onRefresh}
        initialTab={detailTab}
      />
    </div>
  );
}
