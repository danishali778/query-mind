import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Check, Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { useAuth } from '../context/useAuth';
import { ApiRequestError } from '../services/http';
import { AuthBrandPanel } from '../components/auth/AuthBrandPanel';
import { GitHubIcon, GoogleIcon } from '../components/auth/SocialIcons';
import { L, gradient, glow, raisedAccent } from '../components/landing/tokens';

const SIGNUP_PASSWORD_MIN_LENGTH = 12;
const PASSWORD_MAX_LENGTH = 1024;

function authErrorMessage(error: unknown, isLogin: boolean): string {
  if (error instanceof ApiRequestError) {
    if (isLogin && error.status === 401) {
      return 'Invalid email or password.';
    }
    if (!isLogin && [400, 422].includes(error.status)) {
      return 'Could not create account. Check your email and password.';
    }
    if (
      error.status === 0 ||
      error.status === 503 ||
      error.code === 'network_error' ||
      error.code === 'service_unavailable'
    ) {
      return 'Authentication is temporarily unavailable. Please try again shortly.';
    }
  }

  return 'Authentication failed. Please try again.';
}

const inputBase: React.CSSProperties = {
  width: '100%',
  fontFamily: L.fontBody,
  fontSize: 15,
  fontWeight: 500,
  color: L.text,
  padding: '13px 14px 13px 42px',
  borderRadius: 12,
  background: L.surface,
  border: `1px solid ${L.border}`,
  outline: 'none',
  boxShadow: L.inset,
  transition: 'border-color 0.2s, box-shadow 0.2s',
};

const labelText: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: L.text2,
};

