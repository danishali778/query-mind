import React from 'react';
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BaseChartContainer } from '../src/components/charts/BaseChartContainer';
import { DashboardBarChart } from '../src/components/dashboard/charts/DashboardBarChart';
import type { DashboardWidgetItem } from '../src/types/dashboard';

vi.mock('recharts', async () => {
  const ReactModule = await import('react');
  const passthrough = ({ children }: { children?: React.ReactNode }) => ReactModule.createElement('div', null, children);
  const tooltipPayload = [
    { dataKey: 'Missing', name: 'Missing', value: null, color: '#111', fill: '#111', payload: {} },
    { dataKey: 'Zero', name: 'Zero', value: 0, color: '#222', fill: '#222', payload: {} },
    { dataKey: 'Negative', name: 'Negative', value: -20, color: '#333', fill: '#333', payload: {} },
  ];

  return {
    ResponsiveContainer: passthrough,
    BarChart: ({ data, children }: { data: Record<string, unknown>[]; children?: React.ReactNode }) => (
      ReactModule.createElement(
        'div',
        { 'data-testid': 'recharts-bar-chart', 'data-chart-data': JSON.stringify(data) },
        children,
      )
    ),
    Bar: ({ dataKey }: { dataKey: string }) => ReactModule.createElement('div', { 'data-testid': `recharts-bar-${dataKey}` }),
    Cell: passthrough,
    XAxis: passthrough,
    YAxis: passthrough,
    CartesianGrid: passthrough,
    Tooltip: ({ content }: { content?: React.ReactElement }) => (
      ReactModule.isValidElement(content)
        ? ReactModule.cloneElement(content, { active: true, payload: tooltipPayload, label: 'February' })
        : null
    ),
    LineChart: passthrough,
    Line: passthrough,
    AreaChart: passthrough,
    Area: passthrough,
    PieChart: passthrough,
    Pie: passthrough,
  };
});

const groupedRows = [
  { month: 'January', region: 'East', revenue: 100 },
  { month: 'January', region: 'West', revenue: 150 },
  { month: 'February', region: 'East', revenue: 0 },
  { month: 'March', region: 'East', revenue: -20 },
  { month: 'March', region: 'West', revenue: 170 },
];

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class ResizeObserver {
    observe() { /* no-op */ }
    disconnect() { /* no-op */ }
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Recharts-only grouped bars', () => {
  it('renders sparse Chat groups through Recharts while preserving null, zero, and negative values', () => {
    const { container } = render(
      <BaseChartContainer
        recommendation={{
          type: 'bar',
          title: 'Revenue by region',
          x_column: 'month',
          y_columns: ['revenue'],
          color_column: 'region',
          is_grouped: true,
          x_label: 'Month',
          y_label: 'Revenue',
        }}
        rows={groupedRows}
        columns={['month', 'region', 'revenue']}
      />,
    );

    const chartData = JSON.parse(screen.getByTestId('recharts-bar-chart').getAttribute('data-chart-data') || '[]');
    expect(chartData.map((point: Record<string, unknown>) => [point.__xLabel, point.__series, point.__value, point.__xPosition])).toEqual([
      ['January', 'East', 100, -0.2],
      ['January', 'West', 150, 0.2],
      ['February', 'East', 0, 1],
      ['March', 'East', -20, 1.8],
      ['March', 'West', 170, 2.2],
    ]);
    expect(screen.getByTestId('recharts-bar-__value')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Grouped' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Single' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Multi-Grid' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '%' })).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeNull();
  });

  it('keeps a simple Chat bar on the same Recharts path', () => {
    render(
      <BaseChartContainer
        recommendation={{
          type: 'bar',
          title: 'Revenue by month',
          x_column: 'month',
          y_columns: ['revenue'],
          x_label: 'Month',
          y_label: 'Revenue',
        }}
        rows={[{ month: 'January', revenue: 100 }, { month: 'February', revenue: 120 }]}
        columns={['month', 'revenue']}
      />,
    );

    expect(screen.getByTestId('recharts-bar-chart')).toBeInTheDocument();
    expect(screen.getByTestId('recharts-bar-revenue')).toBeInTheDocument();
  });

  it('keeps ordinary multi-column Chat groups on the existing series path', () => {
    render(
      <BaseChartContainer
        recommendation={{
          type: 'bar',
          title: 'Revenue and profit by month',
          x_column: 'month',
          y_columns: ['revenue', 'profit'],
          is_grouped: true,
        }}
        rows={[
          { month: 'January', revenue: 100, profit: 20 },
          { month: 'February', revenue: 120, profit: 25 },
        ]}
        columns={['month', 'revenue', 'profit']}
      />,
    );

    expect(screen.getByTestId('recharts-bar-revenue')).toBeInTheDocument();
    expect(screen.getByTestId('recharts-bar-profit')).toBeInTheDocument();
    expect(screen.queryByTestId('recharts-bar-__value')).not.toBeInTheDocument();
  });

  it('uses the shared sparse data shape in Dashboard and hides only missing tooltip entries', () => {
    const widget: DashboardWidgetItem = {
      id: 'widget-1',
      dashboard_id: 'dashboard-1',
      title: 'Revenue by region',
      viz_type: 'bar',
      size: 'half',
      columns: ['month', 'region', 'revenue'],
      rows: groupedRows,
      chart_config: {
        x_column: 'month',
        y_columns: ['revenue'],
        color_column: 'region',
        is_grouped: true,
      },
      cadence: 'Manual only',
      x: 0,
      y: 0,
      w: 10,
      h: 7,
      minW: 4,
      minH: 5,
      bar_orientation: 'vertical',
      order_index: 0,
    };

    const { container } = render(<DashboardBarChart widget={widget} size="half" />);

    const chartData = JSON.parse(screen.getByTestId('recharts-bar-chart').getAttribute('data-chart-data') || '[]');
    expect(chartData.map((point: Record<string, unknown>) => [point.__xLabel, point.__series, point.__value, point.__xPosition])).toEqual([
      ['January', 'East', 100, -0.2],
      ['January', 'West', 150, 0.2],
      ['February', 'East', 0, 1],
      ['March', 'East', -20, 1.8],
      ['March', 'West', 170, 2.2],
    ]);
    expect(screen.queryByText('Missing')).not.toBeInTheDocument();
    expect(screen.getByText('Zero')).toBeInTheDocument();
    expect(screen.getByText('Negative')).toBeInTheDocument();
    expect(container.querySelector('svg')).toBeNull();
  });
});
