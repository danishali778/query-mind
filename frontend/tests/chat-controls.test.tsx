import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ChatInput } from '../src/components/chat/ChatInput';
import { MessageBubble } from '../src/components/chat/MessageBubble';
import { ResultsTable } from '../src/components/chat/ResultsTable';
import type { ChatMessageView } from '../src/types/chat';

vi.mock('../src/hooks/useSmartSave', () => ({
  useSmartSave: () => ({
    smartAddToDashboard: vi.fn(),
    smartSaveToLibrary: vi.fn(),
    isSaving: false,
  }),
}));

vi.mock('../src/components/charts/BaseChartContainer', () => ({
  BaseChartContainer: () => <div data-testid="supplemental-chart">Chart</div>,
}));

const assistantMessage: ChatMessageView = {
  id: 'message_1',
  role: 'assistant',
  content: 'Here are the rows.',
  sql: 'SELECT id FROM users',
  columns: ['id'],
  rows: [{ id: 1 }],
  row_count: 1,
  execution_time_ms: 12,
  truncated: false,
};

describe('chat result controls', () => {
  it('renders the established SQL, table, chart, and actions layout without a details toggle', () => {
    render(<MessageBubble message={assistantMessage} connectionId="conn_1" onTogglePin={vi.fn()} />);

    expect(screen.getByText('COPY SQL')).toBeInTheDocument();
    expect(screen.getAllByText('RESULTS')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /query details/i })).not.toBeInTheDocument();
    expect(screen.queryByText('COPY LINK')).not.toBeInTheDocument();
    expect(screen.getByText('SAVE TO LIBRARY')).toBeInTheDocument();
    expect(screen.getByText('ADD TO DASHBOARD')).toBeInTheDocument();
    expect(screen.getByText('PIN RESULT')).toBeInTheDocument();
    expect(screen.queryByText('REGENERATE')).not.toBeInTheDocument();
  });

  it('does not show inactive CSV or JSON export buttons', () => {
    render(<ResultsTable columns={['id']} rows={[{ id: 1 }]} rowCount={1} executionTime={12} />);

    expect(screen.getByText('RESULTS')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'CSV' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'JSON' })).not.toBeInTheDocument();
  });

  it('renders clarification without agent activity or result controls', () => {
    render(
      <MessageBubble
        message={{
          id: 'clarification-1',
          role: 'assistant',
          content: 'Which metric should I analyze?',
          response_kind: 'clarification',
          agent_run_id: 'run-1',
          agent_run_status: 'completed',
        }}
        connectionId="conn_1"
      />,
    );

    expect(screen.getByText('Clarification needed')).toBeInTheDocument();
    expect(screen.queryByText('Answer ready')).not.toBeInTheDocument();
    expect(screen.queryByText('COPY SQL')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /query details/i })).not.toBeInTheDocument();
  });

  it('always shows the query result table and adds a selected chart without replacing it', () => {
    render(
      <MessageBubble
        message={{
          ...assistantMessage,
          presentation_kind: 'chart',
          answer_metadata: {
            method: 'Counted active employees by company.',
            limitations: ['Only active employees were included.'],
            evidence: [],
          },
          columns: ['company_name', 'active_employee_count'],
          rows: [{ company_name: 'CreativeHub', active_employee_count: 50 }],
          chart_recommendation: {
            type: 'bar',
            title: 'Active employees by company',
            x_column: 'company_name',
            y_columns: ['active_employee_count'],
          },
        }}
        connectionId="conn_1"
      />,
    );

    expect(screen.getByText('RESULTS')).toBeInTheDocument();
    expect(screen.getByText('CreativeHub')).toBeInTheDocument();
    expect(screen.getByTestId('supplemental-chart')).toBeInTheDocument();
    expect(screen.queryByText(/Method:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Limitations:/i)).not.toBeInTheDocument();
  });

  it('renders a direct answer without an empty technical result panel', () => {
    render(
      <MessageBubble
        message={{
          id: 'direct-1',
          role: 'assistant',
          content: 'I can inspect schemas and perform safe read-only analysis.',
          response_kind: 'direct_answer',
          presentation_kind: 'none',
          sql: 'SELECT 1',
          rows: [{ value: 1 }],
          columns: ['value'],
        }}
        connectionId="conn_1"
      />,
    );

    expect(screen.getByText(/inspect schemas/i)).toBeInTheDocument();
    expect(screen.queryByText('DATA OBSERVATIONS')).not.toBeInTheDocument();
    expect(screen.queryByText('COPY SQL')).not.toBeInTheDocument();
    expect(screen.queryByText('RESULTS')).not.toBeInTheDocument();
    expect(screen.queryByText('PIN RESULT')).not.toBeInTheDocument();
  });

  it('renders a narrative prior-result follow-up without repeating technical panels', () => {
    render(
      <MessageBubble
        message={{
          id: 'follow-up-1',
          role: 'assistant',
          content: 'The two anomalies were December 2022 and December 2023.',
          response_kind: 'result_follow_up',
          presentation_kind: 'none',
          answer_metadata: {
            evidence: [],
            provenance: {
              kind: 'prior_result',
              source_message_id: 'source-1',
              captured_at: '2026-07-17T12:00:00Z',
              reused_without_execution: true,
            },
          },
        }}
        connectionId="conn_1"
      />,
    );

    expect(screen.getByText('Based on previous result')).toBeInTheDocument();
    expect(screen.queryByText('COPY SQL')).not.toBeInTheDocument();
    expect(screen.queryByText('RESULTS')).not.toBeInTheDocument();
  });

  it('renders a reused result panel when a prior-result follow-up requests a chart', () => {
    render(
      <MessageBubble
        message={{
          ...assistantMessage,
          id: 'follow-up-chart-1',
          response_kind: 'result_follow_up',
          presentation_kind: 'chart',
          chart_recommendation: {
            type: 'bar',
            title: 'Employees by company',
            x_column: 'id',
            y_columns: ['id'],
          },
        }}
        connectionId="conn_1"
      />,
    );

    expect(screen.getByText('Based on previous result')).toBeInTheDocument();
    expect(screen.getByText('COPY SQL')).toBeInTheDocument();
    expect(screen.getByText('RESULTS')).toBeInTheDocument();
    expect(screen.getByTestId('supplemental-chart')).toBeInTheDocument();
  });

  it('does not clear the controlled draft before the parent accepts the request', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <ChatInput
        connections={[]}
        activeConnectionId="conn_1"
        onConnectionChange={vi.fn()}
        onSend={onSend}
        draft="synthetic draft"
        onDraftChange={vi.fn()}
        loading={false}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(onSend).toHaveBeenCalledWith('synthetic draft');
    expect(screen.getByDisplayValue('synthetic draft')).toBeInTheDocument();
  });
});
