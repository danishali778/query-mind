import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AgentActivity } from '../src/components/chat/AgentActivity';
import { parseSseBlock } from '../src/services/chatStream';
import { useChatAgentRun } from '../src/hooks/useChatAgentRun';

const apiMocks = vi.hoisted(() => ({
  startChatRun: vi.fn(),
  getChatRun: vi.fn(),
  cancelChatRun: vi.fn(),
}));

vi.mock('../src/services/api', () => apiMocks);


describe('durable chat event stream', () => {
  it('parses event ids and multiline SSE data', () => {
    const parsed = parseSseBlock(
      'id: 14\nevent: stage.started\ndata: {"run_id":"run-1",\ndata: "type":"stage.started","label":"Searching schema"}',
    );

    expect(parsed?.id).toBe('14');
    expect(parsed?.event).toBe('stage.started');
    expect(parsed?.data.label).toBe('Searching schema');
  });

  it('ignores heartbeat comments without data', () => {
    expect(parseSseBlock(': keep-alive')).toBeNull();
  });

  it('renders real activity and exposes an accessible stop action', () => {
    const onStop = vi.fn();
    render(
      <AgentActivity
        status="running"
        label="Inspecting table structure"
        streamState="connected"
        onStop={onStop}
        events={[{
          run_id: 'run-1', sequence: 1, type: 'stage.completed', stage: 'schema_search', label: 'Schema context ready',
        }]}
      />,
    );

    expect(screen.getByText('Inspecting table structure')).toBeInTheDocument();
    expect(screen.getByText('Schema context ready')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Stop response' }));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it('communicates reconnecting state without marking the run failed', () => {
    render(<AgentActivity status="running" label="Running query" streamState="reconnecting" />);
    expect(screen.getByText('Reconnecting to live updates')).toBeInTheDocument();
  });

  it('retrieves an immediate completed clarification without opening a stream', async () => {
    const accepted = {
      run_id: 'run-clarification',
      session_id: 'session-1',
      user_message_id: 'user-message-1',
      assistant_message_id: 'assistant-message-1',
      status: 'completed' as const,
      events_url: '/api/chat/runs/run-clarification/events',
    };
    const snapshot = {
      ...accepted,
      current_stage: 'completed',
      current_stage_label: 'Clarification needed',
      created_at: new Date().toISOString(),
      response: null,
    };
    apiMocks.startChatRun.mockResolvedValue(accepted);
    apiMocks.getChatRun.mockResolvedValue(snapshot);
    const onAccepted = vi.fn();
    const onSnapshot = vi.fn();
    const { result } = renderHook(() => useChatAgentRun({
      onAccepted,
      onSnapshot,
      onEvent: vi.fn(),
      onError: vi.fn(),
    }));

    await act(async () => {
      await result.current.start({
        connection_id: 'connection-1',
        message: 'ambiguous request',
        client_request_id: crypto.randomUUID(),
      });
    });

    expect(onAccepted).toHaveBeenCalledWith(accepted);
    expect(apiMocks.getChatRun).toHaveBeenCalledOnce();
    expect(onSnapshot).toHaveBeenCalledWith(snapshot);
  });
});
