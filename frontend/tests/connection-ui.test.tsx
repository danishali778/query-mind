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
  it('shows schema failure as an error state instead of an empty schema', async () => {
    const user = userEvent.setup();
    const refresh = vi.fn();
    render(
      <ConnectionDetail
        connection={connectionItem}
        schema={null}
        schemaState="error"
        schemaError="Schema inspection failed."
        queryHistory={[]}
        onRefreshSchema={refresh}
      />
    );

    await user.click(screen.getByText('SCHEMA'));

    expect(screen.getByText('SCHEMA SYNC FAILED')).toBeInTheDocument();
    expect(screen.queryByText('NO ENTITIES DISCOVERED - VERIFY SOURCE CONNECTION')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'RETRY SYNC' }));
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('runs saved credential diagnostics from the credentials tab', async () => {
    const user = userEvent.setup();
    apiMocks.testSavedConnection.mockResolvedValue({ success: true, message: 'Connection successful', latency_ms: 15 });

    render(
      <ConnectionDetail
        connection={connectionItem}
        schema={schema}
        schemaState="ready"
        queryHistory={[]}
      />
    );

    await user.click(screen.getByText('CREDENTIALS'));
    await user.click(screen.getByRole('button', { name: 'RE-RUN DIAGNOSTICS' }));

    await waitFor(() => expect(apiMocks.testSavedConnection).toHaveBeenCalledWith('conn_1'));
    expect(await screen.findByText('CONNECTION SUCCESSFUL')).toBeInTheDocument();
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

    await user.click(screen.getByRole('button', { name: /NEXT/ }));
    await user.click(screen.getByRole('button', { name: /NEXT/ }));
    expect(screen.getByRole('button', { name: /NEXT/ })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'RUN CONNECTION TEST' }));
    expect(await screen.findByText('Connection successful')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /NEXT/ }));
    await user.click(screen.getByRole('button', { name: 'SAVE CONNECTION' }));

    await waitFor(() => expect(apiMocks.connectDatabase).toHaveBeenCalledTimes(1));
    expect(saved).toHaveBeenCalledTimes(1);
    expect(apiMocks.connectDatabase.mock.calls[0][0]).toMatchObject({
      input_mode: 'fields', scope_mode: 'all', included_schemas: [], included_tables: [],
    });
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

    render(<ConnectionsPage />);

    expect(await screen.findByText('SOURCE LOAD FAILED')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'RETRY LOAD' }));

    expect((await screen.findAllByText('Warehouse Main')).length).toBeGreaterThan(0);
    expect(apiMocks.listConnections).toHaveBeenCalledTimes(2);
  });
});
