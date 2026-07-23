import { useEffect, useState } from 'react';
import { ArrowRight, Database, Menu, X } from 'lucide-react';
import { L, gradient, raisedAccent } from './tokens';

const NAV_LINKS = [
  { href: '#how-it-works', label: 'How it works' },
  { href: '#features', label: 'Features' },
  { href: '#security', label: 'Security' },
];

export function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [menuOpen]);

  return (
    <nav
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 24,
        padding: '16px clamp(20px, 4vw, 48px)',
        background: 'rgba(252, 250, 247, 0.72)',
        backdropFilter: 'blur(16px) saturate(180%)',
        borderBottom: `1px solid ${L.border}`,
      }}
    >
      <a
        href="/"
        style={{ display: 'flex', alignItems: 'center', gap: 11, textDecoration: 'none', color: L.text, flexShrink: 0 }}
      >
        <span
          style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: gradient(L.sky),
            boxShadow: raisedAccent(L.sky),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}
        >
          <Database size={19} strokeWidth={2.1} />
        </span>
        <span style={{ fontFamily: L.fontDisplay, fontWeight: 700, fontSize: 21, letterSpacing: '-0.03em' }}>
          QueryMind
        </span>
      </a>

      <div
        className="landing-nav-links"
        style={{ display: 'flex', alignItems: 'center', gap: 34, fontSize: 14.5, fontWeight: 600, color: L.text2 }}
      >
        {NAV_LINKS.map((link) => (
          <a key={link.href} href={link.href} className="landing-nav-link" style={{ color: 'inherit', textDecoration: 'none' }}>
            {link.label}
          </a>
        ))}
      </div>

      <div className="landing-nav-actions" style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <a
          href="/auth"
          className="landing-nav-login"
          style={{
            fontSize: 14.5,
            fontWeight: 700,
            color: L.text2,
            padding: '10px 16px',
            borderRadius: 10,
            textDecoration: 'none',
          }}
        >
          Log in
        </a>
        <a
          href="/auth"
          className="landing-btn-primary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 14.5,
            fontWeight: 700,
            color: '#fff',
            padding: '11px 20px',
            borderRadius: 11,
            textDecoration: 'none',
            whiteSpace: 'nowrap',
            background: gradient(L.sky),
            boxShadow: raisedAccent(L.sky, 0.45),
          }}
        >
          Get started
          <ArrowRight size={15} strokeWidth={2.4} />
        </a>
      </div>

      <button
        type="button"
        className="landing-nav-toggle"
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((open) => !open)}
        style={{
          display: 'none',
          alignItems: 'center',
          justifyContent: 'center',
          width: 40,
          height: 40,
          borderRadius: 11,
          border: `1px solid ${L.border}`,
          background: L.surface,
          boxShadow: L.raised,
          color: L.text,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {menuOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      {menuOpen && (
        <div
          style={{
            position: 'fixed',
            top: 69,
            left: 0,
            right: 0,
            background: 'rgba(252, 250, 247, 0.98)',
            backdropFilter: 'blur(16px)',
            borderBottom: `1px solid ${L.border}`,
            padding: '24px clamp(20px, 4vw, 48px) 32px',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
            zIndex: 49,
          }}
        >
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              style={{ color: L.text2, textDecoration: 'none', fontSize: 16, fontWeight: 600 }}
            >
              {link.label}
            </a>
          ))}
          <a
            href="/auth"
            onClick={() => setMenuOpen(false)}
            style={{ color: L.text, textDecoration: 'none', fontSize: 16, fontWeight: 700 }}
          >
            Log in
          </a>
          <a
            href="/auth"
            onClick={() => setMenuOpen(false)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              fontSize: 16,
              fontWeight: 700,
              color: '#fff',
              padding: '14px 24px',
              borderRadius: 12,
              textDecoration: 'none',
              background: gradient(L.sky),
              boxShadow: raisedAccent(L.sky, 0.45),
            }}
          >
            Get started
            <ArrowRight size={16} strokeWidth={2.4} />
          </a>
        </div>
      )}
    </nav>
  );
}
