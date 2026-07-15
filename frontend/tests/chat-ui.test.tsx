import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ChatPage } from '../src/pages/ChatPage';
import { MemoryRouter } from 'react-router-dom';
import type { DatabaseConnection, SessionMessagesResponse, SessionSummary } from '../src/types/api';
import { ApiRequestError } from '../src/services/http';

const apiMocks = vi.hoisted(() => ({
  listConnections: vi.fn(),
  listSessions: vi.fn(),
  getSessionMessages: vi.fn(),
  sendMessage: vi.fn(),
  deleteSession: vi.fn(),
  renameSession: vi.fn(),
  editSql: vi.fn(),
  toggleMessagePin: vi.fn(),
  getSettings: vi.fn(),
  startChatRun: vi.fn(),
  getChatRun: vi.fn(),
  cancelChatRun: vi.fn(),
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
vi.mock('../src/components/common/MainShell', () => ({
  MainShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));
vi.mock('../src/components/chat/MessageBubble', () => ({
  MessageBubble: ({ message }: { message: { content: string; error?: string } }) => (
    <div>{message.error || message.content}</div>
  ),
}));
vi.mock('../src/components/chat/ConnectionModal', () => ({
  ConnectionModal: ({ isOpen }: { isOpen: boolean }) => isOpen ? <div>CONNECTION MODAL MOCK</div> : null,
}));

const connection: DatabaseConnection = {
  id: 'conn_1',
  name: 'Analytics DB',
  db_type: 'postgresql',
  database: 'analytics',
  host: 'db.example.com',
  port: 5432,
  username: 'reader',
  status: 'live',
  health_state: 'live',
  tables_count: 3,
  last_status: 'healthy',
};

const session: SessionSummary = {
  id: 'session_1',
  connection_ids: ['conn_1'],
  last_connection_id: 'conn_1',
  title: 'Revenue check',
  message_count: 2,
  created_at: new Date().toISOString(),
};

const messagesResponse: SessionMessagesResponse = {
  session_id: 'session_1',
  connection_ids: ['conn_1'],
  last_connection_id: 'conn_1',
  messages: [
    {
      id: 'message_1',
      role: 'assistant',
      content: 'Assistant answer',
      timestamp: new Date().toISOString(),
    },
  ],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function renderChatPage() {
  return render(<MemoryRouter initialEntries={['/chat']}><ChatPage /></MemoryRouter>);
}

describe('chat bootstrap states', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiMocks.listConnections.mockResolvedValue([connection]);
    apiMocks.listSessions.mockResolvedValue([]);
    apiMocks.getSessionMessages.mockResolvedValue(messagesResponse);
    apiMocks.getSettings.mockResolvedValue({ stream_responses: false });
  });

  it('shows connection loading state during initial bootstrap', async () => {
    const pendingConnections = deferred<DatabaseConnection[]>();
    apiMocks.listConnections.mockReturnValue(pendingConnections.promise);

    renderChatPage();

    expect(screen.getByText('LOADING DATABASE CONNECTIONS')).toBeInTheDocument();

    pendingConnections.resolve([connection]);
    await screen.findByText(/What would you/i);
  });

  it('shows connection load failure with retry', async () => {
    const user = userEvent.setup();
    apiMocks.listConnections
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce([connection]);

    renderChatPage();

    expect((await screen.findAllByText('SOURCE LOAD FAILED')).length).toBeGreaterThan(0);
    expect(screen.getByText('COULD NOT LOAD DATABASE CONNECTIONS')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'RETRY LOAD' }));

    expect(await screen.findByText(/What would you/i)).toBeInTheDocument();
    expect(apiMocks.listConnections).toHaveBeenCalledTimes(2);
  });

  it('shows no-connection CTA and opens the connection modal', async () => {
    const user = userEvent.setup();
    apiMocks.listConnections.mockResolvedValue([]);

    renderChatPage();

    expect(await screen.findByText('NO DATABASE CONNECTIONS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('CONNECT A DATABASE')).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'CONNECT DATABASE' }));

    expect(screen.getByText('CONNECTION MODAL MOCK')).toBeInTheDocument();
  });

  it('shows sidebar session failure with retry', async () => {
    const user = userEvent.setup();
    apiMocks.listSessions
      .mockRejectedValueOnce(new Error('session service down'))
      .mockResolvedValueOnce([session]);

    renderChatPage();

    expect(await screen.findByText('CONVERSATION LOAD FAILED')).toBeInTheDocument();
    expect(screen.getByText('COULD NOT LOAD CONVERSATIONS')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'RETRY CONVERSATIONS' }));

    expect(await screen.findByText('Revenue check')).toBeInTheDocument();
    expect(apiMocks.listSessions).toHaveBeenCalledTimes(2);
  });

  it('shows message loading while a conversation is selected', async () => {
    const user = userEvent.setup();
    const pendingMessages = deferred<SessionMessagesResponse>();
    apiMocks.listSessions.mockResolvedValue([session]);
    apiMocks.getSessionMessages.mockReturnValue(pendingMessages.promise);

    renderChatPage();

    await user.click(await screen.findByText('Revenue check'));

    expect(screen.getByText('LOADING CONVERSATION')).toBeInTheDocument();

    pendingMessages.resolve(messagesResponse);
    expect(await screen.findByText('Assistant answer')).toBeInTheDocument();
  });

  it('shows message load failure with retry', async () => {
    const user = userEvent.setup();
    apiMocks.listSessions.mockResolvedValue([session]);
    apiMocks.getSessionMessages
      .mockRejectedValueOnce(new Error('message load failed'))
      .mockResolvedValueOnce(messagesResponse);

    renderChatPage();

    await user.click(await screen.findByText('Revenue check'));

    expect(await screen.findByText('COULD NOT LOAD THIS CONVERSATION')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'RETRY MESSAGE LOAD' }));

    expect(await screen.findByText('Assistant answer')).toBeInTheDocument();
    expect(apiMocks.getSessionMessages).toHaveBeenCalledTimes(2);
  });


  it('enforces the visible 2048 character message limit in the input', async () => {
    renderChatPage();

    const input = await screen.findByPlaceholderText('What would you like to know?');

    expect(input).toHaveAttribute('maxLength', '2048');
  });
  it('disables chat send when no active connection exists', async () => {
    apiMocks.listConnections.mockResolvedValue([]);

    renderChatPage();

    expect(await screen.findByText('NO DATABASE CONNECTIONS')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('CONNECT A DATABASE')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
  });

  it('restores a rejected sensitive draft and removes its optimistic bubble', async () => {
    const user = userEvent.setup();
    apiMocks.sendMessage.mockRejectedValue(
      new ApiRequestError('safe rejection', {
        status: 422,
        code: 'chat_sensitive_input_detected',
      }),
    );
    renderChatPage();
    const input = await screen.findByPlaceholderText('What would you like to know?');
    await user.type(input, 'synthetic rejected draft');
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Remove the credential from this message and rotate it before continuing.',
    );
    expect(screen.getByDisplayValue('synthetic rejected draft')).toBeInTheDocument();
    expect(
      screen.queryAllByText('synthetic rejected draft').filter((element) => element.tagName !== 'TEXTAREA'),
    ).toHaveLength(0);
  });
});
