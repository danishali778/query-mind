import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { T } from '../components/dashboard/tokens';
import { useAuth } from '../context/AuthContext';
import { Mail, ChevronRight, Activity, Globe, LockKeyhole } from 'lucide-react';
import { LandingOverlay } from '../components/landing/LandingOverlay';

export function AuthPage() {
  const navigate = useNavigate();
  const { user, isDevMode, signIn, signUp } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);

  useEffect(() => {
    if (user || isDevMode) {
      navigate('/dashboard');
    }

    const logs = [
      'SECURE_GATEWAY_INITIALIZED',
      'LISTENING_ON_PORT_443',
      'ENCRYPTION_LAYER: AES-256',
      'SCANNING_IDENTITY_SIGNALS...',
      'NODE_READY_FOR_HANDSHAKE',
    ];
    let i = 0;
    const iv = setInterval(() => {
      if (i < logs.length) {
        setAuditLogs(prev => [...prev, logs[i++]]);
      }
    }, 1000);
    return () => clearInterval(iv);
  }, [user, isDevMode, navigate]);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);

      const session = isLogin
        ? await signIn(email, password)
        : await signUp(email, password);

      if (session.authenticated) {
        navigate('/dashboard');
        return;
      }

      setError((session.message || 'Check your email to complete sign up.').toUpperCase());
    } catch (err: any) {
      setError(err.message?.toUpperCase() || 'AUTHENTICATION_FAILURE');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: T.bg, position: 'relative', overflow: 'hidden' }}>
      <LandingOverlay />

      <div
        style={{
          flex: 1, position: 'relative', overflow: 'hidden', background: T.text,
          display: 'flex', flexDirection: 'column', padding: 60, color: T.bg
        }}
        className="auth-visual"
      >
        <div
          style={{
            position: 'absolute', inset: 0,
            backgroundImage: `linear-gradient(${T.accent}11 1px, transparent 1px), linear-gradient(90deg, ${T.accent}11 1px, transparent 1px)`,
            backgroundSize: '40px 40px', opacity: 0.3
          }}
        />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <div
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 12,
              background: 'rgba(0,0,0,0.3)', border: `1px solid ${T.accent}33`,
              padding: '8px 16px', fontFamily: T.fontMono, fontSize: '0.55rem',
              letterSpacing: 2, fontWeight: 950, marginBottom: 40
            }}
          >
            <Activity size={10} color={T.accent} />
            SECURITY_AUDIT_PROTOCOL
          </div>

          <h2
            style={{
              fontFamily: T.fontHead, fontWeight: 950, fontSize: '4.5rem',
              letterSpacing: -3, lineHeight: 0.9, textTransform: 'uppercase', fontStyle: 'italic'
            }}
          >
            PROTECTING_YOUR_<br />
            <span style={{ color: T.accent }}>INTELLIGENCE.</span>
          </h2>
        </div>

        <div style={{ marginTop: 'auto', position: 'relative', zIndex: 1 }}>
          <div
            style={{
              fontFamily: T.fontMono, fontSize: '0.6rem', color: T.accent,
              display: 'flex', flexDirection: 'column', gap: 8
            }}
          >
            {auditLogs.map((log, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, opacity: 0.7 + (i * 0.05) }}>
                <span style={{ color: T.accent }}>[{new Date().toLocaleTimeString()}]</span>
                <span>{'>'} {log}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div
        style={{
          width: 600, display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 40, borderLeft: `1px solid ${T.border}`, background: T.bg, zIndex: 1
        }}
        className="auth-form-container"
      >
        <div style={{ width: '100%', maxWidth: 400 }}>
          <div style={{ marginBottom: 48 }}>
            <div
              style={{
                width: 40, height: 40, background: T.text, display: 'flex',
                alignItems: 'center', justifyContent: 'center', color: '#fff',
                fontFamily: T.fontHead, fontWeight: 950, fontSize: '1.4rem',
                marginBottom: 32, boxShadow: `6px 6px 0px ${T.accent}`
              }}
            >Q</div>
            <h1
              style={{
                fontFamily: T.fontHead, fontWeight: 950, fontSize: '2.5rem',
                letterSpacing: -1, textTransform: 'uppercase', marginBottom: 12
              }}
            >
              {isLogin ? 'Welcome Back' : 'Get Started'}
            </h1>
            <p style={{ fontFamily: T.fontMono, fontSize: '0.65rem', color: T.text3, textTransform: 'uppercase', letterSpacing: 1.5, fontWeight: 800 }}>
              {isLogin ? 'Sign in to access your data nodes' : 'Create an account to begin initialization'}
            </p>
          </div>

          {error && (
            <div
              style={{
                padding: '16px', background: `${T.red}11`, border: `1px solid ${T.red}`,
                color: T.red, fontFamily: T.fontMono, fontSize: '0.7rem', fontWeight: 950,
                marginBottom: 32, textTransform: 'uppercase'
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleEmailAuth} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <label style={{ display: 'block', fontFamily: T.fontMono, fontSize: '0.6rem', fontWeight: 950, letterSpacing: 1.5, marginBottom: 8, color: T.text3, textTransform: 'uppercase' }}>Email Address</label>
              <div style={{ position: 'relative' }}>
                <Mail size={16} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: T.text3 }} />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  style={{
                    width: '100%', padding: '16px 16px 16px 48px', background: T.s2,
                    border: `1px solid ${T.border}`, fontFamily: T.fontMono, fontSize: '0.8rem',
                    color: T.text, outline: 'none', transition: 'all 0.2s'
                  }}
                  onFocus={e => e.currentTarget.style.borderColor = T.accent}
                  onBlur={e => e.currentTarget.style.borderColor = T.border}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontFamily: T.fontMono, fontSize: '0.6rem', fontWeight: 950, letterSpacing: 1.5, marginBottom: 8, color: T.text3, textTransform: 'uppercase' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <LockKeyhole size={16} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: T.text3 }} />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="............"
                  style={{
                    width: '100%', padding: '16px 16px 16px 48px', background: T.s2,
                    border: `1px solid ${T.border}`, fontFamily: T.fontMono, fontSize: '0.8rem',
                    color: T.text, outline: 'none', transition: 'all 0.2s'
                  }}
                  onFocus={e => e.currentTarget.style.borderColor = T.accent}
                  onBlur={e => e.currentTarget.style.borderColor = T.border}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                background: T.text, color: T.bg, padding: '18px', fontWeight: 950,
                fontFamily: T.fontMono, fontSize: '0.8rem', textTransform: 'uppercase',
                letterSpacing: 3, border: 'none', cursor: 'pointer',
                transition: 'all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12
              }}
              onMouseEnter={e => { e.currentTarget.style.background = T.accent; e.currentTarget.style.color = '#000'; }}
              onMouseLeave={e => { e.currentTarget.style.background = T.text; e.currentTarget.style.color = T.bg; }}
            >
              {loading ? 'PROCESSING...' : (isLogin ? 'Sign In' : 'Sign Up')}
              <ChevronRight size={16} />
            </button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', margin: '40px 0', color: T.border }}>
            <div style={{ flex: 1, height: 1, background: T.border }} />
            <span style={{ padding: '0 20px', fontFamily: T.fontMono, fontSize: '0.6rem', fontWeight: 950, letterSpacing: 2 }}>GOOGLE OAUTH DEFERRED</span>
            <div style={{ flex: 1, height: 1, background: T.border }} />
          </div>

          <button
            disabled
            style={{
              width: '100%', padding: '16px', background: 'transparent',
              border: `1px solid ${T.border}`, color: T.text3, fontWeight: 950,
              fontFamily: T.fontMono, fontSize: '0.75rem', textTransform: 'uppercase',
              letterSpacing: 2, cursor: 'not-allowed', opacity: 0.65,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12
            }}
          >
            <Globe size={16} />
            Google Identity Soon
          </button>

          <p style={{ textAlign: 'center', marginTop: 40, fontFamily: T.fontMono, fontSize: '0.65rem', color: T.text3, fontWeight: 800, textTransform: 'uppercase', letterSpacing: 1 }}>
            {isLogin ? "Don't have an account?" : 'Already have an account?'}
            <button
              onClick={() => setIsLogin(!isLogin)}
              style={{ background: 'none', border: 'none', color: T.accent, fontWeight: 950, cursor: 'pointer', marginLeft: 8, textTransform: 'uppercase' }}
            >
              {isLogin ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
