import type {
  DashboardPlan,
  DashboardWidget,
  WidgetGenerationStatus,
  WidgetPlan,
} from '../types/api';

export const PROMPT_MAX_LENGTH = 2048;
export const WIDGET_COUNT_MIN = 1;
export const WIDGET_COUNT_MAX = 8;
export const WIDGET_COUNT_DEFAULT = 6;

export const EXAMPLE_PROMPTS = [
  'Revenue trends, top products, and regional performance for the last quarter',
  'Customer retention KPIs with churn risk and cohort activity',
  'Sales pipeline health: win rates, stage conversion, and forecast gap',
] as const;

export const IN_PROGRESS_WIDGET_STATUSES = new Set<WidgetGenerationStatus>([
  'queued',
  'running',
  'regenerating',
]);

export const FAILED_WIDGET_STATUSES = new Set<WidgetGenerationStatus>([
  'failed',
  'cancelled',
]);

export const PLANNING_PAUSE_STATUSES = new Set([
  'awaiting_approval',
  'failed',
  'cancelled',
]);

export const EXECUTION_TERMINAL_STATUSES = new Set([
  'completed',
  'failed',
  'cancelled',
  'partial',
]);

export const PLANNING_STREAM_STOP_EVENTS = new Set([
  'plan.ready',
  'run.failed',
  'run.cancelled',
]);

export const EXECUTION_STREAM_STOP_EVENTS = new Set([
  'run.completed',
  'run.failed',
  'run.cancelled',
  'run.partial',
]);

export interface DescribeFormValues {
  connectionId: string;
  prompt: string;
  widgetCount: number;
  timePeriod: string;
  extraInstructions: string;
}

export interface DescribeFormErrors {
  connectionId?: string;
  prompt?: string;
  widgetCount?: string;
}

export function validateDescribeForm(values: DescribeFormValues): DescribeFormErrors {
  const errors: DescribeFormErrors = {};
  if (!values.connectionId.trim()) {
    errors.connectionId = 'Select a database connection';
  }
  const prompt = values.prompt.trim();
  if (!prompt) {
    errors.prompt = 'Describe what the dashboard should show';
  } else if (prompt.length > PROMPT_MAX_LENGTH) {
    errors.prompt = `Prompt must be ${PROMPT_MAX_LENGTH} characters or fewer`;
  }
  if (
    !Number.isInteger(values.widgetCount)
    || values.widgetCount < WIDGET_COUNT_MIN
    || values.widgetCount > WIDGET_COUNT_MAX
  ) {
    errors.widgetCount = `Choose between ${WIDGET_COUNT_MIN} and ${WIDGET_COUNT_MAX} widgets`;
  }
  return errors;
}

export function isDescribeFormValid(values: DescribeFormValues): boolean {
  return Object.keys(validateDescribeForm(values)).length === 0;
}

export function createEmptyWidgetPlan(order = 0): WidgetPlan {
  return {
    client_key: typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `widget-${Date.now()}-${order}`,
    title: `Widget ${order + 1}`,
    question: '',
    purpose: '',
    visualization: 'auto',
    size: 'half',
    time_range: null,
  };
}

export function normalizePlan(plan: DashboardPlan | null | undefined): DashboardPlan {
  if (!plan) {
    return {
      version: 1,
      title: 'Untitled dashboard',
      description: '',
      assumptions: [],
      warnings: [],
      widgets: [createEmptyWidgetPlan(0)],
    };
  }
  return {
    version: 1,
    title: plan.title || 'Untitled dashboard',
    description: plan.description || '',
    assumptions: [...(plan.assumptions || [])],
    warnings: [...(plan.warnings || [])],
    widgets: (plan.widgets || []).map((widget, index) => ({
      client_key: widget.client_key || createEmptyWidgetPlan(index).client_key,
      title: widget.title || `Widget ${index + 1}`,
      question: widget.question || '',
      purpose: widget.purpose || '',
      visualization: widget.visualization || 'auto',
      size: widget.size || 'half',
      time_range: widget.time_range ?? null,
    })),
  };
}

export function generationRunStorageKey(dashboardId: string): string {
  return `qm:dash-gen-run:${dashboardId}`;
}

export function rememberGenerationRun(dashboardId: string, runId: string): void {
  try {
    sessionStorage.setItem(generationRunStorageKey(dashboardId), runId);
  } catch {
    // Ignore storage failures (private mode / quota).
  }
}

export function recallGenerationRun(dashboardId: string): string | null {
  try {
    return sessionStorage.getItem(generationRunStorageKey(dashboardId));
  } catch {
    return null;
  }
}

export function clearGenerationRun(dashboardId: string): void {
  try {
    sessionStorage.removeItem(generationRunStorageKey(dashboardId));
  } catch {
    // Ignore.
  }
}

export function widgetHasActiveGeneration(widget: DashboardWidget): boolean {
  const status = widget.generation_status || 'ready';
  return IN_PROGRESS_WIDGET_STATUSES.has(status) || status === 'failed';
}

export function countWidgetsByGenerationStatus(widgets: DashboardWidget[]) {
  let ready = 0;
  let inProgress = 0;
  let failed = 0;
  for (const widget of widgets) {
    const status = widget.generation_status || 'ready';
    if (status === 'ready') ready += 1;
    else if (IN_PROGRESS_WIDGET_STATUSES.has(status)) inProgress += 1;
    else if (FAILED_WIDGET_STATUSES.has(status)) failed += 1;
  }
  return { ready, inProgress, failed, total: widgets.length };
}

export function stageLabelForWidget(status: WidgetGenerationStatus | string | undefined): string {
  switch (status) {
    case 'queued':
      return 'Queued';
    case 'running':
      return 'Generating';
    case 'regenerating':
      return 'Regenerating';
    case 'failed':
      return 'Failed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return 'Ready';
  }
}
