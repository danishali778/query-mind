import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  ArrowDownToLine, 
  Maximize2, 
  RotateCw, 
  TrendingUp, 
  TrendingDown,
  MoreHorizontal,
  ChevronDown,
} from 'lucide-react';
import { refreshDashboardWidget, getWidgetInsight } from '../../services/api';
import { T } from './tokens';
import type { DashboardWidgetItem } from '../../types/dashboard';
import { resolveWidgetSize } from '../../types/dashboard';
import type { UpdateDashboardWidgetRequest } from '../../types/api';
import { DashboardBarChart } from './charts/DashboardBarChart';
import { DashboardLineChart } from './charts/DashboardLineChart';
import { DashboardAreaChart } from './charts/DashboardAreaChart';
import { DashboardPieChart } from './charts/DashboardPieChart';
import { exportToPNG, exportToCSV } from '../../utils/exportUtils';


const CHART_TYPES = [
  { key: 'bar', label: 'Bar', icon: '▥' },
  { key: 'line', label: 'Line', icon: '⟋' },
  { key: 'area', label: 'Area', icon: '▨' },
  { key: 'pie', label: 'Pie', icon: '◕' },
] as const;

type ChartType = 'bar' | 'line' | 'area' | 'pie' | 'donut';

/* ── SVG Icons ───────────────────────────────────────────────── */

