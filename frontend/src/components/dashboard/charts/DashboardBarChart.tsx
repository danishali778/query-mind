import { useRef, useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { T } from '../tokens';
import type { DashboardWidgetItem, WidgetSize } from '../../../types/dashboard';
import type { ChartTooltipProps } from './chartTooltipTypes';

const COLORS = [
  '#00e5ff', '#7c3aff', '#22d3a5', '#f59e0b', '#f87171',
  '#a29bfe', '#fab1a0', '#81ecec', '#34d399', '#fb923c',
  '#e879f9', '#facc15', '#38bdf8', '#4ade80', '#f472b6',
  '#a3e635', '#c084fc', '#2dd4bf', '#ff6b6b', '#fbbf24',
];

const GS = T.border;
const TEXT_STYLE = { fontSize: 10, fill: T.text3, fontWeight: 500, fontFamily: T.fontMono };
const TT_STYLE = {
  borderRadius: 12, border: `1px solid ${T.border}`,
  boxShadow: '0 8px 32px rgba(0,0,0,0.12)', fontSize: '0.75rem',
  background: 'rgba(255, 255, 255, 0.8)', backdropFilter: 'blur(10px)',
  color: T.text, padding: '12px 16px',
};

const CustomTooltip = ({ active, payload, label }: ChartTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div style={TT_STYLE}>
        <div style={{ fontWeight: 800, marginBottom: 8, color: T.text, fontSize: '0.8rem', fontFamily: T.fontHead, letterSpacing: 0.3 }}>
          {label}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {payload.map((p, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: p.fill }} />
                <span style={{ color: T.text2, fontSize: '0.7rem' }}>{p.name}</span>
              </div>
              <span style={{ fontWeight: 700, color: T.text, fontFamily: T.fontMono, fontSize: '0.75rem' }}>
                {formatYValue(Number(p.value) || 0)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

function formatColLabel(col: string) {
  return col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatYValue(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  if (abs < 10 && abs !== 0) return v.toFixed(1);
  return String(Math.round(v));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const XTick = ({ x, y, payload }: any) => {
  const raw = String(payload?.value ?? '');
  const label = raw.length > 7 ? raw.slice(0, 7) + '…' : raw;
  return (
    <g transform={`translate(${x},${y})`}>
      <title>{raw}</title>
      <text dy={4} textAnchor="end" fill={T.text3} fontSize={11} transform="rotate(-45)">
        {label}
      </text>
    </g>
  );
};

export function DashboardBarChart({ widget }: { widget: DashboardWidgetItem; size: WidgetSize }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => setContainerWidth(entries[0].contentRect.width));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Sparse grouped SVG state — must be declared before any early return (React rules of hooks)
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [svgContainerWidth, setSvgContainerWidth] = useState(800);
  const [sparseTooltip, setSparseTooltip] = useState<{
    clientX: number; clientY: number; xVal: string; row: Record<string, unknown>;
  } | null>(null);

  useEffect(() => {
    const el = svgContainerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(e => setSvgContainerWidth(e[0].contentRect.width));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const xCol = widget.chart_config?.x_column || widget.columns[0];
  const colorCol = widget.chart_config?.color_column;
  const isGrouped = widget.chart_config?.is_grouped && !!colorCol;
  let yCols: string[] = widget.chart_config?.y_columns?.length ? widget.chart_config.y_columns : [];

  if (yCols.length === 0 && widget.rows.length > 0) {
    const firstRow = widget.rows[0];
    yCols = widget.columns.filter(c => c !== xCol && typeof firstRow[c] === 'number');
    if (yCols.length === 0) yCols = [widget.columns[1]].filter(Boolean);
  } else if (yCols.length === 0) {
    yCols = [widget.columns[1]].filter(Boolean);
  }

  // Grouped: pivot rows by colorCol so each unique color value becomes a Bar series
  let data: Record<string, unknown>[];
  if (isGrouped && colorCol) {
    const metricCol = yCols[0];
    const pivotMap: Record<string, Record<string, unknown>> = {};
    const catSet = new Set<string>();
    widget.rows.forEach(row => {
      const xVal = String(row[xCol] ?? '');
      const catVal = String(row[colorCol] ?? 'Unknown');
      const val = typeof row[metricCol] === 'number' ? row[metricCol] : parseFloat(String(row[metricCol])) || 0;
      catSet.add(catVal);
      if (!pivotMap[xVal]) pivotMap[xVal] = { [xCol]: xVal };
      pivotMap[xVal][catVal] = val;
    });
    const allCats = Array.from(catSet);
    yCols = allCats;
    // Fill missing combinations with 0 so every category group has the same number of bar slots
    data = Object.values(pivotMap).map(row => {
      const filled = { ...row };
      allCats.forEach(cat => { if (!(cat in filled)) filled[cat] = 0; });
      return filled;
    });
  } else {
    data = widget.rows.map(row => {
      const item: Record<string, unknown> = { [xCol]: row[xCol] };
      yCols.forEach(col => {
        const v = row[col];
        item[col] = typeof v === 'number' ? v : parseFloat(String(v)) || 0;
      });
      return item;
    });
  }

  // Grouped charts need more space per slot since multiple bars sit side by side
  const MIN_BAR_WIDTH = yCols.length > 1 ? 24 : 20;
  const totalBars = data.length * Math.max(1, yCols.length);
  const needsScroll = totalBars * MIN_BAR_WIDTH > containerWidth;
  const fixedWidth = Math.max(600, totalBars * (MIN_BAR_WIDTH + 2));

  // ── Sparse grouped bar chart (custom SVG) ──────────────────────────
  // Activates only when: pivoted grouped data + at least one x-category is missing some series.
  // Recharts allocates empty bar slots for 0-value entries — the custom SVG skips them entirely.
  const isPivotedGrouped = isGrouped && !!colorCol && yCols.length > 1;
  const isGroupedSparse = isPivotedGrouped &&
    data.some(row => yCols.filter(c => (Number(row[c]) || 0) > 0).length < yCols.length);

  if (isGroupedSparse && data.length > 0) {
    const FBW = 14;   // fixed bar width (px) — same for every bar in every group
    const BGAP = 2;   // gap between bars within a group
    const GGAP = 16;  // minimum gap between groups
    const m = { t: 10, r: 20, l: 60, b: 70 };
    const svgH = 260; // Slightly more room for the sparse SVG
    const cH = svgH - m.t - m.b;
    const cW = svgContainerWidth - m.l - m.r;

    const groups = data.map(row => {
      const xVal = String(row[xCol] ?? '');
      const cols = yCols.filter(c => (Number(row[c]) || 0) > 0);
      const innerW = cols.length > 0 ? cols.length * FBW + (cols.length - 1) * BGAP : FBW;
      return { xVal, cols, innerW, row };
    });

    const sumInner = groups.reduce((s, g) => s + g.innerW, 0);
    const needsSVGScroll = sumInner + (groups.length - 1) * GGAP > cW;
    const gap = needsSVGScroll || groups.length < 2
      ? GGAP
      : (cW - sumInner) / (groups.length - 1);
    const svgW = needsSVGScroll
      ? m.l + sumInner + (groups.length - 1) * GGAP + m.r
      : svgContainerWidth;

    const gxs: number[] = [];
    let cx = m.l;
    groups.forEach((g, i) => {
      gxs.push(cx);
      cx += g.innerW + (i < groups.length - 1 ? gap : 0);
    });

    const maxY = Math.max(1, ...yCols.flatMap(c => data.map(r => Number(r[c]) || 0)));
    const rawStep = maxY / 6;
    const mag = Math.pow(10, Math.floor(Math.log10(rawStep || 1)));
    const step = Math.ceil(rawStep / mag) * mag || 1;
    const yTicks: number[] = [];
    for (let t = 0; t <= maxY + step; t += step) yTicks.push(t);
    const yTop = yTicks[yTicks.length - 1];
    const ab = m.t + cH;
    const toY = (v: number) => m.t + cH - (v / yTop) * cH;

    return (
      <>
        {yCols.length > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 14, padding: '8px 16px 0' }}>
            {yCols.map((col, i) => (
              <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono }}>{formatColLabel(col)}</span>
              </div>
            ))}
          </div>
        )}
        <div ref={svgContainerRef} style={{ padding: '8px 16px 0', overflowX: needsSVGScroll ? 'auto' : 'visible' }}>
          <svg width={svgW} height={svgH} style={{ display: 'block', overflow: 'visible' }}>
            {/* Grid lines */}
            {yTicks.map(t => (
              <line key={t} x1={m.l} x2={svgW - m.r} y1={toY(t)} y2={toY(t)}
                stroke={GS} strokeDasharray="3 3" />
            ))}
            {/* Y axis */}
            <line x1={m.l} x2={m.l} y1={m.t} y2={ab} stroke={T.border} />
            {/* X axis */}
            <line x1={m.l} x2={svgW - m.r} y1={ab} y2={ab} stroke={T.border} />
            {/* Y tick labels */}
            {yTicks.map(t => (
              <text key={t} x={m.l - 8} y={toY(t)} textAnchor="end"
                dominantBaseline="middle" fill={T.text3} fontSize={11}>
                {formatYValue(t)}
              </text>
            ))}
            {/* Category groups */}
            {groups.map((g, gi) => {
              const gx = gxs[gi];
              const centerX = gx + g.innerW / 2;
              const short = g.xVal.length > 7 ? g.xVal.slice(0, 7) + '…' : g.xVal;
              const hx = gi === 0 ? gx : gx - gap / 2;
              const hw = gi === 0 || gi === groups.length - 1 ? g.innerW + gap / 2 : g.innerW + gap;
              return (
                <g key={g.xVal + gi}>
                  {/* Invisible hover rect triggers tooltip for the whole group */}
                  <rect x={hx} y={m.t} width={Math.max(1, hw)} height={cH}
                    fill="transparent" style={{ cursor: 'pointer' }}
                    onMouseEnter={e => setSparseTooltip({ clientX: e.clientX, clientY: e.clientY, xVal: g.xVal, row: g.row })}
                    onMouseMove={e => setSparseTooltip(p => p ? { ...p, clientX: e.clientX, clientY: e.clientY } : null)}
                    onMouseLeave={() => setSparseTooltip(null)}
                  />
                  {/* Only render bars for series that have data — no empty slots */}
                  {g.cols.map((col, ci) => {
                    const val = Number(g.row[col]) || 0;
                    const bh = Math.max(1, (val / yTop) * cH);
                    return (
                      <rect key={col}
                        x={gx + ci * (FBW + BGAP)} y={ab - bh}
                        width={FBW} height={bh}
                        fill={COLORS[yCols.indexOf(col) % COLORS.length]}
                        rx={3} opacity={0.85}
                      />
                    );
                  })}
                  {/* X tick label — rotated, truncated, full label on hover */}
                  <g transform={`translate(${centerX},${ab + 4})`}>
                    <title>{g.xVal}</title>
                    <text textAnchor="end" fill={T.text3} fontSize={11}
                      transform="rotate(-45)" dy={4}>{short}</text>
                  </g>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Tooltip — shows all non-zero series for the hovered x-category */}
        {sparseTooltip && (() => {
          const nz = yCols.filter(c => (Number(sparseTooltip.row[c]) || 0) > 0);
          return (
            <div style={{
              position: 'fixed', left: sparseTooltip.clientX + 12, top: sparseTooltip.clientY - 40,
              background: T.s1, border: `1px solid ${T.border}`,
              borderRadius: 8, padding: '10px 14px', pointerEvents: 'none', zIndex: 9999,
              minWidth: 160, boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
            }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: T.text, marginBottom: 8 }}>
                {sparseTooltip.xVal}
              </div>
              {nz.map(c => (
                <div key={c} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
                  <span style={{ fontSize: '0.75rem', color: COLORS[yCols.indexOf(c) % COLORS.length] }}>
                    {formatColLabel(c)}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: T.text2, fontFamily: 'monospace' }}>
                    {formatYValue(Number(sparseTooltip.row[c]) || 0)}
                  </span>
                </div>
              ))}
            </div>
          );
        })()}

      </>
    );
  }
  // ── End sparse SVG — Recharts path for complete (non-sparse) data below ──

  const colMaxes: Record<string, number> = Object.fromEntries(
    yCols.map(c => [c, Math.max(...data.map(d => Math.abs(Number(d[c]) || 0))) || 1])
  );

  const sortedBySca = [...yCols].sort((a, b) => (colMaxes[b] || 0) - (colMaxes[a] || 0));
  const maxVal = colMaxes[sortedBySca[0]] || 1;
  const leftCols = sortedBySca.filter(c => (colMaxes[c] || 0) >= maxVal / 10);
  const rightCols = sortedBySca.filter(c => (colMaxes[c] || 0) < maxVal / 10);
  const needsDualAxis = rightCols.length > 0;
  const getAxisId = (col: string): 'left' | 'right' =>
    needsDualAxis && rightCols.includes(col) ? 'right' : 'left';

  const leftAxisColor = COLORS[yCols.indexOf(leftCols[0]) % COLORS.length];
  const rightAxisColor = needsDualAxis ? COLORS[yCols.indexOf(rightCols[0]) % COLORS.length] : '#fff';
  const chartHeight = 220;

  const AXIS_W = 65;
  const chartMargin = { top: 10, right: needsDualAxis ? 70 : 20, left: 50, bottom: 20 };

  const xAxisLabel = { value: formatColLabel(xCol), position: 'insideBottom' as const, offset: -6, fill: T.text3, fontSize: 10, style: { textAnchor: 'middle' as const } };
  const makeAxisLabel = (value: string, color: string, side: 'left' | 'right') => ({
    value, angle: side === 'left' ? -90 : 90,
    position: (side === 'left' ? 'insideLeft' : 'insideRight') as 'insideLeft' | 'insideRight',
    fill: color, fontSize: 10, opacity: 0.8,
    style: { textAnchor: 'middle' as const },
  });
  const leftAxisLabel = leftCols.map(formatColLabel).join(' / ').substring(0, 22);
  const rightAxisLabel = rightCols.map(formatColLabel).join(' / ').substring(0, 22);
  const singleAxisLabel = formatColLabel(yCols[0] || '').substring(0, 22);

  const renderChart = () => (
    <BarChart data={data} margin={chartMargin} barGap={0} barCategoryGap="12%">
      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GS} opacity={0.3} />
      <XAxis dataKey={xCol} tick={XTick} height={68} axisLine={{ stroke: GS, strokeOpacity: 0.5 }} interval={0} label={xAxisLabel} />
      {needsDualAxis ? (
        <>
          <YAxis yAxisId="left" width={AXIS_W} tickCount={6}
            tick={{ fontSize: 11, fill: leftAxisColor, opacity: 0.75 }}
            axisLine={{ stroke: leftAxisColor, strokeOpacity: 0.45 }}
            tickLine={{ stroke: leftAxisColor, strokeOpacity: 0.3 }}
            tickFormatter={formatYValue} label={makeAxisLabel(leftAxisLabel, leftAxisColor, 'left')} />
          <YAxis yAxisId="right" orientation="right" width={AXIS_W} tickCount={6}
            tick={{ fontSize: 11, fill: rightAxisColor, opacity: 0.75 }}
            axisLine={{ stroke: rightAxisColor, strokeOpacity: 0.45 }}
            tickLine={{ stroke: rightAxisColor, strokeOpacity: 0.3 }}
            tickFormatter={formatYValue} label={makeAxisLabel(rightAxisLabel, rightAxisColor, 'right')} />
        </>
      ) : (
        <YAxis yAxisId="left" width={AXIS_W} tickCount={6} tick={TEXT_STYLE} axisLine={{ stroke: GS, strokeOpacity: 0.5 }} tickFormatter={formatYValue}
          label={makeAxisLabel(singleAxisLabel, T.text3, 'left')} />
      )}
      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,229,255,0.03)' }} />
      {yCols.map((c, i) => (
        <Bar 
          key={c} 
          yAxisId={getAxisId(c)} 
          dataKey={c} 
          fill={COLORS[i % COLORS.length]} 
          radius={[4, 4, 0, 0]} 
          maxBarSize={24} 
          isAnimationActive={true}
          animationDuration={1200}
          animationEasing="ease-out"
        />
      ))}
    </BarChart>
  );

  return (
    <>
      {/* Dual Axis Indicator Slot (Fixed 26px) */}
      {needsDualAxis ? (
        <div style={{ padding: '4px 16px', background: T.accentDim, borderTop: `1px solid ${T.border}`, fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, height: 26, display: 'flex', alignItems: 'center' }}>
          Two y-axes — <span style={{ color: leftAxisColor }}>{leftCols.map(formatColLabel).join(' / ')}</span> left · <span style={{ color: rightAxisColor }}>{rightCols.map(formatColLabel).join(' / ')}</span> right
        </div>
      ) : (
        <div style={{ height: 26 }} />
      )}

      {/* Legend / Spacer Slot (Fixed 40px) */}
      {yCols.length > 1 ? (
        <div className="flex flex-wrap gap-x-4 gap-y-2 px-4 py-2 border-t border-gray-100" style={{ minHeight: 40, borderTop: `1px solid ${T.border}` }}>
          {yCols.map((col, i) => (
            <div key={col} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
              <span className="text-[11px] font-medium text-gray-500" style={{ color: T.text3 }}>{formatColLabel(col)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ height: 40 }} />
      )}
      <div ref={containerRef} className="hide-scrollbar" style={{ overflowX: needsScroll ? 'auto' : 'visible', padding: '8px 16px 0' }}>
        {needsScroll
          ? <div style={{ width: fixedWidth, height: chartHeight }}><ResponsiveContainer width="100%" height="100%">{renderChart()}</ResponsiveContainer></div>
          : <ResponsiveContainer width="100%" height={chartHeight}>{renderChart()}</ResponsiveContainer>
        }
      </div>
    </>
  );
}
