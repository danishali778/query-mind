import { Database } from 'lucide-react';
import { L, gradient } from './tokens';

const COLUMNS = [
  { heading: 'Product', links: ['How it works', 'Features', 'Security', 'Pricing'] },
  { heading: 'Resources', links: ['Docs', 'API reference', 'Blog', 'Support'] },
  { heading: 'Company', links: ['About', 'Careers', 'Privacy', 'Terms'] },
];

export function Footer() {
  return (
    <footer
      style={{
        position: 'relative',
        zIndex: 1,
        background: L.surface,
        borderTop: `1px solid ${L.border}`,
        padding: '60px clamp(20px, 4vw, 48px) 40px',
      }}
    >
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div
          className="landing-footer-grid"
          style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 40, marginBottom: 48 }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 9,
                  background: gradient(L.sky),
                  boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                }}
              >
                <Database size={17} strokeWidth={2.1} />
              </span>
              <span style={{ fontFamily: L.fontDisplay, fontWeight: 700, fontSize: 19, letterSpacing: '-0.03em' }}>
                QueryMind
              </span>
            </div>
            <p style={{ fontSize: 14.5, lineHeight: 1.6, color: L.text2, margin: 0, maxWidth: 270, fontWeight: 500 }}>
              Plain-English analytics for every team. Ask, and your database answers.
            </p>
          </div>

          {COLUMNS.map((col) => (
            <div
              key={col.heading}
              style={{ display: 'flex', flexDirection: 'column', gap: 11, fontSize: 14, color: L.text2, fontWeight: 500 }}
            >
              <span
                style={{
                  fontWeight: 800,
                  color: L.text,
                  fontSize: 12,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: 4,
                }}
              >
                {col.heading}
              </span>
              {col.links.map((link) => (
                <span key={link}>{link}</span>
              ))}
            </div>
          ))}
        </div>

        <div
          style={{
            borderTop: `1px solid ${L.border}`,
            paddingTop: 24,
            display: 'flex',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
            fontSize: 13,
            color: L.text3,
            fontWeight: 500,
          }}
        >
          <span>© {new Date().getFullYear()} QueryMind</span>
          <span>Privacy · Terms</span>
        </div>
      </div>
    </footer>
  );
}
