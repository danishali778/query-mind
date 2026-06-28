import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
  onboardUser: () => Promise<void>;
  isDevMode: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Developer Bypass Configuration
const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true';
const MOCK_USER: User = {
  id: '00000000-0000-0000-0000-000000000000',
  email: 'dev@query-mind.com',
  role: 'authenticated',
  aud: 'authenticated',
  created_at: new Date().toISOString(),
  app_metadata: {},
  user_metadata: { full_name: 'Dev Guest' },
} as any;

const MOCK_SESSION: Session = {
  access_token: 'dev-token',
  token_type: 'bearer',
  expires_in: 3600,
  refresh_token: 'dev-refresh',
  user: MOCK_USER,
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(DEV_MODE ? MOCK_USER : null);
  const [session, setSession] = useState<Session | null>(DEV_MODE ? MOCK_SESSION : null);
  const [loading, setLoading] = useState(!DEV_MODE);

  useEffect(() => {
    if (DEV_MODE) {
      setLoading(false);
      return;
    }

    // Get initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      if (session?.user && !DEV_MODE) {
        // Silently ensure onboarding on every load
        try {
          const { request } = await import('../services/http');
          await request('/settings/onboard', { method: 'POST' });
        } catch (e) {
          console.warn("Onboarding check failed", e);
        }
      }
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    if (DEV_MODE) {
      console.warn('Sign out is disabled in DEV_MODE');
      return;
    }
    await supabase.auth.signOut();
  };

  const onboardUser = async () => {
    if (DEV_MODE) return;
    const { request } = await import('../services/http');
    try {
      await request('/settings/onboard', { method: 'POST' });
    } catch (err) {
      console.error('Failed to onboard user:', err);
      throw err;
    }
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut, onboardUser, isDevMode: DEV_MODE }}>
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
