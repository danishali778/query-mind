import { useState } from 'react';
import type { ChatChartBlockProps } from '../../types/chat';
import { T } from '../dashboard/tokens';
import { processChartData } from './utils/dataProcessors';
import { BarChartModule } from './modules/BarChartModule';
import { LineChartModule } from './modules/LineChartModule';
import { AreaChartModule } from './modules/AreaChartModule';
import { PieChartModule } from './modules/PieChartModule';
import { KPIModule } from './modules/KPIModule';

export function BaseChartContainer({ recommendation, rows, column_metadata }: ChatChartBlockProps) {
  const [chartType, setChartType] = useState<'bar' | 'line' | 'pie' | 'area' | 'kpi'>(
    recommendation.type as 'bar' | 'line' | 'pie' | 'area' | 'kpi'
  );
  
  const [normalizedRaw, setNormalizedRaw] = useState(false);
  const { x_column, color_column, tooltip_columns: raw_tooltip_columns, is_grouped, is_dual_axis } = recommendation;
  // If a column appears in both y_columns and tooltip_columns, keep it as a plotted bar and drop it from the tooltip
  const tooltip_columns = (raw_tooltip_columns ?? []).filter(c => !recommendation.y_columns.includes(c));

  // When normalizing, auto-switch away from Pie (pie of percentages is meaningless)
  const setNormalized = (updater: boolean | ((prev: boolean) => boolean)) => {
    setNormalizedRaw(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      if (next && chartType === 'pie') setChartType('bar');
      return next;
    });
  };

  // Process data from raw rows to chart-ready data
  const { data, rawData, colMaxes, categoryCol, yColumns, uniqueCategories } = processChartData(
    rows,
    x_column,
    recommendation.y_columns,
    normalizedRaw,
    column_metadata,
    color_column,
    is_grouped,
    tooltip_columns
  );

  const types = [
    { key: 'bar' as const, label: 'Bar' },
    { key: 'line' as const, label: 'Line' },
    { key: 'pie' as const, label: 'Pie' },
    { key: 'area' as const, label: 'Area' },
  ];

  // Show % button when multiple y columns
  const showNormalizeBtn = yColumns.length > 1;
  const visibleTypes = normalizedRaw ? types.filter(t => t.key !== 'pie') : types;

  const childProps = {
    data,
    rawData,
    xColumn: x_column,
    yColumns,
    categoryCol,
    colMaxes,
    uniqueCategories,
    normalized: normalizedRaw,
    column_metadata,
    xLabel: recommendation.x_label,
    yLabel: recommendation.y_label,
    colorColumn: color_column,
    tooltipColumns: tooltip_columns,
    isDualAxis: is_dual_axis,
  };

  const renderModule = () => {
    switch (chartType) {
      case 'bar': return <BarChartModule {...childProps} />;
      case 'line': return <LineChartModule {...childProps} />;
      case 'area': return <AreaChartModule {...childProps} />;
      case 'pie': return <PieChartModule {...childProps} />;
      case 'kpi': return <KPIModule {...childProps} />;
      default: return null;
    }
  };

  return (
    <div style={{ borderBottom: `1px solid ${T.border}`, width: '100%', minWidth: 0, overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', background: T.s2 }}>
        <span style={{ fontSize: '0.65rem', fontFamily: T.fontMono, fontWeight: 600, letterSpacing: 1, color: T.purple, background: T.purpleDim, border: '1px solid rgba(124,58,255,0.25)', padding: '2px 8px', borderRadius: 4 }}>
          CHART
        </span>
        <span style={{ fontSize: '0.72rem', color: T.text3, fontFamily: T.fontMono, flex: 1, marginLeft: 4 }}>
          Auto-selected: {recommendation.type.charAt(0).toUpperCase() + recommendation.type.slice(1)}
          {normalizedRaw && <span style={{ marginLeft: 8, color: T.green, opacity: 0.8 }}>· normalized</span>}
        </span>
        
        <div style={{ display: chartType === 'kpi' ? 'none' : 'flex', gap: 3, alignItems: 'center' }}>
          {showNormalizeBtn && (
            <button onClick={() => setNormalized(n => !n)} style={{
              padding: '3px 8px', borderRadius: 4,
              border: `1px solid ${normalizedRaw ? 'rgba(34,211,165,0.4)' : T.border}`,
              background: normalizedRaw ? 'rgba(34,211,165,0.1)' : 'transparent',
              color: normalizedRaw ? T.green : T.text3,
              fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono,
            }}>%</button>
          )}
          {visibleTypes.map(t => (
            <button key={t.key} onClick={() => setChartType(t.key)} style={{
              padding: '3px 8px', borderRadius: 4,
              border: `1px solid ${chartType === t.key ? 'rgba(124,58,255,0.3)' : T.border}`,
              background: chartType === t.key ? T.purpleDim : 'transparent',
              color: chartType === t.key ? T.purple : T.text3,
              fontSize: '0.68rem', cursor: 'pointer', fontFamily: T.fontMono,
            }}>{t.label}</button>
          ))}
        </div>
      </div>
      
      {renderModule()}
    </div>
  );
}
