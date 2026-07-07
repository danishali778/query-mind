import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import { T } from '../dashboard/tokens';

const NAV_LINKS = [
  { href: '#features', label: '01_FEATURES' },
  { href: '#how', label: '02_WORKFLOW' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [uptime, setUptime] = useState('99.982%');

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    
    // Mock uptime drift
    const interval = setInterval(() => {
      setUptime((99.98 + Math.random() * 0.01).toFixed(3) + '%');
    }, 3000);
    
    return () => {
      window.removeEventListener('scroll', handleScroll);
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [menuOpen]);

  const navPadding = scrolled ? '16px clamp(16px, 4vw, 40px)' : '24px clamp(16px, 4vw, 60px)';

  return (
    <nav 
      style={{ 
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 900, 
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
        padding: navPadding,
        background: scrolled ? 'rgba(252, 250, 247, 0.85)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px) saturate(180%)' : 'none',
        borderBottom: `1px solid ${scrolled ? T.border : 'transparent'}`,
        transition: 'all 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)',
        gap: 16,
        minWidth: 0,
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ 
          width: 32, height: 32, background: T.text, display: 'flex', 
          alignItems: 'center', justifyContent: 'center', color: '#fff', 
          fontSize: '1.2rem', fontWeight: 950, fontFamily: T.fontHead,
          boxShadow: `4px 4px 0px ${T.accent}`
        }}>Q</div>
        <div style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(1rem, 2.5vw, 1.4rem)', letterSpacing: '-1px', color: T.text, textTransform: 'uppercase' }}>
          QUERY<span style={{ color: T.accent }}>MIND</span>
        </div>
      </div>

      {/* Center Telemetry (Desktop) */}
      <div style={{ 
        display: 'flex', alignItems: 'center', gap: 24, 
        padding: '6px 20px', background: T.s2, border: `1px solid ${T.border}`,
        fontFamily: T.fontMono, fontSize: '0.6rem', color: T.text3,
        fontWeight: 900, letterSpacing: '1.5px', textTransform: 'uppercase'
      }} className="nav-telemetry">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 6, height: 6, background: T.green, borderRadius: '50%' }} />
          SYSTEM_READY
        </div>
        <div style={{ width: 1, height: 12, background: T.border }} />
        <div>UPTIME: <span style={{ color: T.text2 }}>{uptime}</span></div>
        <div style={{ width: 1, height: 12, background: T.border }} />
        <div>SECURE_NODE: <span style={{ color: T.text2 }}>778_ALPHA</span></div>
      </div>

      {/* Desktop Links */}
      <ul className="nav-desktop-links" style={{ display: 'flex', gap: 32, listStyle: 'none', alignItems: 'center', margin: 0, padding: 0, flexShrink: 0 }}>
        {NAV_LINKS.map((link) => (
          <li key={link.href}>
            <a href={link.href} style={{ color: T.text2, textDecoration: 'none', fontSize: '0.65rem', fontWeight: 950, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1.5px', transition: 'color 0.2s' }}>
              {link.label}
            </a>
          </li>
        ))}
        <li style={{ width: 1, height: 16, background: T.border, marginLeft: 8, marginRight: 8 }} />
        <li>
          <a href="/auth" style={{ 
            color: T.text, textDecoration: 'none', fontSize: '0.65rem', fontWeight: 950, 
            fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1.5px' 
          }}>
            SIGN IN
          </a>
        </li>
        <li>
          <a href="/auth" style={{ 
            background: T.text, color: T.bg, padding: '10px 24px', borderRadius: 0, 
            fontWeight: 950, fontSize: '0.65rem', textDecoration: 'none', 
            fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1.5px',
            transition: 'all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)',
            border: `1px solid ${T.text}`,
            whiteSpace: 'nowrap',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = T.text; }}
          onMouseLeave={e => { e.currentTarget.style.background = T.text; e.currentTarget.style.color = T.bg; }}
          >
            GET STARTED FREE
          </a>
        </li>
      </ul>

      <button
        type="button"
        className="nav-mobile-toggle"
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((open) => !open)}
        style={{
          display: 'none',
          alignItems: 'center',
          justifyContent: 'center',
          width: 40,
          height: 40,
          border: `1px solid ${T.border}`,
          background: T.s2,
          color: T.text,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {menuOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      {menuOpen && (
        <div className="nav-mobile-menu" style={{
          position: 'fixed',
          top: scrolled ? 64 : 80,
          left: 0,
          right: 0,
          background: 'rgba(252, 250, 247, 0.98)',
          backdropFilter: 'blur(20px)',
          borderBottom: `1px solid ${T.border}`,
          padding: '24px clamp(16px, 4vw, 40px) 32px',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          zIndex: 899,
        }}>
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              style={{ color: T.text2, textDecoration: 'none', fontSize: '0.75rem', fontWeight: 950, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1.5px' }}
            >
              {link.label}
            </a>
          ))}
          <a href="/auth" onClick={() => setMenuOpen(false)} style={{ color: T.text, textDecoration: 'none', fontSize: '0.75rem', fontWeight: 950, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1.5px' }}>
            SIGN IN
          </a>
          <a
            href="/auth"
            onClick={() => setMenuOpen(false)}
            style={{
              background: T.text,
              color: T.bg,
              padding: '14px 24px',
              fontWeight: 950,
              fontSize: '0.75rem',
              textDecoration: 'none',
              fontFamily: T.fontMono,
              textTransform: 'uppercase',
              letterSpacing: '1.5px',
              textAlign: 'center',
            }}
          >
            GET STARTED FREE
          </a>
        </div>
      )}

      <style>{`
        @media (max-width: 1100px) {
          .nav-telemetry { display: none; }
        }
        @media (max-width: 900px) {
          .nav-desktop-links { display: none !important; }
          .nav-mobile-toggle { display: inline-flex !important; }
        }
      `}</style>
    </nav>
  );
}
