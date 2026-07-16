import { describe, expect, it } from 'vitest';
import { pivotGroupedSeries, processChartData } from '../src/components/charts/utils/dataProcessors';

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
  });
});
