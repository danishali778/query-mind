import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthPage } from '../src/pages/AuthPage';
import { useAuth } from '../src/context/useAuth';


const navigate = vi.fn();
const signIn = vi.fn();
const signUp = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
}));

vi.mock('../src/context/useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('authentication page validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      signIn,
      signUp,
      signOut: vi.fn(),
      refreshSession: vi.fn(),
      isDevMode: false,
    });
  });

  it('keeps legacy login passwords valid while bounding their length', () => {
    render(<AuthPage />);

    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('minlength', '1');
    expect(password).toHaveAttribute('maxlength', '1024');
    expect(screen.queryByText(/use at least 12 characters/i)).not.toBeInTheDocument();
  });

  it('requires twelve characters only in signup mode', () => {
    render(<AuthPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('minlength', '12');
    expect(password).toHaveAttribute('maxlength', '1024');
    expect(password).toHaveAccessibleDescription('Use at least 12 characters.');
  });
});
