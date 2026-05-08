import { useState, useRef, useEffect } from 'react';
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Info } from 'lucide-react';
import type { ChartModuleProps } from '../types';
import { CustomTooltip } from '../shared/CustomTooltip';
import { formatYAxisValue, formatColLabel, COLORS } from '../utils/dataProcessors';
import { chartStyles } from '../utils/config';
import { T } from '../../dashboard/tokens';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const TruncatedXTick = ({ x, y, payload }: any) => {
  const raw = payload?.value != null ? String(payload.value) : '';
  const label = raw.length > 8 ? raw.slice(0, 8) + '…' : raw;
  return (
    <g transform={`translate(${x},${y})`}>
      <text dy={4} textAnchor="end" fill={T.text3} fontSize={11} transform="rotate(-45)" fontFamily={T.fontMono}>
        {label}
      </text>
    </g>
  );
};

export function BarChartModule({
  data,
  rawData,
  xColumn,
  yColumns,
  categoryCol,
  colMaxes,
  normalized,
  column_metadata,
  xLabel,
  yLabel,
  colorColumn,
  tooltipColumns,
  isDualAxis: isDualAxisProp,
}: ChartModuleProps) {
  const [viewMode, setViewMode] = useState<'grouped' | 'single' | 'multi'>('grouped');
  const [activeCategory, setActiveCategory] = useState(yColumns[0]);

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

  const SCROLL_THRESHOLD = 20;
  const barsPerGroup = viewMode === 'grouped' ? yColumns.length : 1;
  const effectiveBarCount = data.length * barsPerGroup;
  const needsScroll = viewMode !== 'multi' && effectiveBarCount > SCROLL_THRESHOLD;
  const fixedWidth = Math.max(600, data.length * Math.max(32, barsPerGroup * 20));

  const isColCurrency = (colName: string) => column_metadata?.[colName] === 'currency';

  // ── Sparse grouped bar chart (custom SVG) ──────────────────────────
  const isPivotedGrouped = !!colorColumn && !categoryCol && yColumns.length > 1;
  const isGroupedSparse = isPivotedGrouped && viewMode === 'grouped' &&
    data.some(row => yColumns.filter(c => (Number(row[c]) || 0) > 0).length < yColumns.length);

  if (isGroupedSparse && data.length > 0) {
    const FBW = 14;
    const BGAP = 2;
    const GGAP = 16;
    const m = { t: 10, r: 20, l: 65, b: 70 };
    const svgH = 360;
    const cH = svgH - m.t - m.b;
    const cW = svgContainerWidth - m.l - m.r;

    const groups = data.map(row => {
      const xVal = String(row[xColumn] ?? '');
      const cols = yColumns.filter(c => (Number(row[c]) || 0) > 0);
      const innerW = cols.length > 0 ? cols.length * FBW + (cols.length - 1) * BGAP : FBW;
      return { xVal, cols, innerW, row };
    });

    const sumInner = groups.reduce((s, g) => s + g.innerW, 0);
    const needsSVGScroll = sumInner + (groups.length - 1) * GGAP > cW;
    const gap = needsSVGScroll || groups.length < 2 ? GGAP : (cW - sumInner) / (groups.length - 1);
    const svgW = needsSVGScroll ? m.l + sumInner + (groups.length - 1) * GGAP + m.r : svgContainerWidth;

    const gxs: number[] = [];
    let curX = m.l;
    groups.forEach((g, i) => {
      gxs.push(curX);
      curX += g.innerW + (i < groups.length - 1 ? gap : 0);
    });

    const maxY = Math.max(1, ...yColumns.flatMap(c => data.map(r => Number(r[c]) || 0)));
    const rawStep = maxY / 6;
    const mag = Math.pow(10, Math.floor(Math.log10(rawStep || 1)));
    const step = Math.ceil(rawStep / mag) * mag || 1;
    const yTicks: number[] = [];
    for (let t = 0; t <= maxY + step; t += step) yTicks.push(t);
    const yTop = yTicks[yTicks.length - 1];
    const ab = m.t + cH;
    const toY = (v: number) => m.t + cH - (v / yTop) * cH;

    const isAnyCurrency = yColumns.some(c => isColCurrency(c));
    const fmtV = (v: number) => formatYAxisValue(v, normalized, isAnyCurrency);

    return (
      <>
        <div ref={svgContainerRef} style={{ padding: '16px 20px 0', overflowX: needsSVGScroll ? 'auto' : 'visible' }}>
          <svg width={svgW} height={svgH} style={{ display: 'block', overflow: 'visible' }}>
            {yTicks.map(t => (
              <line key={t} x1={m.l} x2={svgW - m.r} y1={toY(t)} y2={toY(t)} stroke={T.border} strokeDasharray="3 3" />
            ))}
            <line x1={m.l} x2={m.l} y1={m.t} y2={ab} stroke={T.border} />
            <line x1={m.l} x2={svgW - m.r} y1={ab} y2={ab} stroke={T.border} />
            {yTicks.map(t => (
              <text key={t} x={m.l - 8} y={toY(t)} textAnchor="end" dominantBaseline="middle" fill={T.text3} fontSize={11} fontFamily={T.fontMono}>{fmtV(t)}</text>
            ))}
            {yLabel && <text transform={`translate(${m.l - 52},${m.t + cH / 2}) rotate(-90)`} textAnchor="middle" fill={T.text3} fontSize={11} fontFamily={T.fontMono}>{yLabel}</text>}
            {groups.map((g, gi) => {
              const gx = gxs[gi];
              const centerX = gx + g.innerW / 2;
              const short = g.xVal.length > 8 ? g.xVal.slice(0, 8) + '…' : g.xVal;
              const hx = gi === 0 ? gx : gx - gap / 2;
              const hw = gi === 0 || gi === groups.length - 1 ? g.innerW + gap / 2 : g.innerW + gap;
              return (
                <g key={g.xVal + gi}>
                  <rect x={hx} y={m.t} width={Math.max(1, hw)} height={cH} fill="transparent" style={{ cursor: 'pointer' }}
                    onMouseEnter={e => setSparseTooltip({ clientX: e.clientX, clientY: e.clientY, xVal: g.xVal, row: g.row })}
                    onMouseMove={e => setSparseTooltip(p => p ? { ...p, clientX: e.clientX, clientY: e.clientY } : null)}
                    onMouseLeave={() => setSparseTooltip(null)} />
                  {g.cols.map((col, ci) => {
                    const val = Number(g.row[col]) || 0;
                    const bh = Math.max(1, (val / yTop) * cH);
                    return <rect key={col} x={gx + ci * (FBW + BGAP)} y={ab - bh} width={FBW} height={bh} fill={COLORS[yColumns.indexOf(col) % COLORS.length]} rx={3} opacity={0.85} />;
                  })}
                  <g transform={`translate(${centerX},${ab + 4})`}><title>{g.xVal}</title><text textAnchor="end" fill={T.text3} fontSize={11} transform="rotate(-45)" dy={4} fontFamily={T.fontMono}>{short}</text></g>
                </g>
              );
            })}
            {xLabel && <text x={m.l + (svgW - m.l - m.r) / 2} y={svgH - 6} textAnchor="middle" fill={T.text3} fontSize={11} fontFamily={T.fontMono}>{xLabel}</text>}
          </svg>
        </div>
        {sparseTooltip && (
          <div style={{ position: 'fixed', left: sparseTooltip.clientX + 12, top: sparseTooltip.clientY - 40, background: 'rgba(255,255,255,0.96)', backdropFilter: 'blur(10px)', border: `1px solid ${T.border}`, borderRadius: 8, padding: '10px 14px', pointerEvents: 'none', zIndex: 9999, minWidth: 160, boxShadow: '0 8px 32px rgba(0,0,0,0.08)' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: T.text, marginBottom: 8 }}>{sparseTooltip.xVal}</div>
            {yColumns.filter(c => (Number(sparseTooltip.row[c]) || 0) > 0).map(c => (
              <div key={c} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
                <span style={{ fontSize: '0.75rem', color: COLORS[yColumns.indexOf(c) % COLORS.length], fontWeight: 500 }}>{formatColLabel(c)}</span>
                <span style={{ fontSize: '0.75rem', color: T.text2, fontFamily: T.fontMono }}>{fmtV(Number(sparseTooltip.row[c]) || 0)}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 16, padding: '4px 20px 10px' }}>
          {yColumns.map((col, i) => (
            <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length], flexShrink: 0 }} />
              <span style={{ fontSize: '0.72rem', color: T.text2, fontFamily: T.fontMono, fontWeight: 500 }}>{formatColLabel(col)}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 20px 10px', borderTop: `1px solid ${T.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 4 }}>
            <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, alignSelf: 'center', marginRight: 4, opacity: 0.6 }}>Bar view:</span>
            {(['grouped', 'single', 'multi'] as const).map(mode => (
              <button key={mode} onClick={() => setViewMode(mode)} style={{ padding: '3px 10px', borderRadius: 4, border: `1px solid ${viewMode === mode ? 'rgba(124,58,255,0.35)' : T.border}`, background: viewMode === mode ? T.purpleDim : 'transparent', color: viewMode === mode ? T.purple : T.text3, fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono }}>{mode === 'multi' ? 'Multi-Grid' : mode.charAt(0).toUpperCase() + mode.slice(1)}</button>
            ))}
          </div>
        </div>
      </>
    );
  }

  // ── Dual-axis logic ───────────────────────────────────────
  const sortedBySca = [...yColumns].sort((a, b) => (colMaxes[b] || 0) - (colMaxes[a] || 0));
  const maxVal = colMaxes[sortedBySca[0]] || 1;
  const leftCols = sortedBySca.filter(c => (colMaxes[c] || 0) >= maxVal / 10);
  const rightCols = sortedBySca.filter(c => (colMaxes[c] || 0) < maxVal / 10);
  const needsDualAxis = !normalized && viewMode === 'grouped' && (isDualAxisProp || (yColumns.length > 1 && rightCols.length > 0));
  const getAxisId = (col: string): 'left' | 'right' => (needsDualAxis && rightCols.includes(col)) ? 'right' : 'left';

  const chartScaleHeight = 360;
  const AXIS_W = 72;

  const leftAxisColor = COLORS[yColumns.indexOf(leftCols[0]) % COLORS.length];
  const rightAxisColor = COLORS[yColumns.indexOf(rightCols[0] ?? '') % COLORS.length];

  const leftAxisLabel = leftCols.length > 0 ? (leftCols.map(formatColLabel).join(' / ').length > 20 ? formatColLabel(leftCols[0]) : leftCols.map(formatColLabel).join(' / ')) : 'Value';
  const rightAxisLabel = rightCols.length > 0 ? (rightCols.map(formatColLabel).join(' / ').length > 20 ? formatColLabel(rightCols[0]) : rightCols.map(formatColLabel).join(' / ')) : '';

  const makeAxisLabel = (value: string, color: string, side: 'left' | 'right') => ({
    value,
    angle: side === 'left' ? -90 : 90,
    position: (side === 'left' ? 'insideLeft' : 'insideRight') as 'insideLeft' | 'insideRight',
    fill: color,
    fontSize: 10,
    opacity: 0.8,
    style: { textAnchor: 'middle' as const }
  });

  const showMultiToggle = !normalized && yColumns.length > 1;
  const useCategoryColors = !!categoryCol && yColumns.length === 1;

  const yAxisLabelText = yLabel || (yColumns.length === 1 ? formatColLabel(yColumns[0]) : 'Value');
  const yAxisLabelSingle = {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    content: (props: any) => {
      const vb = props.viewBox;
      if (!vb) return null;
      const cx = vb.x - 32;
      const cy = vb.y + vb.height / 2;
      return <text x={cx} y={cy} transform={`rotate(-90, ${cx}, ${cy})`} textAnchor="middle" fill={T.text3} fontSize={11} fontFamily={T.fontMono}>{yAxisLabelText}</text>;
    }
  };

  const renderSmallMultiples = () => {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
        {yColumns.map((col, i) => {
          const color = COLORS[i % COLORS.length];
          const firstVal = Number(rawData[0]?.[col]) || 0;
          const lastVal = Number(rawData[rawData.length - 1]?.[col]) || 0;
          const pctChange = firstVal !== 0 ? ((lastVal - firstVal) / Math.abs(firstVal)) * 100 : 0;
          const isDown = pctChange < 0;
          const fmtV = (v: number) => formatYAxisValue(v, false, isColCurrency(col));
          return (
            <div key={col} style={{ background: 'rgba(255,255,255,0.03)', border: `1px solid ${T.border}`, borderRadius: 10, padding: '14px 16px 10px', minWidth: 0 }}>
              <div style={{ fontSize: '0.65rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 5 }}>{formatColLabel(col)}</div>
              <div style={{ fontSize: '1.55rem', fontWeight: 700, color: T.text, lineHeight: 1.1, marginBottom: 3 }}>{fmtV(lastVal)}</div>
              <div style={{ fontSize: '0.7rem', color: isDown ? T.red : T.green, marginBottom: 10, fontWeight: 500 }}>{isDown ? '▼' : '▲'} {Math.abs(pctChange).toFixed(0)}% since {String(rawData[0]?.[xColumn] ?? '')}</div>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={rawData} margin={{ top: 12, right: 12, bottom: 45, left: 12 }}>
                  <XAxis dataKey={xColumn} hide axisLine={false} tickLine={false} />
                  <YAxis hide domain={['auto', 'auto']} />
                  <Tooltip content={<CustomTooltip normalizedColMaxes={null} />} />
                  <Bar dataKey={col} fill={color} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </div>
    );
  };

  const renderSingleChart = (col: string, index: number, isMulti = false) => {
    const color = COLORS[index % COLORS.length];
    const yAxisFmtLeft = (val: number) => formatYAxisValue(val, normalized, leftCols.some(isColCurrency));
    const yAxisFmtRight = (val: number) => formatYAxisValue(val, normalized, rightCols.some(isColCurrency));
    const yAxisFmtSingle = (val: number) => formatYAxisValue(val, normalized, yColumns.some(isColCurrency));

    return (
      <div key={col} style={{ height: isMulti ? 240 : chartScaleHeight, width: needsScroll ? fixedWidth : '100%' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 20, right: needsDualAxis ? 40 : 10, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={chartStyles.gridStroke} />
            <XAxis dataKey={xColumn} tick={TruncatedXTick} hide={isMulti} interval={needsScroll ? 0 : (data.length > 20 ? Math.ceil(data.length / 12) - 1 : 0)} />
            {needsDualAxis ? (
              <>
                <YAxis yAxisId="left" width={AXIS_W} tickFormatter={yAxisFmtLeft} tick={{ fontSize: 11, fill: leftAxisColor }} label={makeAxisLabel(leftAxisLabel, leftAxisColor, 'left')} />
                <YAxis yAxisId="right" orientation="right" width={AXIS_W} tickFormatter={yAxisFmtRight} tick={{ fontSize: 11, fill: rightAxisColor }} label={makeAxisLabel(rightAxisLabel, rightAxisColor, 'right')} />
              </>
            ) : (
              <YAxis yAxisId="left" width={AXIS_W} tickFormatter={yAxisFmtSingle} tick={{ fontSize: 11, fill: T.text3, fontFamily: T.fontMono }} label={yAxisLabelSingle} />
            )}
            <Tooltip content={<CustomTooltip normalizedColMaxes={normalized ? colMaxes : null} tooltipColumns={tooltipColumns} />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            {viewMode === 'grouped'
              ? yColumns.map((c, i) => <Bar key={c} dataKey={c} yAxisId={getAxisId(c)} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} barSize={needsDualAxis ? 12 : 20} />)
              : <Bar dataKey={col} yAxisId="left" fill={useCategoryColors ? "" : color} radius={[4, 4, 0, 0]} barSize={30}>{useCategoryColors && data.map((_, i) => <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />)}</Bar>
            }
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <>
      {needsDualAxis && (
        <div style={{ padding: '8px 20px', background: T.purpleDim, borderTop: `1px solid ${T.purple}20`, fontSize: '0.72rem', color: T.text3, fontFamily: T.fontMono, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Info width={14} height={14} style={{ color: T.purple, opacity: 0.8 }} />
          <span>Two independent y-axes — <span style={{ color: leftAxisColor, fontWeight: 600 }}>{leftAxisLabel}</span> scale vs <span style={{ color: rightAxisColor, fontWeight: 600 }}>{rightAxisLabel}</span> scale</span>
        </div>
      )}
      {viewMode !== 'multi' && rightCols.length > 0 && !needsDualAxis && !normalized && (
        <div style={{ padding: '6px 20px', background: 'rgba(245,158,11,0.06)', borderTop: `1px solid rgba(245,158,11,0.15)`, fontSize: '0.7rem', color: 'rgba(245,158,11,0.7)', fontFamily: T.fontMono, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Info width={12} height={12} />
          <span>Scale disparity detected. Consider switching to % or Multi-Grid for better visibility.</span>
        </div>
      )}
      <div style={{ padding: viewMode === 'multi' ? '12px 16px 8px' : '16px 10px 0', overflowX: needsScroll ? 'auto' : 'visible' }}>
        {viewMode === 'multi' ? renderSmallMultiples() : renderSingleChart(viewMode === 'single' ? activeCategory : yColumns[0], 0)}
      </div>
      {needsScroll && xLabel && <div style={{ textAlign: 'center', fontSize: 11, color: T.text3, fontFamily: T.fontMono, padding: '2px 0 6px' }}>{xLabel}</div>}
      {yColumns.length > 1 && viewMode !== 'multi' && (
        <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 16, padding: '4px 20px 10px' }}>
          {yColumns.map((col, i) => (
            <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length] }} />
              <span style={{ fontSize: '0.72rem', color: T.text2, fontFamily: T.fontMono, fontWeight: 500 }}>{formatColLabel(col)}</span>
            </div>
          ))}
        </div>
      )}
      {showMultiToggle && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 20px 10px', borderTop: `1px solid ${T.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 4 }}>
            <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, alignSelf: 'center', marginRight: 4, opacity: 0.6 }}>Bar view:</span>
            <button onClick={() => setViewMode('grouped')} style={{ padding: '3px 10px', borderRadius: 4, border: `1px solid ${viewMode === 'grouped' ? 'rgba(124,58,255,0.35)' : T.border}`, background: viewMode === 'grouped' ? T.purpleDim : 'transparent', color: viewMode === 'grouped' ? T.purple : T.text3, fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono }}>Grouped</button>
            <button onClick={() => setViewMode('single')} style={{ padding: '3px 10px', borderRadius: 4, border: `1px solid ${viewMode === 'single' ? 'rgba(124,58,255,0.35)' : T.border}`, background: viewMode === 'single' ? T.purpleDim : 'transparent', color: viewMode === 'single' ? T.purple : T.text3, fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono }}>Single</button>
            <button onClick={() => setViewMode('multi')} style={{ padding: '3px 10px', borderRadius: 4, border: `1px solid ${viewMode === 'multi' ? 'rgba(124,58,255,0.35)' : T.border}`, background: viewMode === 'multi' ? T.purpleDim : 'transparent', color: viewMode === 'multi' ? T.purple : T.text3, fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono }}>Multi-Grid</button>
          </div>
          {viewMode === 'single' && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 6, flexWrap: 'wrap' }}>
              {yColumns.map((col, i) => (
                <button key={col} onClick={() => setActiveCategory(col)} style={{ padding: '2px 8px', borderRadius: 4, border: `1px solid ${activeCategory === col ? COLORS[i % COLORS.length] : T.border}`, background: activeCategory === col ? `${COLORS[i % COLORS.length]}20` : 'transparent', color: activeCategory === col ? COLORS[i % COLORS.length] : T.text3, fontSize: '0.65rem', cursor: 'pointer', fontFamily: T.fontMono }}>{formatColLabel(col)}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
