import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ApiRequestError } from '../src/services/http';
import { ConnectionListPanel } from '../src/components/connections/ConnectionListPanel';
import { ConnectionDetail } from '../src/components/connections/ConnectionDetail';
import { DisconnectConnectionModal } from '../src/components/connections/DisconnectConnectionModal';
import { ConnectionsPage } from '../src/pages/ConnectionsPage';
import { NewConnectionWizard } from '../src/components/connections/NewConnectionWizard';
import type { DatabaseConnection, SchemaResponse } from '../src/types/api';
import type { ConnectionListItem } from '../src/types/connections';
import { MemoryRouter, useLocation } from 'react-router-dom';

const apiMocks = vi.hoisted(() => ({
  listConnections: vi.fn(),
  disconnectDatabase: vi.fn(),
  getSchema: vi.fn(),
  getQueryHistory: vi.fn(),
  updateConnectionSettings: vi.fn(),
  testSavedConnection: vi.fn(),
  connectDatabase: vi.fn(),
  testConnection: vi.fn(),
  rotateConnectionCredentials: vi.fn(),
  discoverConnectionScope: vi.fn(),
  previewConnectionScope: vi.fn(),
  updateConnectionScope: vi.fn(),
  updateConnectionAutomation: vi.fn(),
  getConnectionHealth: vi.fn(),
}));

vi.mock('../src/services/api', () => apiMocks);
vi.mock('../src/context/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'test-user', email: 'test@example.com' },
    loading: false,
    signIn: async () => ({ authenticated: true, user: { id: 'test-user', email: 'test@example.com' } }),
    signUp: async () => ({ authenticated: true, user: { id: 'test-user', email: 'test@example.com' } }),
    signOut: async () => undefined,
    refreshSession: async () => ({ authenticated: true, user: { id: 'test-user', email: 'test@example.com' } }),
    isDevMode: true,
  }),
}));
vi.mock('../src/components/connections/ErdDiagram', () => ({
  ErdDiagram: () => <div>ERD MOCK</div>,
}));
vi.mock('../src/components/connections/SemanticsWorkspace', () => ({
  SemanticsWorkspace: () => <div>BUSINESS DEFINITIONS MOCK</div>,
}));
vi.mock('../src/components/suggestions/SuggestionGrid', () => ({
  SuggestionGrid: () => <div>EXPLORE THIS SOURCE MOCK</div>,
}));
vi.mock('../src/components/common/MainShell', () => ({
  MainShell: ({ children, headerActions }: { children: React.ReactNode; headerActions?: React.ReactNode }) => (
    <main>
      <div>{headerActions}</div>
      {children}
    </main>
  ),
}));

const connectionItem: ConnectionListItem = {
  id: 'conn_1',
  name: 'Warehouse Main',
  type: 'PostgreSQL',
  status: 'live',
  health_state: 'live',
  latency: 24,
  queries: 3,
  icon: 'P',
  color: '#0ea5e9',
  host: 'db.example.com',
  port: 5432,
  database: 'warehouse',
  username: 'reader',
  last_status: 'healthy',
  credential_revision: 1,
  has_ssl_root_certificate: false,
  has_ssl_client_certificate: false,
  has_ssl_client_private_key: false,
  scope_mode: 'all',
  included_schemas: [],
  included_tables: [],
  scope_revision: 1,
  health_check_enabled: false,
  health_check_interval_minutes: 60,
  schema_refresh_enabled: false,
  schema_refresh_interval_hours: 24,
};

const apiConnection: DatabaseConnection = {
  id: 'conn_1',
  name: 'Warehouse Main',
  db_type: 'postgresql',
  database: 'warehouse',
  host: 'db.example.com',
  port: 5432,
  username: 'reader',
  status: 'live',
  health_state: 'live',
  tables_count: 0,
  latency_ms: 24,
  last_status: 'healthy',
  credential_revision: 1,
  has_ssl_root_certificate: false,
  has_ssl_client_certificate: false,
  has_ssl_client_private_key: false,
  scope_mode: 'all',
  included_schemas: [],
  included_tables: [],
  scope_revision: 1,
  health_check_enabled: false,
  health_check_interval_minutes: 60,
  schema_refresh_enabled: false,
  schema_refresh_interval_hours: 24,
};

const schema: SchemaResponse = {
  connection_id: 'conn_1',
  database: 'warehouse',
  tables: [
    {
      name: 'customers',
      row_count: 12,
      columns: [{ name: 'id', type: 'integer', nullable: false, primary_key: true }],
      foreign_keys: [],
    },
  ],
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{JSON.stringify({ pathname: location.pathname, state: location.state })}</output>;
}

