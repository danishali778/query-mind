import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  getAuthSession,
  signIn as signInRequest,
  signOut as signOutRequest,
  signUp as signUpRequest,
} from '../services/auth';
import type { AuthSessionResponse, AuthUserResponse } from '../types/api';

interface AuthContextType {
  user: AuthUserResponse | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<AuthSessionResponse>;
  signUp: (email: string, password: string) => Promise<AuthSessionResponse>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<AuthSessionResponse | null>;
  isDevMode: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true';
const MOCK_USER: AuthUserResponse = {
  id: '00000000-0000-0000-0000-000000000000',
  email: 'dev@query-mind.com',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUserResponse | null>(DEV_MODE ? MOCK_USER : null);
  const [loading, setLoading] = useState(!DEV_MODE);

  const refreshSession = async (): Promise<AuthSessionResponse | null> => {
    if (DEV_MODE) {
      setUser(MOCK_USER);
      return { authenticated: true, user: MOCK_USER };
    }

    try {
      const session = await getAuthSession();
      setUser(session.authenticated ? session.user : null);
      return session;
    } catch {
      setUser(null);
      return null;
    }
  };

  useEffect(() => {
    if (DEV_MODE) {
      setLoading(false);
      return;
    }

    void refreshSession().finally(() => setLoading(false));
  }, []);

  const signIn = async (email: string, password: string) => {
    const session = await signInRequest({ email, password });
    setUser(session.authenticated ? session.user : null);
    return session;
  };

  const signUp = async (email: string, password: string) => {
    const session = await signUpRequest({ email, password });
    setUser(session.authenticated ? session.user : null);
    return session;
  };

  const signOut = async () => {
    if (DEV_MODE) {
      setUser(MOCK_USER);
      return;
    }

    try {
      await signOutRequest();
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut, refreshSession, isDevMode: DEV_MODE }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

