import { formatColLabel } from '../utils/dataProcessors';
import { T } from '../../dashboard/tokens';

function formatLabel(raw: string): string {
  if (typeof raw !== 'string') return String(raw);
  // Detect ISO datetime: "2022-11-01T00:00:00" or "2022-11-01"
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) {
    const d = new Date(raw);
    if (!isNaN(d.getTime())) {
      const isMidnight = raw.includes('T00:00:00') || raw === raw.slice(0, 10);
      return isMidnight
        ? d.toLocaleDateString('en-US', { year: 'numeric', month: 'short' })
        : d.toLocaleString('en-US', { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }
  }
  return raw;
}

export interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number; color: string; payload: Record<string, unknown> }>;
  label?: string;
  normalizedColMaxes: Record<string, number> | null;
  categoryCol?: string;
  tooltipColumns?: string[];
}

export function CustomTooltip({ active, payload, label, normalizedColMaxes, categoryCol, tooltipColumns }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const tt = {
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    boxShadow: '0 8px 32px rgba(0,0,0,0.06)',
    fontSize: '0.78rem',
    background: 'rgba(255, 255, 255, 0.96)',
    backdropFilter: 'blur(10px)',
    color: T.text,
    padding: '10px 14px',
    zIndex: 100,
  };

  const rowData = payload[0].payload;
  const compactColor = typeof rowData.__color === 'string' ? rowData.__color : null;
  const primaryColor = compactColor ?? payload[0].color;
  const compactLabel = rowData.__xLabel;

  return (
    <div style={tt}>
      <div style={{ fontWeight: 600, marginBottom: 6, color: T.text2 }}>{formatLabel(String(compactLabel ?? label ?? ''))}</div>
      {categoryCol && rowData[categoryCol] != null && (
        <div style={{ color: primaryColor, marginBottom: 4, fontWeight: 500 }}>
          {categoryCol} : {String(rowData[categoryCol])}
        </div>
      )}
      {payload.map((entry, i) => {
        const compactSeries = typeof entry.payload.__series === 'string' ? entry.payload.__series : null;
        const rawKey = `_raw_${entry.dataKey}`;
        const rawValue = (compactSeries ? entry.payload.__rawValue : entry.payload[rawKey]) as number | undefined;
        const displayValue = normalizedColMaxes
          ? `${typeof rawValue === 'number' ? rawValue.toLocaleString() : rawValue} (${entry.value}%)`
          : (typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value);
        return (
          <div key={i} style={{ color: categoryCol && payload.length === 1 ? T.text2 : (compactColor ?? entry.color), marginBottom: 2, fontWeight: 500 }}>
            {formatColLabel(compactSeries ?? entry.dataKey)} : {displayValue}
          </div>
        );
      })}
      {tooltipColumns && tooltipColumns.length > 0 && (
        <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 6, paddingTop: 6 }}>
          {tooltipColumns.map(col => {
            const val = rowData[col];
            if (val == null) return null;
            const display = typeof val === 'number' ? val.toLocaleString() : String(val);
            return (
              <div key={col} style={{ color: T.text3, marginBottom: 2, fontSize: '0.72rem' }}>
                {formatColLabel(col)} : {display}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
