import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { SemanticsWorkspace } from '../src/components/connections/SemanticsWorkspace';
import { MessageBubble } from '../src/components/chat/MessageBubble';
import { ToastProvider } from '../src/components/common/ToastProvider';
import type { SchemaResponse } from '../src/types/api';

const semanticsMocks = vi.hoisted(() => ({
  getSemanticSummary: vi.fn(),
  listSemanticDefinitions: vi.fn(),
  createSemanticDefinition: vi.fn(),
  getSemanticDefinition: vi.fn(),
  updateSemanticDraft: vi.fn(),
  createSemanticVersion: vi.fn(),
  deleteSemanticDraft: vi.fn(),
  validateSemanticVersion: vi.fn(),
  verifySemanticVersion: vi.fn(),
  deprecateSemanticVersion: vi.fn(),
  getSemanticImpact: vi.fn(),
  startSemanticSuggestions: vi.fn(),
  getSemanticSuggestions: vi.fn(),
  cancelSemanticSuggestions: vi.fn(),
}));

vi.mock('../src/services/semantics', () => semanticsMocks);

const schema: SchemaResponse = {
  connection_id: 'connection-1',
  database: 'analytics',
  tables: [
    {
      name: 'orders',
      columns: [
        { name: 'id', type: 'integer', nullable: false, primary_key: true },
        { name: 'total', type: 'numeric', nullable: false, primary_key: false },
      ],
      foreign_keys: [],
    },
  ],
};

describe('semantic workspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    semanticsMocks.getSemanticSummary.mockResolvedValue({
      connection_id: 'connection-1', schema_hash: 'hash-1', total: 1,
      draft: 0, verified: 1, deprecated: 0, invalid: 0, stale: 1,
    });
    semanticsMocks.listSemanticDefinitions.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
  });

  it('loads per connection, exposes drift state, and opens a kind-aware editor', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<SemanticsWorkspace connectionId="connection-1" schema={schema} />);

    expect(await screen.findByText(/became stale after schema drift/i)).toBeInTheDocument();
    expect(semanticsMocks.getSemanticSummary).toHaveBeenCalledWith('connection-1');

    await user.click(screen.getByRole('button', { name: /new definition/i }));
    expect(screen.getByRole('dialog', { name: /new semantic definition/i })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Kind'), 'metric');
    expect(screen.getByText('Aggregate formula')).toBeInTheDocument();

    const closeButtons = screen.getAllByRole('button', { name: 'Close' });
    await user.click(closeButtons[closeButtons.length - 1]);
    rerender(<SemanticsWorkspace connectionId="connection-2" schema={schema} />);
    await waitFor(() => expect(semanticsMocks.getSemanticSummary).toHaveBeenCalledWith('connection-2'));
  });
});

describe('semantic lineage disclosure', () => {
  it('shows exact definition versions and policy roles on chat answers', async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider><MessageBubble
        message={{
          id: 'message-1',
          role: 'assistant',
          content: 'Revenue is 42.',
          semantic_lineage: [
            {
              definition_id: 'definition-1', version_id: 'version-3', reference: 'sem_metric_revenue_v3',
              kind: 'metric', display_name: 'Revenue', version: 3, usage_role: 'applied', verification_status: 'verified',
            },
          ],
        }}
      /></ToastProvider>,
    );
    await user.click(screen.getByRole('button', { name: /show definitions used/i }));
    expect(screen.getAllByText(/Revenue/).length).toBeGreaterThan(1);
    expect(screen.getByText(/V3/)).toBeInTheDocument();
  });
});
