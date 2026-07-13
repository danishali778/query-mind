import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { SuggestionGrid } from '../src/components/suggestions/SuggestionGrid';
import type { QuestionSuggestionResponse } from '../src/types/questionSuggestions';


const apiMocks = vi.hoisted(() => ({
  getQuestionSuggestions: vi.fn(),
  refreshQuestionSuggestions: vi.fn(),
  dismissQuestionSuggestion: vi.fn(),
}));

vi.mock('../src/services/api', () => apiMocks);

const fallback: QuestionSuggestionResponse = {
  connection_id: 'connection-1',
  surface: 'chat',
  status: 'fallback',
  context_fingerprint: 'a'.repeat(64),
  schema_hash: 'schema-1',
  suggestions: [{
    id: 'qs_1234567890abcdef',
    surface: 'chat',
    title: 'Monthly revenue',
    prompt: 'Show monthly revenue for the latest periods.',
    rationale: 'Revenue and an order date are available.',
    category: 'trend',
    source: 'deterministic',
    based_on: ['Revenue', 'Order date'],
  }],
  refresh_required: true,
  ai_available: true,
  generated_at: null,
  failure: null,
};

describe('schema-aware question suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getQuestionSuggestions.mockResolvedValue(fallback);
    apiMocks.refreshQuestionSuggestions.mockResolvedValue({
      ...fallback,
      status: 'ready',
      refresh_required: false,
      suggestions: fallback.suggestions.map((item) => ({ ...item, source: 'ai' })),
    });
    apiMocks.dismissQuestionSuggestion.mockResolvedValue({
      ...fallback,
      status: 'ready',
      refresh_required: false,
      suggestions: [],
    });
  });

  it('renders deterministic ideas and lazily enriches once without selecting them', async () => {
    const onSelect = vi.fn();
    render(
      <SuggestionGrid
        connectionId="connection-1"
        surface="chat"
        onSelect={onSelect}
        primaryLabel="Fill composer"
      />,
    );

    expect(await screen.findByText('Monthly revenue')).toBeInTheDocument();
    await waitFor(() => expect(apiMocks.refreshQuestionSuggestions).toHaveBeenCalledTimes(1));
    expect(onSelect).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Fill composer' }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      prompt: 'Show monthly revenue for the latest periods.',
    }));
  });

  it('dismisses a card using the current fingerprint', async () => {
    render(
      <SuggestionGrid
        connectionId="connection-1"
        surface="chat"
        onSelect={() => undefined}
      />,
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss Monthly revenue' }));
    await waitFor(() => expect(apiMocks.dismissQuestionSuggestion).toHaveBeenCalledWith(
      'connection-1',
      'chat',
      'qs_1234567890abcdef',
      'a'.repeat(64),
    ));
  });
});
