import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useDashboardGenerationRun } from '../src/hooks/useDashboardGenerationRun';
import type { DashboardGenerationRun } from '../src/types/api';

const apiMocks = vi.hoisted(() => ({
  createDashboardGeneration: vi.fn(),
  getDashboardGeneration: vi.fn(),
  cancelDashboardGeneration: vi.fn(),
}));

vi.mock('../src/services/api', () => apiMocks);

const planningSnapshot: DashboardGenerationRun = {
  id: 'run-1',
  owner_id: 'owner-1',
  connection_id: 'connection-1',
  client_request_id: 'request-1',
  prompt: 'Revenue dashboard',
  requested_widget_count: 1,
  plan_revision: 0,
  status: 'planning',
  current_stage: 'planning',
  current_stage_label: 'Planning dashboard',
  items: [],
};

const readySnapshot: DashboardGenerationRun = {
  ...planningSnapshot,
  plan_revision: 1,
  status: 'awaiting_approval',
  current_stage: 'awaiting_approval',
  current_stage_label: 'Dashboard plan ready',
  plan_json: {
    version: 1,
    title: 'Revenue dashboard',
    description: 'Revenue performance overview',
    assumptions: [],
    warnings: [],
    widgets: [{
      client_key: 'widget-1',
      title: 'Monthly revenue',
      question: 'Show monthly revenue.',
      purpose: 'Track revenue over time.',
      visualization: 'line',
      size: 'half',
      time_range: null,
    }],
  },
};

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('dashboard planning stream lifecycle', () => {
  it('loads the durable plan snapshot as soon as plan.ready pauses an open stream', async () => {
    let streamCancelled = false;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          'id: 4\nevent: plan.ready\ndata: {"run_id":"run-1","type":"plan.ready","stage":"awaiting_approval","label":"Dashboard plan ready"}\n\n',
        ));
      },
      cancel() {
        streamCancelled = true;
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body,
    }));

    apiMocks.createDashboardGeneration.mockResolvedValue({
      run_id: 'run-1',
      status: 'planning',
      events_url: '/api/dashboard/generations/run-1/events',
    });
    apiMocks.getDashboardGeneration
      .mockResolvedValueOnce(planningSnapshot)
      .mockResolvedValueOnce(readySnapshot);

    const onSnapshot = vi.fn();
    const onEvent = vi.fn();
    const { result, unmount } = renderHook(() => useDashboardGenerationRun({
      onSnapshot,
      onEvent,
      onError: vi.fn(),
    }));

    await act(async () => {
      await result.current.startPlanning({
        connection_id: 'connection-1',
        prompt: 'Revenue dashboard',
        requested_widget_count: 1,
        default_time_range: null,
        extra_instructions: null,
        client_request_id: 'request-1',
      });
    });

    await waitFor(() => expect(onSnapshot).toHaveBeenLastCalledWith(readySnapshot));

    expect(onEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'plan.ready' }));
    expect(streamCancelled).toBe(true);
    expect(apiMocks.getDashboardGeneration).toHaveBeenCalledTimes(2);
    unmount();
  });
});
