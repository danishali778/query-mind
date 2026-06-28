import { useEffect, useRef, useState } from 'react';
import { T } from '../dashboard/tokens';
import { SqlBlock } from '../chat/SqlBlock';
import { listConnections, listPublicTemplates, triggerTemplateGeneration, cloneTemplate } from '../../services/api';
import type { DatabaseConnection, PublicTemplate } from '../../types/api';

const CATEGORIES = ['All', 'Sales', 'Marketing', 'Finance', 'Operations', 'Analytics', 'Users'];

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner: '#22d3a5',
  intermediate: '#f59e0b',
  advanced: '#f87171',
};

interface Props {
  onCloned: () => void;
}

export function PublicLibraryPanel({ onCloned }: Props) {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [status, setStatus] = useState<'not_started' | 'generating' | 'ready' | 'error'>('not_started');
  const [templates, setTemplates] = useState<PublicTemplate[]>([]);
  const [activeCategory, setActiveCategory] = useState('All');
  const [cloning, setCloning] = useState<string | null>(null);
  const [cloned, setCloned] = useState<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load connections on mount
  useEffect(() => {
    listConnections()
      .then(conns => {
        setConnections(conns);
        if (conns.length > 0) setActiveConnectionId(conns[0].id);
      })
      .catch(() => {});
  }, []);

  // Poll for templates whenever active connection changes
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    
    if (!activeConnectionId) {
      setTemplates([]);
      setStatus('not_started');
      return;
    }

    const fetch = async () => {
      try {
        const res = await listPublicTemplates(activeConnectionId);
        setStatus(res.status);
        setTemplates(res.templates);
        
        if (res.status === 'ready' || res.status === 'error') {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        setStatus('error');
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    };

    fetch();
    // Only poll if still generating or not started
    pollRef.current = setInterval(fetch, 3000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeConnectionId]);

  const handleRetry = async () => {
    if (!activeConnectionId) return;
    setStatus('generating');
    setTemplates([]);
    try {
      await triggerTemplateGeneration(activeConnectionId);
      // Polling will continue as long as status is 'generating'
    } catch {
      setStatus('error');
    }
  };

  const handleClone = async (t: PublicTemplate) => {
    if (cloning || cloned.has(t.id) || !activeConnectionId) return;
    setCloning(t.id);
    try {
      await cloneTemplate(t.id, activeConnectionId);
      setCloned(prev => new Set(prev).add(t.id));
      onCloned();
    } catch {
      // silently handle
    } finally {
      setCloning(null);
    }
  };

  const filtered = activeCategory === 'All'
    ? templates
    : templates.filter(t => t.category === activeCategory);

  const activeName = connections.find(c => c.id === activeConnectionId)?.name ?? '';

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: T.bg }}>

      {/* Toolbar */}
      <div style={{ padding: '14px 20px', background: T.s1, borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.78rem', color: T.text3, fontFamily: T.fontMono, flex: 1 }}>
          <span>Library</span>
          <span style={{ opacity: 0.4 }}>›</span>
          <span style={{ color: T.text2 }}>Public Library</span>
        </div>

        {/* Connection selector */}
        {connections.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono }}>Connection:</span>
            <select
              value={activeConnectionId ?? ''}
              onChange={e => setActiveConnectionId(e.target.value)}
              style={{
                background: T.s2, border: `1px solid ${T.border}`, borderRadius: 7,
                padding: '4px 10px', color: T.text2, fontSize: '0.72rem',
                fontFamily: T.fontMono, outline: 'none', cursor: 'pointer',
              }}
            >
              {connections.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }} className="custom-scroll">

        {/* No connections */}
        {connections.length === 0 && (
          <EmptyState
            icon="🔌"
            title="No database connected"
            subtitle="Connect a database first — query-mind will automatically analyze its schema and generate relevant query templates for you."
          />
        )}

        {/* Generating */}
        {connections.length > 0 && status === 'generating' && (
          <GeneratingState connectionName={activeName} />
        )}

        {/* Error */}
        {connections.length > 0 && status === 'error' && (
          <ErrorState connectionName={activeName} onRetry={handleRetry} />
        )}

        {/* Not started (edge case — connect should auto-trigger) */}
        {connections.length > 0 && status === 'not_started' && (
          <EmptyState
            icon="✨"
            title="Ready to generate"
            subtitle={`Click below to analyze the schema of "${activeName}" and generate personalized query templates.`}
            action={{ label: 'Generate Templates', onClick: handleRetry }}
          />
        )}

        {/* Ready */}
        {status === 'ready' && templates.length > 0 && (
          <>
            {/* Category filters */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
              {CATEGORIES.filter(cat => cat === 'All' || templates.some(t => t.category === cat)).map(cat => {
                const active = activeCategory === cat;
                const count = cat === 'All' ? templates.length : templates.filter(t => t.category === cat).length;
                return (
                  <button key={cat} onClick={() => setActiveCategory(cat)} style={{
                    padding: '4px 14px', borderRadius: 20, fontSize: '0.72rem', fontFamily: T.fontMono,
                    cursor: 'pointer', transition: 'all 0.15s',
                    border: `1px solid ${active ? 'rgba(0,229,255,0.3)' : T.border}`,
                    background: active ? T.accentDim : 'transparent',
                    color: active ? T.accent : T.text3,
                  }}>
                    {cat} <span style={{ opacity: 0.6 }}>{count}</span>
                  </button>
                );
              })}
            </div>

            {/* Template grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {filtered.map(t => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  isCloning={cloning === t.id}
                  isCloned={cloned.has(t.id)}
                  onClone={() => handleClone(t)}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 3px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: ${T.s4}; border-radius: 2px; }
      `}</style>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────

function GeneratingState({ connectionName }: { connectionName: string }) {
  const [tick, setTick] = useState(0);
  const messages = [
    'Reading your schema…',
    'Identifying tables and relationships…',
    'Generating relevant queries…',
    'Categorizing by business domain…',
    'Almost ready…',
  ];

  useEffect(() => {
    const t = setInterval(() => setTick(v => v + 1), 2000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 20px', gap: 20 }}>
      <div style={{ position: 'relative', width: 56, height: 56 }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          border: `3px solid ${T.border}`,
          borderTopColor: T.accent,
          animation: 'spin 1s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem',
        }}>✨</div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '0.92rem', fontWeight: 600, color: T.text, marginBottom: 6 }}>
          Analyzing <span style={{ color: T.accent }}>{connectionName}</span>
        </div>
        <div style={{ fontSize: '0.78rem', color: T.text3, fontFamily: T.fontMono, transition: 'all 0.3s' }}>
          {messages[tick % messages.length]}
        </div>
      </div>
      {/* Skeleton cards */}
      <div style={{ width: '100%', maxWidth: 700, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 8 }}>
        {[...Array(4)].map((_, i) => (
          <div key={i} style={{
            height: 140, borderRadius: 12, background: T.s1,
            border: `1px solid ${T.border}`, overflow: 'hidden', position: 'relative',
          }}>
            <div style={{ height: '100%', background: `linear-gradient(90deg, transparent 25%, ${T.s2} 50%, transparent 75%)`, backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite' }} />
          </div>
        ))}
      </div>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
      `}</style>
    </div>
  );
}

function ErrorState({ connectionName, onRetry }: { connectionName: string; onRetry: () => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 20px', gap: 14 }}>
      <div style={{ fontSize: '2rem' }}>⚠️</div>
      <div style={{ fontSize: '0.9rem', fontWeight: 600, color: T.text2 }}>Generation failed</div>
      <div style={{ fontSize: '0.78rem', color: T.text3, textAlign: 'center', maxWidth: 340 }}>
        Could not generate templates for <strong style={{ color: T.text2 }}>{connectionName}</strong>. This may be a temporary LLM issue.
      </div>
      <button onClick={onRetry} style={{
        marginTop: 6, padding: '8px 22px', borderRadius: 8, fontSize: '0.78rem',
        fontFamily: T.fontBody, fontWeight: 600, cursor: 'pointer',
        border: `1px solid rgba(0,229,255,0.25)`, background: T.accentDim, color: T.accent,
      }}>Try Again</button>
    </div>
  );
}

function EmptyState({ icon, title, subtitle, action }: {
  icon: string; title: string; subtitle: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 20px', gap: 12 }}>
      <div style={{ fontSize: '2rem' }}>{icon}</div>
      <div style={{ fontSize: '0.9rem', fontWeight: 600, color: T.text2 }}>{title}</div>
      <div style={{ fontSize: '0.78rem', color: T.text3, textAlign: 'center', maxWidth: 360, lineHeight: 1.6 }}>{subtitle}</div>
      {action && (
        <button onClick={action.onClick} style={{
          marginTop: 8, padding: '8px 22px', borderRadius: 8, fontSize: '0.78rem',
          fontFamily: T.fontBody, fontWeight: 600, cursor: 'pointer',
          border: `1px solid rgba(0,229,255,0.25)`, background: T.accentDim, color: T.accent,
        }}>{action.label}</button>
      )}
    </div>
  );
}

function TemplateCard({ template: t, isCloning, isCloned, onClone }: {
  template: PublicTemplate;
  isCloning: boolean;
  isCloned: boolean;
  onClone: () => void;
}) {
  return (
    <div style={{
      background: T.s1, border: `1px solid ${T.border}`, borderRadius: 12,
      display: 'flex', flexDirection: 'column', overflow: 'hidden', transition: 'border-color 0.2s',
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = T.border2}
      onMouseLeave={e => e.currentTarget.style.borderColor = T.border}
    >
      {/* Header */}
      <div style={{ padding: '14px 16px 10px', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 9, background: t.icon_bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.1rem', flexShrink: 0,
        }}>{t.icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: T.text, fontFamily: T.fontHead, marginBottom: 3 }}>
            {t.title}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: '0.62rem', fontFamily: T.fontMono, padding: '2px 7px', borderRadius: 10,
              border: `1px solid ${t.category_color}33`, color: t.category_color, background: `${t.category_color}12`,
            }}>{t.category}</span>
            <span style={{
              fontSize: '0.62rem', fontFamily: T.fontMono, padding: '2px 7px', borderRadius: 10,
              color: DIFFICULTY_COLOR[t.difficulty], background: `${DIFFICULTY_COLOR[t.difficulty]}12`,
              border: `1px solid ${DIFFICULTY_COLOR[t.difficulty]}33`,
            }}>{t.difficulty}</span>
          </div>
        </div>
      </div>

      {/* Description */}
      <div style={{ padding: '0 16px 10px', fontSize: '0.75rem', color: T.text3, lineHeight: 1.5 }}>
        {t.description}
      </div>

      {/* SQL preview */}
      <div style={{ margin: '0 16px 12px', position: 'relative' }}>
        <div style={{ maxHeight: 110, overflowY: 'hidden', borderRadius: 11 }}>
          <SqlBlock sql={t.sql} mode="card" />
        </div>
        {t.sql.split('\n').length > 4 && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, height: 36,
            background: `linear-gradient(transparent, ${T.s1})`,
            borderRadius: '0 0 11px 11px',
            pointerEvents: 'none',
          }} />
        )}
      </div>

      {/* Tags */}
      {t.tags.length > 0 && (
        <div style={{ padding: '0 16px 10px', display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {t.tags.map(tag => (
            <span key={tag} style={{
              fontSize: '0.62rem', fontFamily: T.fontMono, padding: '2px 7px', borderRadius: 10,
              background: T.s3, color: T.text3, border: `1px solid ${T.border}`,
            }}>#{tag}</span>
          ))}
        </div>
      )}

      {/* Clone button */}
      <div style={{ padding: '10px 16px 14px', marginTop: 'auto' }}>
        <button onClick={onClone} disabled={isCloning || isCloned} style={{
          width: '100%', padding: '8px 0', borderRadius: 8, fontSize: '0.75rem',
          fontFamily: T.fontBody, fontWeight: 600, cursor: isCloned ? 'default' : 'pointer',
          border: `1px solid ${isCloned ? T.green + '44' : 'rgba(0,229,255,0.25)'}`,
          background: isCloned ? `${T.green}18` : T.accentDim,
          color: isCloned ? T.green : T.accent,
          transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          {isCloning ? <>⏳ Cloning…</>
            : isCloned ? <>✓ Cloned to My Library</>
            : <>＋ Clone to My Library</>}
        </button>
      </div>
    </div>
  );
}
