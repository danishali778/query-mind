import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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

export function AreaChartModule({
  data,
  xColumn,
  yColumns,
  colMaxes,
  normalized,
  column_metadata,
  xLabel,
  yLabel,
  tooltipColumns,
  isDualAxis: isDualAxisProp,
}: ChartModuleProps) {
  const SCROLL_THRESHOLD = 20;
  const effectivePointCount = data.length * Math.max(1, yColumns.length);
  const needsScroll = effectivePointCount > SCROLL_THRESHOLD;
  const fixedWidth = Math.max(600, data.length * Math.max(32, yColumns.length * 20));

  const xLabelInterval = needsScroll ? 0 : (data.length > 20 ? Math.ceil(data.length / 12) - 1 : 0);
  const chartMargin = { top: 10, right: 20, left: 50, bottom: 45 };

  const xAxisProps = {
    dataKey: xColumn,
    tick: TruncatedXTick,
    height: xLabel && !needsScroll ? 70 : 55,
    axisLine: { stroke: chartStyles.gridStroke },
    interval: xLabelInterval,
    ...(xLabel && !needsScroll ? {
      label: {
        value: xLabel,
        position: 'insideBottom' as const,
        offset: -6,
        fill: T.text3,
        fontSize: 11,
        fontFamily: T.fontMono,
      }
    } : {}),
  };

  const isColCurrency = (colName: string) => column_metadata?.[colName] === 'currency';

  // ── Dual-axis logic ────────────────────────────────────────
  const sortedBySca = [...yColumns].sort((a, b) => (colMaxes[b] || 0) - (colMaxes[a] || 0));
  const maxVal = colMaxes[sortedBySca[0]] || 1;

  const leftCols = sortedBySca.filter(c => (colMaxes[c] || 0) >= maxVal / 10);
  const rightCols = sortedBySca.filter(c => (colMaxes[c] || 0) < maxVal / 10);

  const needsDualAxis = !normalized && (isDualAxisProp || rightCols.length > 0);
  const getAxisId = (col: string): 'left' | 'right' => (needsDualAxis && rightCols.includes(col)) ? 'right' : 'left';

  const chartHeight = 360;

  const leftAxisColor = COLORS[yColumns.indexOf(leftCols[0]) % COLORS.length];
  const rightAxisColor = COLORS[yColumns.indexOf(rightCols[0] ?? '') % COLORS.length];

  const leftAxisLabel = (() => {
    const full = leftCols.map(formatColLabel).join(' / ');
    return full.length > 24 ? formatColLabel(leftCols[0]) : full;
  })();
  const rightAxisLabel = (() => {
    const full = rightCols.map(formatColLabel).join(' / ');
    return full.length > 24 ? formatColLabel(rightCols[0]) : full;
  })();

  const AXIS_W = 72;
  const makeAxisLabel = (value: string, color: string, side: 'left' | 'right') => ({
    value,
    angle: side === 'left' ? -90 : 90,
    position: (side === 'left' ? 'insideLeft' : 'insideRight') as 'insideLeft' | 'insideRight',
    fill: color,
    fontSize: 10,
    opacity: 0.85,
    style: { textAnchor: 'middle' as const },
  });

  const yAxisLabelText = yLabel || (yColumns.length === 1 ? formatColLabel(yColumns[0]) : 'Value');
  const yAxisLabelSingle = {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    content: (props: any) => {
      const vb = props.viewBox;
      if (!vb) return null;
      const cx = vb.x - 32;
      const cy = vb.y + vb.height / 2;
      return (
        <text x={cx} y={cy} transform={`rotate(-90, ${cx}, ${cy})`}
          textAnchor="middle" fill={T.text3} fontSize={11} fontFamily={T.fontMono}>
          {yAxisLabelText}
        </text>
      );
    }
  };

  const renderSingleChart = () => {
    const margin = needsDualAxis ? { ...chartMargin, left: 40, right: 40 } : chartMargin;
    const cp = { data, margin };
    const dims = needsScroll ? { width: fixedWidth, height: chartHeight } : {};
    const yAxisFmtLeft = (v: number) => formatYAxisValue(v, normalized, leftCols.some(isColCurrency));
    const yAxisFmtRight = (v: number) => formatYAxisValue(v, normalized, rightCols.some(isColCurrency));
    const yAxisFmtSingle = (v: number) => formatYAxisValue(v, normalized, yColumns.some(isColCurrency));

    const yLeft = (
      <YAxis yAxisId="left" width={AXIS_W} tickCount={9}
        tick={{ fontSize: 11, fill: leftAxisColor, opacity: 0.75 }}
        axisLine={{ stroke: leftAxisColor, strokeOpacity: 0.45 }}
        tickLine={{ stroke: leftAxisColor, strokeOpacity: 0.3 }}
        tickFormatter={yAxisFmtLeft} label={makeAxisLabel(leftAxisLabel, leftAxisColor, 'left')} />
    );
    const yRight = needsDualAxis ? (
      <YAxis yAxisId="right" orientation="right" width={AXIS_W} tickCount={9}
        tick={{ fontSize: 11, fill: rightAxisColor, opacity: 0.75 }}
        axisLine={{ stroke: rightAxisColor, strokeOpacity: 0.45 }}
        tickLine={{ stroke: rightAxisColor, strokeOpacity: 0.3 }}
        tickFormatter={yAxisFmtRight} label={makeAxisLabel(rightAxisLabel, rightAxisColor, 'right')} />
    ) : null;

    return (
      <AreaChart {...dims} {...cp}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartStyles.gridStroke} />
        <XAxis {...xAxisProps} />
        {needsDualAxis ? (
          <>{yLeft}{yRight}</>
        ) : (
          <YAxis yAxisId="left" width={65} tickCount={9} tick={chartStyles.textStyle} axisLine={{ stroke: chartStyles.gridStroke }} tickFormatter={yAxisFmtSingle} label={yAxisLabelSingle} />
        )}
        <Tooltip content={<CustomTooltip normalizedColMaxes={normalized ? colMaxes : null} tooltipColumns={tooltipColumns} />} />
        {yColumns.map((c, i) => (
          <Area key={c} yAxisId={getAxisId(c)} type="monotone" dataKey={c} stroke={COLORS[i % COLORS.length]} fill={COLORS[i % COLORS.length]} fillOpacity={0.15} strokeWidth={2} connectNulls />
        ))}
      </AreaChart>
    );
  };

  return (
    <>
      {needsDualAxis && (
        <div style={{ padding: '6px 20px', background: T.purpleDim, borderTop: `1px solid ${T.purple}20`, fontSize: '0.7rem', color: T.text3, fontFamily: T.fontMono }}>
          Two independent y-axes — <span style={{ color: leftAxisColor, fontWeight: 600 }}>{leftAxisLabel}</span> on left · <span style={{ color: rightAxisColor, fontWeight: 600 }}>{rightAxisLabel}</span> on right
        </div>
      )}

      <div style={{ padding: '16px 20px 0', overflowX: needsScroll ? 'auto' : 'visible' }}>
        {needsScroll
          ? <div style={{ width: fixedWidth }}>{renderSingleChart()}</div>
          : <ResponsiveContainer width="100%" height={chartHeight}>{renderSingleChart() as React.ReactElement}</ResponsiveContainer>
        }
      </div>

      {needsScroll && xLabel && (
        <div style={{ textAlign: 'center', fontSize: 11, color: T.text3, fontFamily: T.fontMono, padding: '2px 0 6px' }}>
          {xLabel}
        </div>
      )}

      {yColumns.length > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 16, padding: '4px 20px 10px' }}>
          {yColumns.map((col, i) => (
            <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length], flexShrink: 0 }} />
              <span style={{ fontSize: '0.72rem', color: T.text2, fontFamily: T.fontMono, fontWeight: 500 }}>{formatColLabel(col)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
