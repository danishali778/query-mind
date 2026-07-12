import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DashboardCreateChoiceModal } from '../src/components/dashboard/DashboardCreateChoiceModal';
import { DashboardCreateForm } from '../src/components/dashboard/DashboardCreateForm';
import { WidgetGenerationPlaceholder } from '../src/components/dashboard/WidgetGenerationPlaceholder';
import { WidgetRenderer } from '../src/components/dashboard/WidgetRenderer';
import type { DashboardWidgetItem } from '../src/types/dashboard';
import {
  PROMPT_MAX_LENGTH,
  isDescribeFormValid,
  validateDescribeForm,
} from '../src/utils/dashboardGeneration';

describe('prompt-to-dashboard describe validation', () => {
  it('requires connection, prompt, and widget count bounds', () => {
    expect(validateDescribeForm({
      connectionId: '',
      prompt: '',
      widgetCount: 6,
      timePeriod: '',
      extraInstructions: '',
    })).toEqual({
      connectionId: 'Select a database connection',
      prompt: 'Describe what the dashboard should show',
    });

    expect(validateDescribeForm({
      connectionId: 'conn-1',
      prompt: 'x'.repeat(PROMPT_MAX_LENGTH + 1),
      widgetCount: 9,
      timePeriod: '',
      extraInstructions: '',
    }).prompt).toMatch(/2048/);

    expect(isDescribeFormValid({
      connectionId: 'conn-1',
      prompt: 'Revenue overview',
      widgetCount: 6,
      timePeriod: '90d',
      extraInstructions: '',
    })).toBe(true);
  });
});

describe('dashboard creation choice', () => {
  it('offers AI and manual paths', async () => {
    const user = userEvent.setup();
    const onChooseAi = vi.fn();
    const onChooseManual = vi.fn();

    render(
      <DashboardCreateChoiceModal
        isOpen
        onClose={vi.fn()}
        onChooseAi={onChooseAi}
        onChooseManual={onChooseManual}
      />,
    );

    expect(screen.getByText('GENERATE WITH AI')).toBeInTheDocument();
    expect(screen.getByText('CREATE MANUALLY')).toBeInTheDocument();

    await user.click(screen.getByText('Prompt to dashboard'));
    expect(onChooseAi).toHaveBeenCalledOnce();

    await user.click(screen.getByText('Empty dashboard'));
    expect(onChooseManual).toHaveBeenCalledOnce();
  });

  it('keeps the existing manual create form available', async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    render(
      <DashboardCreateForm
        value="Ops Board"
        onChange={vi.fn()}
        onCreate={onCreate}
        onCancel={vi.fn()}
        ctaLabel="Create"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Create' }));
    expect(onCreate).toHaveBeenCalledOnce();
  });
});

describe('widget generation placeholder', () => {
  const baseWidget: DashboardWidgetItem = {
    id: 'w1',
    dashboard_id: 'd1',
    title: 'Revenue trend',
    viz_type: 'line',
    size: 'half',
    columns: [],
    rows: [],
    cadence: 'Manual only',
    x: 0,
    y: 0,
    w: 10,
    h: 7,
    minW: 4,
    minH: 5,
    bar_orientation: 'horizontal',
    order_index: 0,
    created_at: new Date().toISOString(),
    generation_status: 'running',
    source_type: 'ai',
  };

  it('renders stage placeholder without crashing on missing sql/rows', () => {
    render(<WidgetGenerationPlaceholder widget={baseWidget} />);
    expect(screen.getByTestId('widget-generation-placeholder')).toBeInTheDocument();
    expect(screen.getByText('Generating')).toBeInTheDocument();
    expect(screen.getByText('Revenue trend')).toBeInTheDocument();
  });

  it('exposes retry and regenerate for failed widgets', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const onRegenerate = vi.fn();
    render(
      <WidgetGenerationPlaceholder
        widget={{ ...baseWidget, generation_status: 'failed', generation_error: 'SQL failed' }}
        onRetry={onRetry}
        onRegenerate={onRegenerate}
      />,
    );

    expect(screen.getByText('SQL failed')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledOnce();
    await user.click(screen.getByRole('button', { name: 'Regenerate' }));
    await user.click(screen.getByRole('button', { name: 'Run regenerate' }));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it('WidgetRenderer uses placeholder when generation_status is not ready', () => {
    render(
      <WidgetRenderer
        widget={{ ...baseWidget, sql: null, rows: undefined as unknown as [], columns: undefined as unknown as [] }}
        onDelete={vi.fn()}
        onUpdateWidget={vi.fn()}
      />,
    );
    expect(screen.getByTestId('widget-generation-placeholder')).toBeInTheDocument();
  });
});