describe('connection list states', () => {
  it('renders loading, error, empty, and filtered-empty states separately', async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <ConnectionListPanel connections={[]} activeId={null} status="loading" onSelect={vi.fn()} onAdd={vi.fn()} />
    );

    expect(screen.getByText('LOADING SOURCES')).toBeInTheDocument();

    rerender(
      <ConnectionListPanel connections={[]} activeId={null} status="error" error="Could not load." onSelect={vi.fn()} onAdd={vi.fn()} onRetry={retry} />
    );
    expect(screen.getByText('SOURCE LOAD FAILED')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'RETRY LOAD' }));
    expect(retry).toHaveBeenCalledTimes(1);

    rerender(
      <ConnectionListPanel connections={[]} activeId={null} status="empty" onSelect={vi.fn()} onAdd={vi.fn()} />
    );
    expect(screen.getByText('NO SOURCES CONNECTED')).toBeInTheDocument();

    rerender(
      <ConnectionListPanel connections={[connectionItem]} activeId="conn_1" status="ready" onSelect={vi.fn()} onAdd={vi.fn()} />
    );
    await user.type(screen.getByPlaceholderText('FILTER SOURCES...'), 'missing');
    expect(screen.getByText('NO MATCHING SOURCES')).toBeInTheDocument();
  });
});

