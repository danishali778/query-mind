import { describe, expect, it } from 'vitest';
import { compactGroupedBars, pivotGroupedSeries, processChartData, sortTemporalRows } from '../src/components/charts/utils/dataProcessors';

describe('sortTemporalRows', () => {
  it('sorts date-like chart rows ascending without mutating table rows', () => {
    const rows = [
      { month: '2025-02-01', revenue: 2 },
      { month: '2025-01-01', revenue: 1 },
    ];
    expect(sortTemporalRows(rows, 'month')).toEqual([
      { month: '2025-01-01', revenue: 1 },
      { month: '2025-02-01', revenue: 2 },
    ]);
    expect(rows[0].month).toBe('2025-02-01');
  });

  it('preserves non-temporal category ordering', () => {
    const rows = [{ company: 'Zed' }, { company: 'Alpha' }];
    expect(sortTemporalRows(rows, 'company')).toBe(rows);
  });
});

describe('pivotGroupedSeries', () => {
  it('creates stable grouped series and fills missing combinations with null', () => {
    const result = pivotGroupedSeries([
      { month: 'January', region: 'East', revenue: 100 },
      { month: 'January', region: 'West', revenue: 150 },
      { month: 'February', region: 'East', revenue: 120 },
      { month: 'March', region: 'West', revenue: 170 },
    ], 'month', 'region', 'revenue');

    expect(result.series).toEqual(['East', 'West']);
    expect(result.data).toEqual([
      { month: 'January', East: 100, West: 150 },
      { month: 'February', East: 120, West: null },
      { month: 'March', West: 170, East: null },
    ]);
  });

  it('preserves zero and negative values while parsing valid numeric strings', () => {
    const result = pivotGroupedSeries([
      { month: 'January', region: 'East', revenue: 0 },
      { month: 'January', region: 'West', revenue: '-20' },
      { month: 'February', region: 'East', revenue: '42.5' },
    ], 'month', 'region', 'revenue');

    expect(result.data).toEqual([
      { month: 'January', East: 0, West: -20 },
      { month: 'February', East: 42.5, West: null },
    ]);
  });

  it('converts null, empty, invalid, and non-finite values to null', () => {
    const result = pivotGroupedSeries([
      { month: 'January', region: 'Null', revenue: null },
      { month: 'January', region: 'Empty', revenue: '   ' },
      { month: 'January', region: 'Invalid', revenue: 'not-a-number' },
      { month: 'January', region: 'Infinite', revenue: Number.POSITIVE_INFINITY },
    ], 'month', 'region', 'revenue');

    expect(result.data).toEqual([{
      month: 'January',
      Null: null,
      Empty: null,
      Invalid: null,
      Infinite: null,
    }]);
  });

  it('keeps first-seen series order and the last duplicate combination value', () => {
    const result = pivotGroupedSeries([
      { month: 'January', region: 'West', revenue: 10 },
      { month: 'January', region: 'East', revenue: 20 },
      { month: 'January', region: 'West', revenue: 30 },
    ], 'month', 'region', 'revenue');

    expect(result.series).toEqual(['West', 'East']);
    expect(result.data).toEqual([{ month: 'January', West: 30, East: 20 }]);
  });
});

describe('processChartData grouped normalization', () => {
  it('keeps missing grouped values null when normalization is enabled', () => {
    const result = processChartData([
      { month: 'January', region: 'East', revenue: 100 },
      { month: 'January', region: 'West', revenue: 50 },
      { month: 'February', region: 'East', revenue: 25 },
    ], 'month', ['revenue'], true, undefined, 'region', true);

    expect(result.data).toEqual([
      { month: 'January', _raw_East: 100, East: 100, _raw_West: 50, West: 100 },
      { month: 'February', _raw_East: 25, East: 25, _raw_West: null, West: null },
    ]);
    expect(result.isPivotedGrouped).toBe(true);
  });
});

describe('compactGroupedBars', () => {
  it('centers only present values while keeping X groups equally spaced', () => {
    const result = compactGroupedBars([
      { month: 'January', East: 100, West: null },
      { month: 'February', East: 0, West: -20 },
      { month: 'March', East: null, West: 170 },
    ], 'month', ['East', 'West']);

    expect(result.ticks).toEqual([0, 1, 2]);
    expect(result.labels).toEqual(['January', 'February', 'March']);
    expect(result.maxVisibleBars).toBe(2);
    expect(result.data).toEqual([
      { __xPosition: 0, __xLabel: 'January', __series: 'East', __value: 100, __rawValue: undefined },
      { __xPosition: 0.8, __xLabel: 'February', __series: 'East', __value: 0, __rawValue: undefined },
      { __xPosition: 1.2, __xLabel: 'February', __series: 'West', __value: -20, __rawValue: undefined },
      { __xPosition: 2, __xLabel: 'March', __series: 'West', __value: 170, __rawValue: undefined },
    ]);
  });

  it('omits invalid values without treating zero or negatives as missing', () => {
    const result = compactGroupedBars([
      { month: 'January', Missing: null, Invalid: 'bad', Zero: 0, Negative: -5 },
    ], 'month', ['Missing', 'Invalid', 'Zero', 'Negative']);

    expect(result.data.map(point => [point.__series, point.__value])).toEqual([
      ['Zero', 0],
      ['Negative', -5],
    ]);
  });
});
