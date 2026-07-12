import { useRef, useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: p.color }} />
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

export function DashboardLineChart({ widget, size: _size }: { widget: DashboardWidgetItem; size: WidgetSize }) { // eslint-disable-line @typescript-eslint/no-unused-vars
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => setContainerWidth(entries[0].contentRect.width));
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
    yCols = Array.from(catSet);
    data = Object.values(pivotMap);
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

  const MIN_BAR_WIDTH = 12;
  const totalBars = data.length * Math.max(1, yCols.length);
  const needsScroll = totalBars * MIN_BAR_WIDTH > containerWidth;
  const fixedWidth = Math.max(600, totalBars * (MIN_BAR_WIDTH + 2));

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
    <LineChart data={data} margin={chartMargin}>
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
      <Tooltip content={<CustomTooltip />} />
      {yCols.map((c, i) => (
        <Line 
          key={c} 
          yAxisId={getAxisId(c)} 
          type="monotone" 
          dataKey={c}
          stroke={COLORS[i % COLORS.length]} 
          strokeWidth={3}
          dot={{ r: 4, strokeWidth: 2, fill: '#fff' }} 
          activeDot={{ r: 6, strokeWidth: 0 }}
          connectNulls 
          isAnimationActive={true}
          animationDuration={1500}
          animationEasing="ease-in-out"
        />
      ))}
    </LineChart>
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
