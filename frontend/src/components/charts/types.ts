export interface ChartModuleProps {
  data: Record<string, unknown>[];
  rawData: Record<string, unknown>[];
  xColumn: string;
  yColumns: string[];
  categoryCol?: string;
  colMaxes: Record<string, number>;
  uniqueCategories: string[];
  normalized: boolean;
  column_metadata?: Record<string, string>;
  xLabel?: string;
  yLabel?: string;
  colorColumn?: string | null;
  tooltipColumns?: string[];
  isDualAxis?: boolean;
  isPivotedGrouped?: boolean;
}
