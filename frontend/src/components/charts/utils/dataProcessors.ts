export const COLORS = [
  '#00e5ff', '#7c3aff', '#22d3a5', '#f59e0b', '#f87171',
  '#a29bfe', '#fab1a0', '#81ecec', '#34d399', '#fb923c',
  '#e879f9', '#facc15', '#38bdf8', '#4ade80', '#f472b6',
  '#a3e635', '#c084fc', '#2dd4bf', '#ff6b6b', '#fbbf24',
];

export interface ProcessedChartData {
  data: Record<string, unknown>[];
  rawData: Record<string, unknown>[];
  colMaxes: Record<string, number>;
  categoryCol?: string;
  yColumns: string[];
  uniqueCategories: string[];
  isPivotedGrouped: boolean;
}

export interface PivotedGroupedSeries {
  data: Record<string, unknown>[];
  series: string[];
}

export interface CompactGroupedBars {
  data: Record<string, unknown>[];
  ticks: number[];
  labels: string[];
  maxVisibleBars: number;
}

function toFiniteChartNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value !== 'string' || value.trim() === '') return null;

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function pivotGroupedSeries(
  rows: Record<string, unknown>[],
  xColumn: string,
  colorColumn: string,
  metricColumn: string,
): PivotedGroupedSeries {
  const pivotMap = new Map<string, Record<string, unknown>>();
  const series: string[] = [];
  const seenSeries = new Set<string>();

  rows.forEach((row) => {
    const xValue = String(row[xColumn] ?? '');
    const seriesName = String(row[colorColumn] ?? 'Unknown');
    if (!seenSeries.has(seriesName)) {
      seenSeries.add(seriesName);
      series.push(seriesName);
    }

    let pivotedRow = pivotMap.get(xValue);
    if (!pivotedRow) {
      pivotedRow = { [xColumn]: xValue };
      pivotMap.set(xValue, pivotedRow);
    }
    pivotedRow[seriesName] = toFiniteChartNumber(row[metricColumn]);
  });

  const data = Array.from(pivotMap.values(), (row) => {
    const completed = { ...row };
    series.forEach((seriesName) => {
      if (!Object.prototype.hasOwnProperty.call(completed, seriesName)) {
        completed[seriesName] = null;
      }
    });
    return completed;
  });

  return { data, series };
}

/**
 * Convert pivoted categorical rows into one Recharts bar point per present
 * value. Numeric X positions keep every category group equally spaced while
 * centering only the bars that actually exist in that group.
 */
export function compactGroupedBars(
  rows: Record<string, unknown>[],
  xColumn: string,
  series: string[],
): CompactGroupedBars {
  const presentByGroup = rows.map((row) => series.flatMap((seriesName) => {
    const value = toFiniteChartNumber(row[seriesName]);
    if (value === null) return [];
    return [{ seriesName, value, rawValue: row[`_raw_${seriesName}`] }];
  }));
  const maxVisibleBars = Math.max(1, ...presentByGroup.map(values => values.length));
  const slotStep = 0.8 / maxVisibleBars;
  const ticks = rows.map((_, index) => index);
  const labels = rows.map(row => String(row[xColumn] ?? ''));

  const data = presentByGroup.flatMap((values, groupIndex) => values.map((item, valueIndex) => ({
    __xPosition: groupIndex + (valueIndex - (values.length - 1) / 2) * slotStep,
    __xLabel: labels[groupIndex],
    __series: item.seriesName,
    __value: item.value,
    __rawValue: item.rawValue,
  })));

  return { data, ticks, labels, maxVisibleBars };
}

