import { useState } from 'react';
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
  tooltipColumns,
  isDualAxis: isDualAxisProp,
}: ChartModuleProps) {
  const [viewMode, setViewMode] = useState<'grouped' | 'single' | 'multi'>('grouped');
  const [activeCategory, setActiveCategory] = useState(yColumns[0]);

  const SCROLL_THRESHOLD = 20;
  const barsPerGroup = viewMode === 'grouped' ? yColumns.length : 1;
  const effectiveBarCount = data.length * barsPerGroup;
  const needsScroll = viewMode !== 'multi' && effectiveBarCount > SCROLL_THRESHOLD;
  const fixedWidth = Math.max(600, data.length * Math.max(32, barsPerGroup * 20));

  const isColCurrency = (colName: string) => column_metadata?.[colName] === 'currency';

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