describe('connection detail states', () => {
  it('shows four accessible sections and connection-first header actions', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/connections']}><ConnectionDetail connection={connectionItem} schema={schema} schemaState="ready" queryHistory={[]} /><LocationProbe /></MemoryRouter>);

    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getByRole('tab', { name: 'OVERVIEW' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByRole('tab', { name: 'CREDENTIALS' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'SEMANTICS' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'SECURITY' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'SHARE' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'ASK IN CHAT' }));
    expect(screen.getByTestId('location')).toHaveTextContent('"pathname":"/chat"');
    expect(screen.getByTestId('location')).toHaveTextContent('"connectionId":"conn_1"');

    await user.click(screen.getByRole('button', { name: 'BUILD DASHBOARD' }));
    expect(screen.getByTestId('location')).toHaveTextContent('"pathname":"/dashboard"');
    expect(screen.getByTestId('location')).toHaveTextContent('"openAiWizard":true');
    expect(screen.getByTestId('location')).toHaveTextContent('"connectionId":"conn_1"');
  });

  it('shows schema failure as an error state instead of an empty schema', async () => {
    const user = userEvent.setup();
    const refresh = vi.fn();
    render(
      <MemoryRouter><ConnectionDetail
        connection={connectionItem}
        schema={null}
        schemaState="error"
        schemaError="Schema inspection failed."
        queryHistory={[]}
        onRefreshSchema={refresh}
      /></MemoryRouter>
    );

    await user.click(screen.getByRole('tab', { name: 'SCHEMA' }));

    expect(screen.getByText('SCHEMA SYNC FAILED')).toBeInTheDocument();
    expect(screen.queryByText('NO ENTITIES DISCOVERED - VERIFY SOURCE CONNECTION')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'RETRY SYNC' }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('tests saved credentials from the simplified overview', async () => {
    const user = userEvent.setup();
    apiMocks.testSavedConnection.mockResolvedValue({ success: true, message: 'Connection successful', latency_ms: 15 });
    const updated = vi.fn();

    render(
      <MemoryRouter><ConnectionDetail
        connection={connectionItem}
        schema={schema}
        schemaState="ready"
        queryHistory={[]}
        onConnectionUpdated={updated}
      /></MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'TEST CONNECTION' }));

    await waitFor(() => expect(apiMocks.testSavedConnection).toHaveBeenCalledWith('conn_1'));
    expect(await screen.findByText('Connection successful')).toBeInTheDocument();
    expect(updated).toHaveBeenCalledTimes(1);
  });

  it('mounts business definitions only after selecting the nested schema view', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><ConnectionDetail connection={connectionItem} schema={schema} schemaState="ready" queryHistory={[]} /></MemoryRouter>);

    expect(screen.queryByText('BUSINESS DEFINITIONS MOCK')).not.toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'SCHEMA' }));
    expect(screen.queryByText('BUSINESS DEFINITIONS MOCK')).not.toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'BUSINESS DEFINITIONS' }));
    expect(screen.getByText('BUSINESS DEFINITIONS MOCK')).toBeInTheDocument();
  });

  it('loads scope inventory lazily and keeps activity query-only', async () => {
    const user = userEvent.setup();
    apiMocks.discoverConnectionScope.mockResolvedValue({ mode: 'all', included_schemas: [], included_tables: [], revision: 1, inventory: [{ name: 'public', tables: ['orders'] }] });
    const history = [{ id: 'query_1', connection_id: 'conn_1', sql: 'SELECT * FROM orders', success: true, execution_time_ms: 25, timestamp: '2026-07-16T00:00:00Z' }];
    render(<MemoryRouter><ConnectionDetail connection={connectionItem} schema={schema} schemaState="ready" queryHistory={history} queryHistoryState="ready" /></MemoryRouter>);

    await user.click(screen.getByRole('tab', { name: 'SETTINGS' }));
    expect(apiMocks.discoverConnectionScope).not.toHaveBeenCalled();
    const scopeButton = screen.getByRole('button', { name: /DATA ACCESS SCOPE/ });
    expect(scopeButton).toHaveAttribute('aria-expanded', 'false');
    await user.click(scopeButton);
    await waitFor(() => expect(apiMocks.discoverConnectionScope).toHaveBeenCalledWith('conn_1'));

    await user.click(screen.getByRole('tab', { name: 'ACTIVITY' }));
    expect(screen.getByText('SELECT * FROM orders')).toBeInTheDocument();
    expect(apiMocks.getConnectionHealth).not.toHaveBeenCalled();
  });

  it('rotates only supplied credentials and clears plaintext after success', async () => {
    const user = userEvent.setup();
    apiMocks.rotateConnectionCredentials.mockResolvedValue({ ...apiConnection, credential_revision: 2 });
    const updated = vi.fn();
    render(<MemoryRouter><ConnectionDetail connection={connectionItem} schema={schema} schemaState="ready" queryHistory={[]} onConnectionUpdated={updated} /></MemoryRouter>);

    await user.click(screen.getByRole('tab', { name: 'SETTINGS' }));
    expect(screen.getByRole('button', { name: /TRANSPORT SECURITY/ })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText('ROOT CA CERTIFICATE')).not.toBeInTheDocument();

    const password = screen.getByLabelText('NEW DATABASE PASSWORD');
    await user.type(password, 'replacement-password');
    await user.click(screen.getByRole('button', { name: 'SAVE CREDENTIAL CHANGES' }));

    await waitFor(() => expect(apiMocks.rotateConnectionCredentials).toHaveBeenCalledTimes(1));
    expect(apiMocks.rotateConnectionCredentials).toHaveBeenCalledWith('conn_1', {
      expected_credential_revision: 1,
      ssl_mode: 'disable',
      password: 'replacement-password',
    });
    expect(password).toHaveValue('');
    expect(updated).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Credentials updated and tested successfully.')).toBeInTheDocument();
  });

  it('previews and acknowledges scope impact before applying an allowlist', async () => {
    const user = userEvent.setup();
    apiMocks.discoverConnectionScope.mockResolvedValue({ mode: 'all', included_schemas: [], included_tables: [], revision: 1, inventory: [{ name: 'public', tables: ['orders'] }] });
    apiMocks.previewConnectionScope.mockResolvedValue({
      valid: true,
      normalized_scope: { mode: 'allowlist', included_schemas: [], included_tables: ['public.orders'] },
      errors: [],
      warnings: [],
      impacts: [{ code: 'dashboard_uses_table', consumer_type: 'dashboard_widget', consumer_id: 'widget_1', label: 'Revenue widget' }],
    });
    apiMocks.updateConnectionScope.mockResolvedValue({ mode: 'allowlist', included_schemas: [], included_tables: ['public.orders'], revision: 2 });
    const updated = vi.fn();
    render(<MemoryRouter><ConnectionDetail connection={connectionItem} schema={schema} schemaState="ready" queryHistory={[]} onConnectionUpdated={updated} /></MemoryRouter>);

    await user.click(screen.getByRole('tab', { name: 'SETTINGS' }));
    await user.click(screen.getByRole('button', { name: /DATA ACCESS SCOPE/ }));
    await screen.findByLabelText('SCOPE MODE');
    await user.selectOptions(screen.getByLabelText('SCOPE MODE'), 'allowlist');
    await user.click(await screen.findByLabelText('orders'));
    await user.click(screen.getByRole('button', { name: 'PREVIEW IMPACT' }));

    expect(await screen.findByText(/Revenue widget/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'APPLY SCOPE' })).toBeDisabled();
    await user.click(screen.getByLabelText('I acknowledge these impacts'));
    await user.click(screen.getByRole('button', { name: 'APPLY SCOPE' }));

    await waitFor(() => expect(apiMocks.updateConnectionScope).toHaveBeenCalledWith('conn_1', {
      mode: 'allowlist',
      included_schemas: [],
      included_tables: ['public.orders'],
      expected_scope_revision: 1,
      acknowledged_impact_codes: ['dashboard_uses_table'],
    }));
    expect(updated).toHaveBeenCalledTimes(1);
  });
});

