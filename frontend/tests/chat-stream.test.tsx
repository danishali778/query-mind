import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AgentActivity } from '../src/components/chat/AgentActivity';
import { parseSseBlock } from '../src/services/chatStream';


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
});
