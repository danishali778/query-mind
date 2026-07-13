import { createContext, useContext } from 'react';
import type { AuthSessionResponse, AuthUserResponse } from '../types/api';

export interface AuthContextType {
  user: AuthUserResponse | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<AuthSessionResponse>;
  signUp: (email: string, password: string) => Promise<AuthSessionResponse>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<AuthSessionResponse | null>;
  isDevMode: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