function IconClose() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconZap({ style }: { style?: React.CSSProperties }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={style}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

/* ── Utility Functions ───────────────────────────────────────── */

function formatColHeader(col: string) {
  return col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMetric(value: unknown) {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toLocaleString();
  }
  return String(value ?? '-');
}

function widgetBadge(vizType: string) {
  const map: Record<string, { bg: string; color: string; label: string; borderColor: string }> = {
    kpi:     { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'METRIC',  borderColor: 'rgba(0,0,0,0.1)' },
    bar:     { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'BAR',     borderColor: 'rgba(0,0,0,0.1)' },
    line:    { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'LINE',    borderColor: 'rgba(0,0,0,0.1)' },
    area:    { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'AREA',    borderColor: 'rgba(0,0,0,0.1)' },
    scatter: { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'SCATTER', borderColor: 'rgba(0,0,0,0.1)' },
    donut:   { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'DONUT',   borderColor: 'rgba(0,0,0,0.1)' },
    table:   { bg: '#fdfcfb',   color: '#1a1a1a',  label: 'TABLE',   borderColor: 'rgba(0,0,0,0.1)' },
  };
  return map[vizType] || map.table;
}


/* ── Premium UI Helpers ───────────────────────────────────────── */

function LiveIndicator() {
  return (
    <span style={{ 
      display: 'inline-flex', alignItems: 'center', gap: 6, 
      color: T.text3, fontSize: '0.62rem', fontWeight: 700,
      fontFamily: T.fontMono, marginLeft: 8,
      letterSpacing: '0.05em'
    }}>
      <span className="live-indicator-pulse" style={{
        width: 5, height: 5, borderRadius: '50%', background: T.accent,
        boxShadow: `0 0 8px ${T.accent}40`
      }} />
      LIVE
    </span>
  );
}

function Typewriter({ text, speed = 15 }: { text: string; speed?: number }) {
  const [displayedText, setDisplayedText] = useState('');
  
  useEffect(() => {
    let i = 0;
    setDisplayedText('');
    const timer = setInterval(() => {
      setDisplayedText((prev) => prev + text.charAt(i));
      i++;
      if (i >= text.length) clearInterval(timer);
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed]);

  return <MarkdownLite text={displayedText} />;
}

function MarkdownLite({ text }: { text: string }) {
  // Simple regex-based formatter for **bold**, - list, and line breaks
  const parts = text.split(/(\*\*.*?\*\*|- .*?\n|\n)/g);
  
  return (
    <div style={{ lineHeight: 1.6 }}>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} style={{ color: T.text, fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('- ')) {
          return <div key={i} style={{ display: 'flex', gap: 8, paddingLeft: 4, margin: '4px 0' }}>
            <span style={{ color: T.accent }}>•</span>
            <span>{part.slice(2)}</span>
          </div>;
        }
        if (part === '\n') {
          return <br key={i} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

/* ── Table Viz ────────────────────────────────────────────────── */

function TableViz({ columns, rows, compact }: { columns: string[]; rows: Array<Record<string, unknown>>; compact: boolean }) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  // Detection logic for special columns
  const isRankCol = (col: string, index: number) => index === 0 && (col.toLowerCase().includes('rank') || col === '#' || col.toLowerCase() === 'id');
  const isTrendCol = (val: any) => typeof val === 'string' && (val.includes('%') || val.startsWith('+') || val.startsWith('-'));
  const isShareCol = (col: string) => col.toLowerCase().includes('share') || col.toLowerCase().includes('ratio');

  const renderCellContent = (col: string, val: any, index: number) => {
    if (val === null || val === undefined || val === '') {
      return <span style={{ color: T.text3, fontStyle: 'italic', opacity: 0.6 }}>--</span>;
    }

    const strVal = String(val);

    // 1. Rank Badge
    if (isRankCol(col, index)) {
      const rank = parseInt(strVal);
      if (!isNaN(rank)) {
        const isTop3 = rank <= 3;
        return (
          <div style={{ 
            width: 24, height: 24, borderRadius: '50%', 
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: isTop3 ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.05)',
            border: `1px solid ${isTop3 ? 'rgba(245, 158, 11, 0.3)' : 'rgba(255,255,255,0.1)'}`,
            color: isTop3 ? '#f59e0b' : T.text3,
            fontSize: '0.7rem', fontWeight: 700,
            fontFamily: T.fontMono
          }}>
            {rank}
          </div>
        );
      }
    }

    // 2. Trend Badge
    if (isTrendCol(strVal)) {
      const isUp = strVal.includes('+') || (!strVal.includes('-') && parseFloat(strVal) > 0);
      const isDown = strVal.includes('-');
      const color = isUp ? '#22d3a5' : isDown ? '#f87171' : T.text3;
      
      return (
        <div style={{ 
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '2px 8px', borderRadius: 6,
          background: `${color}15`, border: `1px solid ${color}30`,
          color: color, fontSize: '0.68rem', fontWeight: 600
        }}>
          {isUp && <TrendingUp size={10} />}
          {isDown && <TrendingDown size={10} />}
          {strVal}
        </div>
      );
    }

    // 3. Share Bar
    if (isShareCol(col)) {
      const numericVal = parseFloat(strVal.replace('%', ''));
      if (!isNaN(numericVal)) {
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%' }}>
            <div style={{ 
              flex: 1, height: 4, background: 'rgba(255,255,255,0.05)', 
              borderRadius: 2, overflow: 'hidden', maxWidth: 80 
            }}>
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(numericVal, 100)}%` }}
                transition={{ duration: 1, ease: "easeOut" }}
                style={{ 
                  height: '100%', 
                  background: T.text,
                }} 
              />
            </div>
            <span style={{ fontSize: '0.7rem', color: T.text2, fontFamily: T.fontMono }}>{strVal}</span>
          </div>
        );
      }
    }

    return strVal;
  };

  return (
    <div 
      ref={scrollContainerRef}
      className="hide-scrollbar"
      style={{ 
        overflowY: 'auto', 
        maxHeight: compact ? 280 : 500,
        position: 'relative',
        borderRadius: '0 0 12px 12px'
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
        <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
          <tr>
            {columns.map((col, idx) => (
              <th key={col} style={{
                background: 'rgba(255, 255, 255, 0.7)',
                backdropFilter: 'blur(8px)',
                color: T.text2, fontFamily: T.fontMono,
                fontSize: '0.62rem', textTransform: 'uppercase', textAlign: 'left',
                padding: '14px 16px', borderBottom: `1px solid ${T.border}`,
                whiteSpace: 'nowrap', letterSpacing: 1,
                borderRight: idx === columns.length - 1 ? 'none' : `1px solid rgba(0,0,0,0.03)`
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {formatColHeader(col)}
                  {col.toLowerCase().includes('revenue') && <ChevronDown size={10} style={{ opacity: 0.5 }} />}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <motion.tr
              key={rowIndex}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: rowIndex * 0.03 }}
              style={{ 
                background: rowIndex % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                e.currentTarget.style.boxShadow = 'inset 0 0 20px rgba(0,229,255,0.02)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = rowIndex % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              {columns.map((col, colIndex) => {
                const cellValue = row[col];
                return (
                  <td key={colIndex} style={{
                    padding: '12px 16px', borderBottom: `1px solid rgba(255,255,255,0.03)`,
                    color: colIndex === 1 ? T.text : T.text2, 
                    fontWeight: colIndex === 1 ? 600 : 400,
                    fontFamily: colIndex === 1 ? T.fontBody : T.fontMono,
                    fontSize: '0.78rem',
                    maxWidth: 300,
                  }}>
                    <motion.div 
                      layout
                      style={{ 
                        overflow: 'hidden', textOverflow: 'ellipsis', 
                        whiteSpace: 'nowrap',
                        transition: 'white-space 0.2s ease'
                      }}
                      onMouseEnter={e => {
                        const target = e.currentTarget as HTMLDivElement;
                        if (target.scrollWidth > target.clientWidth) {
                          target.style.whiteSpace = 'normal';
                        }
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLDivElement).style.whiteSpace = 'nowrap';
                      }}
                    >
                      {renderCellContent(col, cellValue, colIndex)}
                    </motion.div>
                  </td>
                );
              })}
            </motion.tr>
          ))}
        </tbody>
      </table>
      
      {rows.length === 0 && (
        <div style={{ 
          padding: '40px 0', textAlign: 'center', color: T.text3,
          fontFamily: T.fontMono, fontSize: '0.75rem' 
        }}>
          No data available for this view
        </div>
      )}
    </div>
  );
}

/* ── KPI Card ─────────────────────────────────────────────────── */

function Sparkline({ rows, yColumn, color }: { rows: Array<Record<string, unknown>>; yColumn?: string; color: string }) {
  if (!yColumn || rows.length < 2) {
    return <div style={{ height: 40, borderTop: `1px dashed ${T.border}`, marginTop: 4 }} />;
  }
  const values = rows.slice(-16).map((r) => Number(r[yColumn] ?? 0));
  const maxV = Math.max(...values, 1);
  const minV = Math.min(...values, 0);
  const range = maxV - minV || 1;
  const w = 260, h = 46;
  const points = values.map((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * (w - 2) + 1;
    const y = h - ((v - minV) / range) * (h - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  const gradId = `spark-${color.replace('#', '')}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 40 }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.2} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon
        points={`${points} ${w - 1},${h} 1,${h}`}
        fill={`url(#${gradId})`}
      />
      <polyline points={points} fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function KpiCard({ widget, onDelete }: {
  widget: DashboardWidgetItem;
  onDelete: (id: string) => void;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const metricCol = (widget.chart_config?.y_columns || []).find(Boolean)
    || widget.columns.find((c) => widget.rows.some((r) => typeof r[c] === 'number'));
  const primaryRow = widget.rows[widget.rows.length - 1] || widget.rows[0] || {};
  const metric = metricCol ? primaryRow[metricCol] : undefined;

  return (
    <motion.div 
      layout
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="widget-card widget-drag-handle" 
      style={{
        background: '#fff',
        border: `1px solid ${isHovered ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.08)'}`, 
        borderRadius: 0, // Structured lines
        overflow: 'hidden', 
        minHeight: 190,
        height: '100%',
        cursor: 'grab',
        boxShadow: isHovered ? '0 12px 30px rgba(0,0,0,0.03)' : 'none',
        zIndex: isHovered ? 10 : 1,
        transition: 'all 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative'
      }}
    >
      <div style={{
        padding: '24px 24px 12px', display: 'flex',
        alignItems: 'flex-start', gap: 10,
      }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <div style={{
            fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono,
            letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8
          }}>
            Metric
          </div>
          <motion.div 
            layout
            style={{
              fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.25rem',
              color: T.text, 
              whiteSpace: isHovered ? 'normal' : 'nowrap', 
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: 1.1,
              fontStyle: 'italic'
            }}
          >
            {widget.title}
          </motion.div>
        </div>
        <button
          className="dash-action-btn"
          onClick={(e) => { e.stopPropagation(); onDelete(widget.id); }}
          style={{ 
            width: 32, height: 32, borderRadius: '50%',
            background: 'transparent', border: '1px solid rgba(0,0,0,0.05)',
            display: isHovered ? 'flex' : 'none',
            alignItems: 'center', justifyContent: 'center'
          }}
          title="Remove widget"
        >
          <IconClose />
        </button>
      </div>
      <motion.div layout style={{ padding: '0 24px 12px', flex: 1 }}>
        <div style={{
          fontFamily: T.fontHead, fontWeight: 900, fontSize: '3.2rem',
          color: T.text, letterSpacing: '-0.02em', lineHeight: 0.9,
          margin: '12px 0'
        }}>
          {formatMetric(metric)}
        </div>
        <div style={{ 
          fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono,
          letterSpacing: '0.05em', textTransform: 'uppercase'
        }}>
          {metricCol || 'value'}
        </div>
      </motion.div>
      <motion.div layout style={{ padding: '0 0 0 0', borderTop: '1px solid rgba(0,0,0,0.05)' }}>
        <Sparkline rows={widget.rows} yColumn={metricCol} color={T.text} />
      </motion.div>
    </motion.div>
  );
}

/* ── Main Widget Renderer ────────────────────────────────────── */

export function WidgetRenderer({
  widget,
  onDelete,
  onUpdateWidget,
}: {
  widget: DashboardWidgetItem;
  onDelete: (id: string) => void;
  onUpdateWidget: (id: string, patch: UpdateDashboardWidgetRequest) => void;
}) {
  const size = resolveWidgetSize(widget.size, widget.viz_type, widget.rows.length);
  const badge = widgetBadge(widget.viz_type);

  const isChartType = (t: string): t is ChartType => ['bar', 'line', 'area', 'pie'].includes(t);
  const initialType: ChartType = isChartType(widget.viz_type) ? widget.viz_type : 'bar';
  const [chartType, setChartType] = useState<ChartType>(initialType);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(widget.title);
  const [refreshing, setRefreshing] = useState(false);
  const [insight, setInsight] = useState<string | null>(null);
  const [loadingInsight, setLoadingInsight] = useState(false);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const commitTitle = () => {
    setEditingTitle(false);
    if (titleValue.trim() && titleValue.trim() !== widget.title) {
      onUpdateWidget(widget.id, { title: titleValue.trim() });
    } else {
      setTitleValue(widget.title);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const updated = await refreshDashboardWidget(widget.id);
      onUpdateWidget(widget.id, { columns: updated.columns, rows: updated.rows } as UpdateDashboardWidgetRequest);
    } finally {
      setRefreshing(false);
    }
  };

  const handleGetInsight = async () => {
    if (insight) {
      setInsight(null);
      return;
    }
    setLoadingInsight(true);
    try {
      const res = await getWidgetInsight(widget.id);
      setInsight(res.insight);
    } catch (err) {
      console.error('Insight failed:', err);
    } finally {
      setLoadingInsight(false);
    }
  };

  const handleExportPNG = async () => {
    await exportToPNG(`widget-${widget.id}`, `${widget.title}_Chart`);
  };

  const handleExportCSV = () => {
    exportToCSV(widget.rows, `${widget.title}_Data`);
  };

  if (widget.viz_type === 'kpi') {
    return <KpiCard widget={widget} onDelete={onDelete} />;
  }

   const onToggleSize = () => {
    const isPie = widget.viz_type === 'pie' || widget.viz_type === 'donut' || chartType === 'pie' || chartType === 'donut';
    let nextW = 10;
    let nextH = 7; // Standard Height

    if (isPie) {
      if (widget.w >= 10) {
        nextW = 7; // ~35%
        nextH = 7; 
      } else {
        nextW = 10; // 50%
        nextH = 7;
      }
    } else {
      if (widget.w < 10) {
        nextW = 10; // 50%
        nextH = 7;
      } else if (widget.w >= 10 && widget.w < 13) {
        nextW = 13; // 65%
        nextH = 7;
      } else if (widget.w >= 13 && widget.w < 20) {
        nextW = 20; // 100%
        nextH = 7;
      } else {
        nextW = 10; // Back to 50%
        nextH = 7;
      }
    }

    onUpdateWidget(widget.id, { w: nextW, h: nextH });
  };

  const isChart = widget.viz_type !== 'table';
  const canRefresh = !!(widget.sql && widget.connection_id);

  return (
    <div className="widget-card" style={{
      background: '#fff',
      border: `1px solid rgba(0,0,0,0.08)`, 
      borderRadius: 0, 
      overflow: 'hidden',
      display: 'flex', flexDirection: 'column', height: '100%',
      boxShadow: 'none',
    }}>
      {/* Header */}
      <div className="widget-drag-handle" style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '16px 20px',
        borderBottom: `1px solid rgba(0,0,0,0.05)`,
        cursor: 'grab',
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {editingTitle ? (
            <input
              ref={titleInputRef}
              autoFocus
              value={titleValue}
              onChange={e => setTitleValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') commitTitle();
                else if (e.key === 'Escape') { setTitleValue(widget.title); setEditingTitle(false); }
              }}
              onBlur={commitTitle}
              style={{
                width: '100%', background: '#fff',
                border: '1px solid rgba(0,0,0,0.1)',
                borderRadius: 0, padding: '4px 10px',
                color: T.text, fontFamily: T.fontHead,
                fontWeight: 700, fontSize: '1rem', outline: 'none',
                fontStyle: 'italic'
              }}
            />
          ) : (
            <div
              title="Double-click to rename"
              onDoubleClick={() => { setEditingTitle(true); setTimeout(() => titleInputRef.current?.select(), 0); }}
              style={{
                fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.1rem',
                color: T.text, whiteSpace: 'nowrap', overflow: 'hidden',
                textOverflow: 'ellipsis', cursor: 'text',
                fontStyle: 'italic'
              }}
            >
              {titleValue}
            </div>
          )}
          <div style={{
            fontSize: '0.6rem', color: T.text3, fontFamily: T.fontMono,
            marginTop: 4, display: 'flex', alignItems: 'center', gap: 8,
            letterSpacing: '0.05em', textTransform: 'uppercase'
          }}>
            <span>{widget.rows.length} OBSERVATIONS</span>
            <span style={{
              width: 3, height: 3, borderRadius: '50%',
              background: 'rgba(0,0,0,0.1)', display: 'inline-block',
            }} />
            <span>{widget.cadence.toUpperCase()}</span>
            {widget.cadence !== 'Manual only' && <LiveIndicator />}
          </div>
        </div>

        {/* Chart type switcher */}
        {isChart && (
          <div style={{
            display: 'flex', gap: 1,
            background: 'rgba(0,0,0,0.03)', borderRadius: 0,
            padding: 1, border: `1px solid rgba(0,0,0,0.05)`,
          }}>
            {CHART_TYPES.map((t) => (
              <button
                key={t.key}
                onClick={() => {
                  setChartType(t.key);
                  onUpdateWidget(widget.id, { viz_type: t.key });
                }}
                title={t.label}
                style={{
                  padding: '4px 12px', borderRadius: 0,
                  border: 'none',
                  background: chartType === t.key
                    ? '#fff'
                    : 'transparent',
                  color: T.text,
                  fontSize: '0.62rem', cursor: 'pointer',
                  fontFamily: T.fontMono, fontWeight: 800,
                  transition: 'all 0.2s ease',
                  letterSpacing: '0.05em',
                  boxShadow: chartType === t.key ? '0 2px 8px rgba(0,0,0,0.05)' : 'none'
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}

        {/* Size toggle */}
        <button
          className="dash-action-btn"
          onClick={onToggleSize}
          style={{ width: 26, height: 26 }}
          title={(() => {
            const isPie = widget.viz_type === 'pie' || widget.viz_type === 'donut' || chartType === 'pie' || chartType === 'donut';
            if (isPie) {
              return widget.size === 'half' ? 'Collapse to 35% width' : 'Expand to 50% width';
            }
            return widget.size === 'half' ? 'Expand to 65% width' : widget.size === 'three-quarter' ? 'Expand to full width' : 'Collapse to 50% width';
          })()}
        >
          <Maximize2 size={12} />
        </button>

        {/* Badge */}
        <span className="viz-badge" style={{
          background: badge.bg, color: badge.color,
          border: `1px solid ${badge.borderColor}`,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          fontWeight: 800,
          fontSize: '0.6rem',
          padding: '2px 8px',
          borderRadius: 4
        }}>
          {badge.label}
        </span>

        {/* AI Insight */}
        <button
          className="dash-action-btn"
          onClick={handleGetInsight}
          disabled={loadingInsight}
          title="Get AI insights"
          style={{
            width: 26, height: 26,
            color: (insight || loadingInsight) ? T.accent : T.text3,
            background: (insight || loadingInsight) ? 'rgba(0,229,255,0.1)' : 'transparent',
            border: (insight || loadingInsight) ? '1px solid rgba(0,229,255,0.2)' : '1px solid transparent',
          }}
        >
          {loadingInsight ? <RotateCw size={12} className="refresh-spin" /> : '✨'}
        </button>

        {/* Refresh */}
        {canRefresh && (
          <button
            className="dash-action-btn"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh data"
            style={{
              width: 26, height: 26,
              color: refreshing ? T.accent : undefined,
              cursor: refreshing ? 'default' : 'pointer',
            }}
          >
            <RotateCw size={12} className={refreshing ? 'refresh-spin' : ''} />
          </button>
        )}

        {/* Exports */}
        <button
          className="dash-action-btn"
          onClick={handleExportPNG}
          title="Export as Image (PNG)"
          style={{ width: 26, height: 26 }}
        >
          <ArrowDownToLine size={13} />
        </button>

        <button
          className="dash-action-btn"
          onClick={handleExportCSV}
          title="Export Data (CSV/Excel)"
          style={{ width: 26, height: 26 }}
        >
          <div style={{ position: 'relative' }}>
            <ArrowDownToLine size={13} />
            <span style={{ 
              position: 'absolute', bottom: -2, right: -2, 
              fontSize: '0.42rem', fontWeight: 900, color: T.accent,
              background: T.s1, borderRadius: 2, padding: '0 1px',
              border: `1px solid ${T.border}`
            }}>CSV</span>
          </div>
        </button>

        <button
          className="dash-action-btn"
          onClick={() => {}} // Handle more actions
          title="More Actions"
          style={{ width: 26, height: 26 }}
        >
          <MoreHorizontal size={14} />
        </button>

        {/* Delete */}
        <button
          className="dash-action-btn dash-action-btn--danger"
          onClick={() => onDelete(widget.id)}
          style={{ width: 26, height: 26 }}
          title="Remove widget"
        >
          <IconClose />
        </button>
      </div>

      {/* Insight Panel */}
      {insight && (
        <div 
          className="insight-panel-premium"
          style={{
            padding: '16px 20px',
            background: 'linear-gradient(135deg, rgba(0,229,255,0.06), rgba(124,58,255,0.04))',
            borderBottom: `1px solid ${T.border}`,
            fontSize: '0.78rem',
            lineHeight: 1.6,
            color: T.text2,
            position: 'relative'
          }}
        >
          <div style={{ 
            display: 'flex', alignItems: 'center', gap: 8, 
            marginBottom: 10, color: T.accent, 
            fontWeight: 800, fontSize: '0.68rem', textTransform: 'uppercase',
            fontFamily: T.fontHead, letterSpacing: 0.5
          }}>
            <IconZap style={{ width: 14, height: 14 }} />
            <span>✨ AI ANALYSIS</span>
            <div style={{ flex: 1 }} />
            <button 
              onClick={() => setInsight(null)}
              style={{ background: 'transparent', border: 'none', color: T.text3, cursor: 'pointer', fontSize: '1rem', padding: '0 4px' }}
            >✕</button>
          </div>
          <Typewriter text={insight} />
        </div>
      )}

      {/* Body */}
      <div style={{ padding: isChart ? '0 0 12px' : '12px 16px 16px', position: 'relative', height: isChart ? 320 : 'auto' }}>
        {isChart && chartType === 'bar' && <DashboardBarChart widget={widget} size={size} />}
        {isChart && chartType === 'line' && <DashboardLineChart widget={widget} size={size} />}
        {isChart && chartType === 'area' && <DashboardAreaChart widget={widget} size={size} />}
        {isChart && (chartType === 'pie' || chartType === 'donut') && <DashboardPieChart widget={widget} size={size} />}
        {widget.viz_type === 'table' && <TableViz columns={widget.columns} rows={widget.rows} compact={size !== 'full'} />}
      </div>
    </div>
  );
}
