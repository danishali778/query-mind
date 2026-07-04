import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
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
  it('keeps real message actions and removes inactive controls', () => {
    render(<MessageBubble message={assistantMessage} connectionId="conn_1" onTogglePin={vi.fn()} />);

    expect(screen.getByText('COPY SQL')).toBeInTheDocument();
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
});