export function AuthPage() {
  const navigate = useNavigate();
  const { user, isDevMode, signIn, signUp } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user || isDevMode) {
      navigate('/dashboard');
    }
  }, [user, isDevMode, navigate]);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);

      const session = isLogin ? await signIn(email, password) : await signUp(email, password);

      if (session.authenticated) {
        navigate('/dashboard');
        return;
      }

      setError(session.message || 'Check your email to complete sign up.');
    } catch (err) {
      setError(authErrorMessage(err, isLogin));
    } finally {
      setLoading(false);
    }
  };

  const focusRing = (el: HTMLInputElement) => {
    el.style.borderColor = L.sky.base;
    el.style.boxShadow = `${L.inset}, 0 0 0 3px ${glow(L.sky.base, 0.18)}`;
  };
  const blurRing = (el: HTMLInputElement) => {
    el.style.borderColor = L.border;
    el.style.boxShadow = L.inset;
  };

  return (
    <div className="auth-split" style={{ minHeight: '100vh', fontFamily: L.fontBody, color: L.text, background: L.bg }}>
      <AuthBrandPanel />

      {/* form panel */}
      <div
        className="auth-form-panel"
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          padding: '40px clamp(24px, 5vw, 56px)',
          background: L.bg,
        }}
      >
        {/* top switch */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            gap: 12,
            fontSize: 14,
            fontWeight: 600,
            color: L.text2,
          }}
        >
          <span>{isLogin ? 'New to QueryMind?' : 'Already have an account?'}</span>
          <button
            type="button"
            className="auth-switch-btn"
            onClick={() => {
              setIsLogin((v) => !v);
              setError(null);
              setAgree(false);
            }}
            style={{
              fontFamily: L.fontBody,
              fontWeight: 700,
              fontSize: 14,
              color: L.sky.deep,
              padding: '8px 16px',
              borderRadius: 10,
              border: `1px solid ${L.border}`,
              background: L.surface,
              boxShadow: L.raised,
              cursor: 'pointer',
            }}
          >
            {isLogin ? 'Create account' : 'Sign in'}
          </button>
        </div>

        {/* form body */}
        <div style={{ margin: 'auto', width: '100%', maxWidth: 404 }}>
          <div key={isLogin ? 'login' : 'signup'} style={{ animation: `qm-fade-up 0.5s ${L.ease} both` }}>
            <h1
              style={{
                fontFamily: L.fontDisplay,
                fontWeight: 800,
                fontSize: 'clamp(2rem, 4vw, 38px)',
                lineHeight: 1.05,
                letterSpacing: '-0.04em',
                margin: '0 0 10px',
              }}
            >
              {isLogin ? 'Welcome back' : 'Create your account'}
            </h1>
            <p style={{ fontSize: 15.5, lineHeight: 1.55, color: L.text2, fontWeight: 500, margin: '0 0 30px' }}>
              {isLogin
                ? 'Sign in to keep talking to your data.'
                : 'Start querying in plain English — free for individuals, no card required.'}
            </p>

            {/* social — not yet wired to the backend */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
              {[
                { label: 'Google', icon: <GoogleIcon /> },
                { label: 'GitHub', icon: <GitHubIcon /> },
              ].map((s) => (
                <button
                  key={s.label}
                  type="button"
                  disabled
                  title="Coming soon"
                  aria-label={`Continue with ${s.label} — coming soon`}
                  style={{
                    flex: 1,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 9,
                    fontFamily: L.fontBody,
                    fontSize: 14.5,
                    fontWeight: 700,
                    color: L.text2,
                    padding: 12,
                    borderRadius: 12,
                    background: L.surface,
                    border: `1px solid ${L.border}`,
                    boxShadow: L.raised,
                    cursor: 'not-allowed',
                    opacity: 0.6,
                  }}
                >
                  {s.icon}
                  {s.label}
                  <span
                    style={{
                      fontSize: 9.5,
                      fontWeight: 700,
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                      color: L.text3,
                      background: L.surfaceSunken,
                      borderRadius: 5,
                      padding: '2px 5px',
                    }}
                  >
                    Soon
                  </span>
                </button>
              ))}
            </div>

            {/* divider */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                marginBottom: 24,
                color: L.text3,
                fontSize: 12.5,
                fontWeight: 700,
                letterSpacing: '0.04em',
              }}
            >
              <span style={{ flex: 1, height: 1, background: L.border }} />
              OR
              <span style={{ flex: 1, height: 1, background: L.border }} />
            </div>

            {error && (
              <div
                role="alert"
                aria-live="polite"
                style={{
                  padding: '12px 14px',
                  marginBottom: 20,
                  borderRadius: 12,
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.35)',
                  color: '#b91c1c',
                  fontSize: 13.5,
                  fontWeight: 600,
                }}
              >
                {error}
              </div>
            )}

            <form onSubmit={handleEmailAuth} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                <label htmlFor="auth-email" style={labelText}>
                  Email address
                </label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <Mail
                    size={17}
                    style={{ position: 'absolute', left: 14, color: L.text3, pointerEvents: 'none' }}
                    aria-hidden="true"
                  />
                  <input
                    id="auth-email"
                    type="email"
                    name="email"
                    autoComplete="email"
                    required
                    maxLength={320}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    style={inputBase}
                    onFocus={(e) => focusRing(e.currentTarget)}
                    onBlur={(e) => blurRing(e.currentTarget)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                <label htmlFor="auth-password" style={labelText}>
                  Password
                </label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <Lock
                    size={17}
                    style={{ position: 'absolute', left: 14, color: L.text3, pointerEvents: 'none' }}
                    aria-hidden="true"
                  />
                  <input
                    id="auth-password"
                    type={showPw ? 'text' : 'password'}
                    name="password"
                    autoComplete={isLogin ? 'current-password' : 'new-password'}
                    required
                    minLength={isLogin ? 1 : SIGNUP_PASSWORD_MIN_LENGTH}
                    maxLength={PASSWORD_MAX_LENGTH}
                    aria-describedby={!isLogin ? 'signup-password-guidance' : undefined}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isLogin ? 'Enter your password' : 'Create a password'}
                    style={{ ...inputBase, paddingRight: 44 }}
                    onFocus={(e) => focusRing(e.currentTarget)}
                    onBlur={(e) => blurRing(e.currentTarget)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 4,
                      border: 'none',
                      background: 'transparent',
                      color: L.text3,
                      cursor: 'pointer',
                    }}
                  >
                    {showPw ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
                {!isLogin && (
                  <span id="signup-password-guidance" style={{ fontSize: 12, color: L.text3, fontWeight: 500, marginTop: 1 }}>
                    Use at least {SIGNUP_PASSWORD_MIN_LENGTH} characters.
                  </span>
                )}
              </div>

              {/* decorative meta row */}
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  fontSize: 13.5,
                  fontWeight: 600,
                  color: L.text2,
                  cursor: 'pointer',
                  marginTop: 2,
                }}
              >
                <input
                  type="checkbox"
                  checked={agree}
                  onChange={(e) => setAgree(e.target.checked)}
                  style={{ position: 'absolute', opacity: 0, width: 1, height: 1 }}
                />
                <span
                  aria-hidden="true"
                  style={{
                    width: 19,
                    height: 19,
                    borderRadius: 6,
                    border: `1px solid ${agree ? L.sky.base : L.border}`,
                    background: agree ? gradient(L.sky) : L.surface,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.8)',
                    transition: 'background 0.15s, border-color 0.15s',
                  }}
                >
                  {agree && <Check size={12} strokeWidth={3.2} color="#fff" />}
                </span>
                {isLogin ? 'Keep me signed in' : 'I agree to the Terms & Privacy Policy'}
              </label>

              <button
                type="submit"
                disabled={loading}
                className="auth-submit"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 9,
                  fontFamily: L.fontBody,
                  fontSize: 16,
                  fontWeight: 700,
                  color: '#fff',
                  padding: 15,
                  border: 'none',
                  borderRadius: 13,
                  cursor: loading ? 'wait' : 'pointer',
                  background: gradient(L.sky),
                  boxShadow: raisedAccent(L.sky, 0.45),
                  opacity: loading ? 0.75 : 1,
                  marginTop: 6,
                }}
              >
                {loading ? 'Processing…' : isLogin ? 'Sign in' : 'Create account'}
                {!loading && <ArrowRight size={16} strokeWidth={2.4} />}
              </button>
            </form>

            <p style={{ fontSize: 12, lineHeight: 1.55, color: L.text3, fontWeight: 500, margin: '22px 0 0', textAlign: 'center' }}>
              {isLogin
                ? 'Read-only by default · Encrypted in transit'
                : 'By creating an account you agree to our Terms and Privacy Policy.'}
            </p>
          </div>
        </div>

        {/* bottom */}
        <div style={{ textAlign: 'center', fontSize: 13, color: L.text3, fontWeight: 500 }}>
          <a href="/" style={{ color: L.text2, fontWeight: 600, textDecoration: 'none' }}>
            ← Back to home
          </a>
        </div>
      </div>
    </div>
  );
}