export function processChartData(
  rows: Record<string, unknown>[],
  xColumn: string,
  originalYCols: string[],
  normalized: boolean,
  column_metadata?: Record<string, string>,
  colorColumn?: string | null,
  isGrouped?: boolean,
  tooltipColumns?: string[]
): ProcessedChartData {
  if (!rows || rows.length === 0) {
    return { data: [], rawData: [], yColumns: originalYCols, colMaxes: {}, uniqueCategories: [], categoryCol: undefined, isPivotedGrouped: false };
  }

  const isCategorical = (col: string) => {
    if (column_metadata && column_metadata[col]) {
      return column_metadata[col] === 'categorical';
    }
    return rows.length > 0 && typeof rows[0][col] === 'string' && isNaN(Number(rows[0][col]));
  };

  const isIdentifier = (col: string) => {
    if (column_metadata && column_metadata[col]) {
      return column_metadata[col] === 'identifier';
    }
    return false;
  };

  // Use explicit colorColumn from LLM blueprint, or fall back to heuristic detection
  const effectiveColorCol: string | undefined = colorColumn || originalYCols.find(c => isCategorical(c));

  // tooltip_columns are display-only — never render them on an axis.
  // By the time we get here, tooltip_columns has already been filtered to exclude
  // any columns that are also in y_columns (done in BaseChartContainer).
  let yColumns = originalYCols.filter(c =>
    !isCategorical(c) && !isIdentifier(c) && !(tooltipColumns?.includes(c))
  );
  let categoryCol: string | undefined = effectiveColorCol && originalYCols.includes(effectiveColorCol)
    ? effectiveColorCol
    : originalYCols.find(c => isCategorical(c));

  if (!categoryCol) {
    const keys = Object.keys(rows[0]);
    categoryCol = keys.find(k => k !== xColumn && !originalYCols.includes(k) && isCategorical(k));
  }

  // Fallback if no numeric columns found, pick the first valid non-identifier one
  if (yColumns.length === 0 && originalYCols.length > 0) {
    const fallback = originalYCols.find(c => !isIdentifier(c)) || originalYCols[0];
    yColumns.push(fallback);
  }

  let finalRawData: Record<string, unknown>[] = [];

  const xValues = rows.map(r => r[xColumn]);
  const hasRepeatingX = new Set(xValues).size < xValues.length;

  // PIVOT LOGIC:
  // Use explicit is_grouped flag when provided; fall back to heuristic (repeating X + single metric)
  const shouldPivot = colorColumn && isGrouped
    ? true
    : Boolean(categoryCol && yColumns.length === 1 && hasRepeatingX);

  const pivotCol = colorColumn || categoryCol;

  if (shouldPivot && pivotCol) {
    const metricCol = yColumns[0];
    const pivoted = pivotGroupedSeries(rows, xColumn, pivotCol, metricCol);
    finalRawData = pivoted.data;
    yColumns = pivoted.series;
    categoryCol = undefined; // Pivot consumed the category column
  } else {
    // Standard data mapping — include tooltipColumns in each row
    finalRawData = rows.map(row => {
      const item: Record<string, unknown> = { [xColumn]: row[xColumn] };
      yColumns.forEach(col => {
        const v = row[col];
        item[col] = typeof v === 'number' ? v : parseFloat(String(v)) || 0;
      });
      if (categoryCol && row[categoryCol] !== undefined) {
        item[categoryCol] = row[categoryCol];
      }
      tooltipColumns?.forEach(col => {
        const v = row[col];
        if (v !== undefined && v !== null) {
          item[col] = typeof v === 'number' ? v : (typeof v === 'string' ? v : Number(v) || String(v));
        }
      });
      return item;
    });
  }

  const colMaxes: Record<string, number> = Object.fromEntries(
    yColumns.map(c => [c, Math.max(...finalRawData.map(d => Math.abs(Number(d[c]) || 0))) || 1])
  );

  const data = normalized
    ? finalRawData.map(row => {
      const item: Record<string, unknown> = { [xColumn]: row[xColumn] };
      if (categoryCol && row[categoryCol] !== undefined) {
        item[categoryCol] = row[categoryCol];
      }
      yColumns.forEach(c => {
        const rawValue = row[c];
        item[`_raw_${c}`] = rawValue;
        item[c] = rawValue === null || rawValue === undefined
          ? null
          : Math.round(((Number(rawValue) || 0) / (colMaxes[c] || 1)) * 1000) / 10;
      });
      tooltipColumns?.forEach(col => {
        const v = row[col];
        if (v !== undefined && v !== null) {
          item[col] = typeof v === 'number' ? v : (typeof v === 'string' ? v : Number(v) || String(v));
        }
      });
      return item;
    })
    : finalRawData;

  const uniqueCategories = categoryCol ? Array.from(new Set(finalRawData.map(d => String(d[categoryCol])))) : [];

  return { data, rawData: finalRawData, colMaxes, categoryCol, yColumns, uniqueCategories, isPivotedGrouped: shouldPivot };
}

/** Sort date-like chart rows chronologically without changing authoritative table order. */
export function sortTemporalRows(
  rows: Record<string, unknown>[],
  xColumn: string,
  columnMetadata?: Record<string, string>,
): Record<string, unknown>[] {
  const semanticType = columnMetadata?.[xColumn]?.toLowerCase();
  const normalizedName = xColumn.toLowerCase();
  const isTemporal = ['date', 'datetime', 'temporal'].includes(semanticType || '')
    || ['date', 'time', 'month', 'year', 'week', 'quarter', 'day'].some(token => normalizedName.includes(token));
  if (!isTemporal || rows.length < 2) return rows;

  const timestamps = rows.map(row => Date.parse(String(row[xColumn] ?? '')));
  if (timestamps.some(value => Number.isNaN(value))) return rows;
  return rows
    .map((row, index) => ({ row, timestamp: timestamps[index], index }))
    .sort((a, b) => a.timestamp - b.timestamp || a.index - b.index)
    .map(item => item.row);
}

export function getColorForCategory(cat: string, uniqueCategories: string[]) {
  return COLORS[uniqueCategories.indexOf(cat) % COLORS.length];
}

export function formatYAxisValue(v: number, normalized: boolean, isCurrency: boolean = false) {
  if (normalized) return `${v}%`;
  const prefix = isCurrency ? '$' : '';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${prefix}${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${prefix}${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${prefix}${(v / 1e3).toFixed(0)}K`;
  if (abs < 10 && abs !== 0) return `${prefix}${v.toFixed(1)}`;
  return `${prefix}${String(Math.round(v))}`;
}

export function formatSmallMultipleValue(v: number, isCurrency: boolean = false) {
  const prefix = isCurrency ? '$' : '';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${prefix}${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${prefix}${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${prefix}${(v / 1e3).toFixed(1)}k`;
  if (abs < 10 && abs !== 0) return `${prefix}${v.toFixed(2)}`;
  return `${prefix}${Math.round(v).toLocaleString()}`;
}

export function formatColLabel(col: string) {
  return col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