describe('disconnect confirmation', () => {
  it('requires confirmation before disconnecting', async () => {
    const user = userEvent.setup();
    const cancel = vi.fn();
    const confirm = vi.fn();

    render(
      <DisconnectConnectionModal
        connection={connectionItem}
        isDisconnecting={false}
        onCancel={cancel}
        onConfirm={confirm}
      />
    );

    expect(screen.getByRole('dialog', { name: 'Disconnect Source' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'CANCEL' }));
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'CONFIRM DISCONNECT' }));
    expect(confirm).toHaveBeenCalledTimes(1);
  });
});

describe('guided connection wizard', () => {
  it('requires current live diagnostics before saving', async () => {
    const user = userEvent.setup();
    apiMocks.testConnection.mockResolvedValue({
      success: true,
      message: 'Connection successful',
      code: 'connection_healthy',
      category: 'success',
      checks: [{ code: 'database', status: 'passed', label: 'Database authenticated' }],
      suggestions: [], warnings: [], inventory: [{ name: 'public', tables: ['orders'] }],
      inventory_truncated: false, tables_found: 1, latency_ms: 12,
    });
    apiMocks.connectDatabase.mockResolvedValue(apiConnection);
    const saved = vi.fn();
    render(<NewConnectionWizard isOpen onClose={vi.fn()} onSaved={saved} />);

    expect(screen.getByRole('button', { name: 'SAVE CONNECTION' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /ADVANCED CONNECTION OPTIONS/ })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText('ROOT CA CERTIFICATE')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'TEST CONNECTION' }));
    expect(await screen.findByText('Connection successful')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'SAVE CONNECTION' })).toBeEnabled();
    expect(screen.getByRole('button', { name: /LIMIT DATA ACCESS/ })).toHaveAttribute('aria-expanded', 'false');

    await user.clear(screen.getByLabelText('HOST'));
    await user.type(screen.getByLabelText('HOST'), 'db.changed.example');
    expect(screen.getByRole('button', { name: 'SAVE CONNECTION' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /LIMIT DATA ACCESS/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'TEST CONNECTION' }));
    expect(await screen.findByText('Connection successful')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'SAVE CONNECTION' }));

    await waitFor(() => expect(apiMocks.connectDatabase).toHaveBeenCalledTimes(1));
    expect(saved).toHaveBeenCalledTimes(1);
    expect(apiMocks.connectDatabase.mock.calls[0][0]).toMatchObject({
      input_mode: 'fields', host: 'db.changed.example', scope_mode: 'all', included_schemas: [], included_tables: [],
    });
  });

  it('clears secret fields when the wizard closes', async () => {
    const user = userEvent.setup();
    const closed = vi.fn();
    render(<NewConnectionWizard isOpen onClose={closed} />);
    await user.type(screen.getByLabelText('PASSWORD'), 'temporary-secret');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(closed).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('PASSWORD')).toHaveValue('');
  });
});

describe('connections page retries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getSchema.mockResolvedValue({ connection_id: 'conn_1', database: 'warehouse', tables: [] });
    apiMocks.getQueryHistory.mockResolvedValue([]);
  });

  it('retries connection list loading after a failed initial request', async () => {
    const user = userEvent.setup();
    apiMocks.listConnections
      .mockRejectedValueOnce(new ApiRequestError('Unavailable', { status: 503, code: 'service_unavailable' }))
      .mockResolvedValueOnce([apiConnection]);

    render(<MemoryRouter><ConnectionsPage /></MemoryRouter>);

    expect(await screen.findByText('SOURCE LOAD FAILED')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'RETRY LOAD' }));

    expect((await screen.findAllByText('Warehouse Main')).length).toBeGreaterThan(0);
    expect(apiMocks.listConnections).toHaveBeenCalledTimes(2);
  });
});
