import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import 'react-grid-layout/css/styles.css';
import { MainShell } from '../components/common/MainShell';
import { HeaderIcons } from '../components/common/AppHeader';
import { DashboardCreateForm } from '../components/dashboard/DashboardCreateForm';
import { WidgetRenderer } from '../components/dashboard/WidgetRenderer';
import { T } from '../components/dashboard/tokens';
import { DashboardFilterBar } from '../components/dashboard/DashboardFilterBar';
import {
  deleteDashboard,
  renameDashboard,
  updateDashboard,
  refreshDashboardWidget,
  listDashboardWidgets,
  deleteDashboardWidget,
  getDashboardStats,
  updateDashboardWidget,
} from '../services/api';
import { useDashboardCatalog } from '../hooks/useDashboardCatalog';
import type { DashboardItem, DashboardMetrics, DashboardWidgetItem } from '../types/dashboard';
import type { UpdateDashboardWidgetRequest } from '../types/api';
import { DeleteDashboardModal } from '../components/dashboard/DeleteDashboardModal';

/* ── SVG Icons ─────────────────────────────────────────────────── */

function IconGrid() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function IconTrash() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function IconDashboard() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  );
}

/* ── Dashboard Sidebar Rail ─────────────────────────────────────── */

function DashboardRail({
  dashboards,
  activeDashId,
  onSelect,
  onDelete,
  onRename,
  showCreateForm,
  onShowCreateForm,
  newDashName,
  onNewDashNameChange,
  onCreate,
  onCancelCreate,
  creating,
  externalHover,
}: {
  dashboards: DashboardItem[];
  activeDashId: string | null;
  onSelect: (id: string) => void;
  onDelete: (dashboard: DashboardItem) => void;
  onRename: (id: string, name: string) => void;
  showCreateForm: boolean;
  onShowCreateForm: () => void;
  newDashName: string;
  onNewDashNameChange: (value: string) => void;
  onCreate: () => void;
  onCancelCreate: () => void;
  creating: boolean;
  externalHover: boolean;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isHovered, setIsHovered] = useState(false);

  const startEdit = (e: React.MouseEvent, dash: DashboardItem) => {
    e.stopPropagation();
    setEditingId(dash.id);
    setEditValue(dash.name);
  };

  const commitEdit = (id: string) => {
    if (editValue.trim()) onRename(id, editValue.trim());
    setEditingId(null);
  };

  const isExpanded = isHovered || editingId !== null || showCreateForm || externalHover;

  return (
    <div style={{ width: 0, flexShrink: 0, position: 'relative', zIndex: 40 }}>
      {/* Absolute positioning container for overlay collapse effect */}
      <div
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          position: 'absolute',
          top: 0, left: 0, bottom: 0,
          width: isExpanded ? 240 : 20,
          background: isExpanded ? T.s1 : 'transparent',
          backdropFilter: isExpanded ? 'blur(20px)' : 'none',
          boxShadow: isExpanded ? `12px 0 40px ${T.bg}dd` : 'none',
          borderRight: isExpanded ? `1px solid ${T.border}` : 'transparent',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          transition: 'all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)',
          whiteSpace: 'nowrap',
          zIndex: 100
        }}
      >
        {/* Subtle texture overlay for sidebar */}
        {isExpanded && (
          <div style={{ 
            position: 'absolute', inset: 0, 
            backgroundImage: `radial-gradient(${T.border} 0.5px, transparent 0.5px)`, 
            backgroundSize: '24px 24px', opacity: 0.15, pointerEvents: 'none' 
          }} />
        )}
        <div style={{
          width: 240, height: '100%', display: 'flex', flexDirection: 'column',
          opacity: isExpanded ? 1 : 0,
          pointerEvents: isExpanded ? 'auto' : 'none',
          transition: 'opacity 0.25s ease',
        }}>
          {/* Rail header */}
          <div style={{
            padding: '24px 20px',
            borderBottom: `1px solid ${T.border}`,
            background: `linear-gradient(180deg, ${T.s2}44, transparent)`,
            position: 'relative'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 0, flexShrink: 0,
                background: T.s2,
                border: `1px solid ${T.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: T.accent,
              }}>
                <IconGrid />
              </div>
              <div style={{
                fontFamily: T.fontHead, fontWeight: 900, fontSize: '0.85rem',
                color: T.text, letterSpacing: '1px', textTransform: 'uppercase', transition: 'opacity 0.3s',
                opacity: isExpanded ? 1 : 0,
              }}>DASHBOARDS</div>
            </div>
            <div style={{
              fontSize: '0.58rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 800,
              paddingLeft: 46, transition: 'opacity 0.3s', letterSpacing: '2px',
              opacity: isExpanded ? 1 : 0,
            }}>{dashboards.length} // ACTIVE_NODES</div>
          </div>

          {/* Dashboard list */}
          <div className="dash-scroll" style={{ flex: 1, overflowY: 'auto', padding: '8px 4px 8px 8px' }}>
            {/* New Dashboard at top */}
            <div style={{ padding: '8px 12px', marginBottom: 12 }}>
              {!showCreateForm ? (
                <button
                  onClick={onShowCreateForm}
                  className="new-dash-cta"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '12px 20px', borderRadius: 0,
                    border: `1px solid ${T.border}`,
                    background: T.s2,
                    cursor: 'pointer', width: '100%',
                    color: T.text,
                    fontFamily: T.fontMono, fontSize: '0.72rem',
                    fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  <div style={{
                    width: 22, height: 22, borderRadius: 0, flexShrink: 0,
                    background: 'transparent',
                    border: `1px solid ${T.accent}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: T.accent
                  }}>
                    <IconPlus />
                  </div>
                  <span style={{ transition: 'opacity 0.3s', opacity: isExpanded ? 1 : 0 }}>
                    NEW_DASHBOARD
                  </span>
                </button>
              ) : (
                <div style={{ transition: 'opacity 0.2s', opacity: isExpanded ? 1 : 0 }}>
                  <DashboardCreateForm
                    value={newDashName}
                    onChange={onNewDashNameChange}
                    onCreate={onCreate}
                    onCancel={onCancelCreate}
                    creating={creating}
                    compact
                    ctaLabel="Add"
                  />
                </div>
              )}
            </div>

            {dashboards.map((dashboard, index) => {
              const isActive = dashboard.id === activeDashId;
              const isEditing = editingId === dashboard.id;
              return (
                <div
                  key={dashboard.id}
                  className={`dash-rail-item ${isActive ? 'dash-rail-item--active' : ''} dash-section`}
                  style={{ animationDelay: `${index * 0.04}s` }}
                  onClick={() => !isEditing && onSelect(dashboard.id)}
                  onMouseEnter={e => {
                    if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.025)';
                  }}
                  onMouseLeave={e => {
                    if (!isActive) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '12px 16px',
                    borderRadius: 0,
                    cursor: isEditing ? 'default' : 'pointer',
                    color: isActive ? T.accent : T.text2,
                    borderLeft: `4px solid ${isActive ? T.accent : 'transparent'}`,
                    background: isActive ? T.s2 : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                  className="dash-rail-item-content"
                >
                  <div style={{
                    width: 32, height: 32, borderRadius: 0, flexShrink: 0,
                    background: isActive ? T.s3 : 'transparent',
                    border: `1px solid ${isActive ? T.accent : T.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: isActive ? T.accent : T.text3,
                    fontSize: '0.85rem', transition: 'all 0.3s ease',
                  }}>
                    {dashboard.icon || <IconDashboard />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0, transition: 'opacity 0.3s', opacity: isExpanded ? 1 : 0 }}>
                    {isEditing ? (
                      <input
                        autoFocus
                        value={editValue}
                        onChange={e => setEditValue(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') commitEdit(dashboard.id);
                          else if (e.key === 'Escape') setEditingId(null);
                        }}
                        onBlur={() => commitEdit(dashboard.id)}
                        onClick={e => e.stopPropagation()}
                        style={{
                          width: '100%', background: T.s2,
                          border: `1px solid ${T.accent}`,
                          borderRadius: 0, padding: '4px 8px',
                          color: T.text, fontFamily: T.fontMono,
                          fontSize: '0.72rem', outline: 'none',
                        }}
                      />
                    ) : (
                      <>
                        <div style={{
                          fontSize: '0.72rem', fontWeight: 900, fontFamily: T.fontMono,
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap', lineHeight: 1.3, letterSpacing: '0.5px',
                          textTransform: 'uppercase'
                        }}>{dashboard.name}</div>
                        <div style={{
                          fontSize: '0.58rem', color: T.text3,
                          fontFamily: T.fontMono, marginTop: 2, fontWeight: 700,
                          letterSpacing: '1px'
                        }}>{dashboard.widget_count} // NODES</div>
                      </>
                    )}
                  </div>
                  {isActive && !isEditing && isExpanded && (
                      <div style={{ display: 'flex', gap: 3 }}>
                        <button
                          className="dash-action-btn"
                          title="Rename"
                          onClick={(e) => startEdit(e, dashboard)}
                          style={{ 
                            width: 24, height: 24, borderRadius: 0, 
                            border: `1px solid ${T.border}`, background: T.s3,
                            color: T.text, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer', transition: 'all 0.2s'
                          }}
                        >
                          <IconEdit />
                        </button>
                        <button
                          className="dash-action-btn dash-action-btn--danger"
                          title="Delete"
                          onClick={(e) => { e.stopPropagation(); onDelete(dashboard); }}
                          style={{ 
                            width: 24, height: 24, borderRadius: 0, 
                            border: `1px solid ${T.border}`, background: T.s3,
                            color: T.red, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer', transition: 'all 0.2s'
                          }}
                        >
                          <IconTrash />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{
            padding: '12px 20px', borderTop: `1px solid ${T.border}`,
            display: 'flex', alignItems: 'center', gap: 10,
            background: T.s2 + '44'
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: 0, flexShrink: 0,
              background: T.green,
              boxShadow: `0 0 10px ${T.green}44`,
              transform: 'rotate(45deg)'
            }} />
            <span style={{
              fontSize: '0.58rem', color: T.text3, fontFamily: T.fontMono,
              transition: 'opacity 0.3s', opacity: isExpanded ? 0.8 : 0,
              fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px'
            }}>SYSTEM_NOMINAL // 778</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Empty State ──────────────────────────────────────────────── */

function EmptyState() {
  return (
    <div className="dash-section" style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      height: '100%', minHeight: 400,
      position: 'relative',
    }}>
      <div style={{
        width: 140, height: 140, borderRadius: 0,
        background: T.s1,
        border: `1px solid ${T.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 40,
        boxShadow: `20px 20px 60px ${T.bg}dd`,
        position: 'relative'
      }}>
        <div style={{ position: 'absolute', top: 8, left: 8, fontSize: '0.5rem', fontFamily: T.fontMono, color: T.text3 }}>000 // NULL</div>
        <IconGrid />
      </div>

      <div style={{
        fontFamily: T.fontHead, fontWeight: 950, fontSize: '2.4rem',
        color: T.text, marginBottom: 16, letterSpacing: '-2px',
        textTransform: 'uppercase', lineHeight: 1
      }}>
        BEGIN INVESTIGATION
      </div>
      <div style={{
        fontSize: '0.75rem', color: T.text3, maxWidth: 400,
        lineHeight: 1.8, textAlign: 'center', marginBottom: 40,
        fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px'
      }}>
        INITIALIZE CUSTOM DASHBOARDS FROM QUERY_RESULTS. RUN A COMMAND IN CHAT TO POPULATE THIS NODE.
      </div>

      <div style={{ display: 'flex', gap: 20 }}>
        <button 
          onClick={() => {}} 
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '16px 32px', borderRadius: 0,
            background: T.text,
            border: 'none',
            color: T.bg, cursor: 'pointer',
            fontFamily: T.fontMono, fontSize: '0.72rem', fontWeight: 950,
            textTransform: 'uppercase', letterSpacing: '2px',
            transition: 'all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)',
          }}
        >
          <HeaderIcons.Plus width={14} height={14} /> CREATE_DASHBOARD
        </button>
      </div>

      {/* Editorial Hint */}
      <div style={{
        marginTop: 48, display: 'flex', alignItems: 'center', gap: 8,
        padding: '12px 20px', borderRadius: 0,
        background: T.s2,
        border: '1px solid rgba(0,0,0,0.05)',
      }}>
        <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          💡 Run a query in Chat → click <strong style={{ color: T.text }}>+ Dashboard</strong> to add widgets
        </span>
      </div>
    </div>
  );
}

const ResponsiveGridLayout = WidthProvider(Responsive);

interface GridLayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

/* ── Dashboard Canvas ─────────────────────────────────────────── */

function DashboardCanvas({
  activeDash,
  stats,
  widgets,
  onDeleteWidget,
  onUpdateWidget,
}: {
  activeDash?: DashboardItem;
  stats: DashboardMetrics;
  widgets: DashboardWidgetItem[];
  onDeleteWidget: (id: string) => void;
  onUpdateWidget: (id: string, patch: UpdateDashboardWidgetRequest) => void;
}) {
  if (!activeDash) return <EmptyState />;

  const [localFilters, setLocalFilters] = useState<Record<string, unknown>>(activeDash.filters || {});
  const [refreshInterval, setRefreshInterval] = useState<number | null>(null); // null = off, otherwise ms

  useEffect(() => {
    setLocalFilters(activeDash.filters || {});
  }, [activeDash.id, activeDash.filters]);

  useEffect(() => {
    if (!refreshInterval) return;

    const interval = setInterval(() => {
      console.log('Live Refreshing Dashboard...');
      widgets.forEach(w => {
        if (w.sql) {
          refreshDashboardWidget(w.id).then((updated) => {
            onUpdateWidget(w.id, { columns: updated.columns, rows: updated.rows } as UpdateDashboardWidgetRequest);
          }).catch((err: unknown) => console.error('Refresh fail:', err));
        }
      });
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, widgets, onUpdateWidget]);

  const handleApplyFilters = async () => {
    try {
      await updateDashboard(activeDash.id, { filters: localFilters });
      window.location.reload();
    } catch (err) {
      console.error('Failed to apply filters:', err);
    }
  };

  const layouts = useMemo(() => {
    return {
      lg: widgets.map((w): GridLayoutItem => {
        const isKPI = w.viz_type === 'kpi';

        let safeW = w.w;
        let safeH = w.h;

        return {
          i: w.id,
          x: w.x,
          y: w.y,
          w: safeW,
          h: safeH,
          minW: isKPI ? 5 : 4,
          minH: isKPI ? 4 : 5
        };
      })
    };
  }, [widgets]);

  const handleLayoutChange = (currentLayout: readonly GridLayoutItem[]) => {
    console.log('🔍 GRID TRIGGERED:', currentLayout.map(i => ({ id: i.i, h: i.h })));
    currentLayout.forEach((item) => {
      const widget = widgets.find(w => w.id === item.i);
      if (widget) {
        if (widget.x !== item.x || widget.y !== item.y || widget.w !== item.w || widget.h !== item.h) {
          onUpdateWidget(item.i, {
            x: item.x,
            y: item.y,
            w: item.w,
            h: item.h
          });
        }
      }
    });
  };

  return (
    <>
      <div className="dash-hero-editorial" style={{
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 40, 
        padding: '60px 0 40px 0',
        position: 'relative',
        borderBottom: `1px solid rgba(0, 0, 0, 0.05)`,
        marginBottom: 40
      }}>
        <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start' }}>
          <div style={{
            width: 80, height: 80, borderRadius: 16, flexShrink: 0,
            background: '#fff',
            border: '1px solid rgba(0,0,0,0.08)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '2rem',
            boxShadow: '0 10px 30px rgba(0,0,0,0.03)',
          }}>
            {activeDash.icon || '📊'}
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{
              fontSize: '0.62rem', 
              color: T.text3, 
              fontFamily: T.fontMono, 
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <span style={{ color: T.text }}>#</span>
              Live Dashboard
            </div>
            
            <div style={{
              fontFamily: T.fontHead, 
              fontStyle: 'italic',
              fontWeight: 900, 
              fontSize: '4.5rem',
              color: T.text, 
              letterSpacing: '-0.02em', 
              lineHeight: 0.9,
              marginBottom: 20,
            }}>{activeDash.name}</div>
            
            <div style={{
              display: 'flex', alignItems: 'center', gap: 20,
            }}>
              <div style={{
                fontSize: '0.7rem', color: T.text2, fontFamily: T.fontMono,
                letterSpacing: '0.05em', fontWeight: 600
              }}>
                <span style={{ color: T.text, fontWeight: 800 }}>{stats.total_widgets}</span> WIDGETS
              </div>

              <div style={{
                fontSize: '0.7rem', color: T.text3, fontFamily: T.fontMono,
                opacity: 0.7
              }}>
                CREATED {new Date(activeDash.created_at).toLocaleDateString().toUpperCase()}
              </div>

              <button 
                onClick={() => setRefreshInterval(refreshInterval ? null : 60000)}
                style={{
                  background: 'transparent', border: 'none', 
                  color: refreshInterval ? T.accent : T.text3,
                  fontSize: '0.68rem', fontFamily: T.fontMono, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: 0, fontWeight: 700, letterSpacing: '0.05em'
                }}
              >
                <div style={{ 
                  width: 6, height: 6, borderRadius: '50%', 
                  background: refreshInterval ? T.accent : T.text3,
                  boxShadow: refreshInterval ? `0 0 10px ${T.accent}40` : 'none',
                }} />
                LIVE REFRESH: {refreshInterval ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>
        </div>

        {/* Breakdown Pills on the Right */}
        <div style={{
          display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'flex-end',
          maxWidth: 400, paddingTop: 60
        }}>
          {Object.entries(stats.viz_breakdown || {}).map(([key, value]) => (
            <div key={key} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: '#fff', 
              border: `1px solid rgba(0,0,0,0.08)`,
              borderRadius: 30, padding: '6px 18px',
              fontSize: '0.7rem', fontFamily: T.fontMono,
              transition: 'all 0.2s ease',
              boxShadow: '0 4px 12px rgba(0,0,0,0.02)',
              cursor: 'default',
            }}>
              <div style={{ 
                width: 5, height: 5, borderRadius: '50%', 
                background: key.toLowerCase() === 'table' ? T.accent : T.purple
              }} />
              <span style={{ color: T.text, fontWeight: 800 }}>{String(value)}</span>
              <span style={{ color: T.text3, letterSpacing: '0.05em', fontWeight: 600 }}>{key.toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>

      <DashboardFilterBar
        filters={localFilters}
        onFiltersChange={setLocalFilters}
        onApply={handleApplyFilters}
      />

      {widgets.length > 0 ? (
        <div id="dashboard-grid" className="dash-section dash-section-d2" style={{ paddingBottom: 14, background: T.bg }}>
          <ResponsiveGridLayout
            layouts={layouts}
            breakpoints={{ lg: 1024, md: 996, sm: 768, xs: 480, xxs: 0 }}
            cols={{ lg: 20, md: 15, sm: 10, xs: 5, xxs: 2 }}
            rowHeight={30}
            draggableHandle=".widget-drag-handle"
            isDraggable={true}
            isResizable={true}
            onLayoutChange={(_, allLayouts) => handleLayoutChange(allLayouts.lg || [])}
            margin={[20, 20]}
          >
            {widgets.map((widget) => (
              <div key={widget.id}>
                <WidgetRenderer
                  widget={widget}
                  onDelete={onDeleteWidget}
                  onUpdateWidget={onUpdateWidget}
                />
              </div>
            ))}
          </ResponsiveGridLayout>

          <div style={{
            border: `1px dashed rgba(0,0,0,0.08)`,
            borderRadius: 14, minHeight: 64,
            color: T.text3, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            fontSize: '0.78rem', marginTop: 16,
            background: 'rgba(0,0,0,0.01)',
            transition: 'all 0.2s ease',
            cursor: 'pointer',
          }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'rgba(0,0,0,0.15)';
              e.currentTarget.style.background = 'rgba(0,0,0,0.02)';
              e.currentTarget.style.color = T.text2;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
              e.currentTarget.style.background = 'rgba(0,0,0,0.01)';
              e.currentTarget.style.color = T.text3;
            }}
          >
            <HeaderIcons.Plus />&nbsp; Add more widgets from Chat using
            <strong style={{ color: T.text, marginLeft: 5 }}>+ Dashboard</strong>
          </div>
        </div>
      ) : (
        <div className="dash-section dash-section-d1" style={{
          border: `1px dashed rgba(0,0,0,0.08)`,
          borderRadius: 18, padding: '55px 40px',
          textAlign: 'center', position: 'relative',
          background: 'rgba(0,0,0,0.005)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 14, position: 'relative' }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,0,0,0.1)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="9" y1="21" x2="9" y2="9" />
            </svg>
          </div>
          <div style={{
            fontFamily: T.fontHead, fontWeight: 700, fontSize: '1.15rem',
            color: T.text, marginBottom: 8, position: 'relative',
          }}>No widgets yet</div>
          <div style={{
            fontSize: '0.82rem', color: T.text3, maxWidth: 340,
            lineHeight: 1.7, margin: '0 auto', position: 'relative',
          }}>
            Run queries in Chat and add your visualizations here to build your dashboard.
          </div>
        </div>
      )}
    </>
  );
}

/* ── Main DashboardPage ─────────────────────────────────────────── */

export function DashboardPage() {
  const { dashboards, reloadDashboards, createNewDashboard, creating } = useDashboardCatalog();
  const [activeDashId, setActiveDashId] = useState<string | null>(null);
  const [widgets, setWidgets] = useState<DashboardWidgetItem[]>([]);
  const [stats, setStats] = useState<DashboardMetrics>({ total_widgets: 0, viz_breakdown: {} });
  const [newDashName, setNewDashName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [dashboardToDelete, setDashboardToDelete] = useState<DashboardItem | null>(null);
  const [sidebarTriggeredHover, setSidebarTriggeredHover] = useState(false);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSidebarHover = (isHovering: boolean) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    if (isHovering) {
      setSidebarTriggeredHover(true);
    } else {
      hoverTimeoutRef.current = setTimeout(() => setSidebarTriggeredHover(false), 150);
    }
  };

  useEffect(() => {
    if (dashboards.length > 0 && !activeDashId) {
      setActiveDashId(dashboards[0].id);
    }
  }, [dashboards, activeDashId]);

  const loadActiveDashboard = useCallback(async () => {
    if (!activeDashId) return;
    try {
      const data = await listDashboardWidgets(activeDashId);
      setWidgets(data);
      const s = await getDashboardStats(activeDashId);
      setStats(s);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    }
  }, [activeDashId]);

  useEffect(() => {
    loadActiveDashboard();
  }, [loadActiveDashboard]);

  const handleCreateDashboard = async () => {
    if (!newDashName.trim()) return;
    try {
      const newDash = await createNewDashboard({ name: newDashName });
      setNewDashName('');
      setShowCreateForm(false);
      setActiveDashId(newDash.id);
    } catch (err) {
      console.error('Failed to create dashboard:', err);
    }
  };

  const handleDeleteWidget = async (id: string) => {
    try {
      await deleteDashboardWidget(id);
      setWidgets(prev => prev.filter(w => w.id !== id));
      loadActiveDashboard();
    } catch (err) {
      console.error('Failed to delete widget:', err);
    }
  };

  const handleUpdateWidget = async (id: string, patch: UpdateDashboardWidgetRequest) => {
    try {
      const updated = await updateDashboardWidget(id, patch);
      setWidgets(prev => prev.map(w => w.id === id ? { ...w, ...updated } : w));
    } catch (err) {
      console.error('Failed to update widget:', err);
    }
  };

  const handleRenameDashboard = async (id: string, name: string) => {
    try {
      await renameDashboard(id, name);
      reloadDashboards();
    } catch (err) {
      console.error('Failed to rename dashboard:', err);
    }
  };

  const handleDeleteDashboard = async () => {
    if (!dashboardToDelete) return;
    try {
      await deleteDashboard(dashboardToDelete.id);
      setDashboardToDelete(null);
      await reloadDashboards();
      if (activeDashId === dashboardToDelete.id) {
        setActiveDashId(null);
      }
    } catch (err) {
      console.error('Failed to delete dashboard:', err);
    }
  };

  const activeDash = dashboards.find(d => d.id === activeDashId);

  return (
    <MainShell
      title={activeDash?.name || 'Dashboards'}
      subtitle=""
      badge={undefined}
      headerActions={
        <>
          <button style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 16px', borderRadius: 0,
            background: 'transparent',
            border: `1px solid ${T.border}`,
            color: T.text2, fontSize: '0.68rem', fontFamily: T.fontMono, fontWeight: 800,
            cursor: 'pointer', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            textTransform: 'uppercase', letterSpacing: '1px'
          }}
            onMouseEnter={e => {
              e.currentTarget.style.background = T.s2;
              e.currentTarget.style.borderColor = T.text2;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.borderColor = T.border;
            }}
          >
            <HeaderIcons.Download width={14} height={14} /> EXPORT_PNG
          </button>
          
          <button style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 24px', borderRadius: 0,
            background: T.text,
            border: 'none',
            color: T.bg, fontSize: '0.68rem', fontFamily: T.fontMono, fontWeight: 950,
            cursor: 'pointer', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            textTransform: 'uppercase', letterSpacing: '2px'
          }}
            onClick={() => setShowCreateForm(true)}
          >
            <HeaderIcons.Plus width={14} height={14} /> NEW_DASHBOARD
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', height: '100%', position: 'relative' }}>
        <DashboardRail
          dashboards={dashboards}
          activeDashId={activeDashId}
          onSelect={setActiveDashId}
          onDelete={setDashboardToDelete}
          onRename={handleRenameDashboard}
          showCreateForm={showCreateForm}
          onShowCreateForm={() => setShowCreateForm(true)}
          newDashName={newDashName}
          onNewDashNameChange={setNewDashName}
          onCreate={handleCreateDashboard}
          onCancelCreate={() => setShowCreateForm(false)}
          creating={creating}
          externalHover={sidebarTriggeredHover}
        />

        <div 
          onMouseEnter={() => handleSidebarHover(true)}
          onMouseLeave={() => handleSidebarHover(false)}
          style={{
            position: 'absolute', top: 0, left: 0, bottom: 0, width: 20, zIndex: 35,
          }}
        />

        <div style={{ flex: 1, padding: '0 0 40px 0', overflowY: 'auto' }}>
          <DashboardCanvas
            activeDash={activeDash}
            stats={stats}
            widgets={widgets}
            onDeleteWidget={handleDeleteWidget}
            onUpdateWidget={handleUpdateWidget}
          />
        </div>
      </div>

      <DeleteDashboardModal
        isOpen={!!dashboardToDelete}
        onClose={() => setDashboardToDelete(null)}
        onConfirm={handleDeleteDashboard}
        dashboardName={dashboardToDelete?.name || ''}
      />
    </MainShell>
  );
}
