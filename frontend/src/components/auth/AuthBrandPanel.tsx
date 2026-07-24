import { Database, Lock, ShieldCheck } from 'lucide-react';
import { L, glow } from '../landing/tokens';

/**
 * Decorative left panel for the auth screen — the marketing surface.
 * Mirrors the landing page's language (gradient chrome, orbit rings, a glass
 * query card) using the app's sky accent. Purely presentational; all auth
 * logic lives in AuthPage.
 */
export function AuthBrandPanel() {
  return (
    <div
      className="auth-brand"
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: `linear-gradient(150deg, ${L.sky.light}, ${L.sky.deep})`,
        padding: '48px clamp(32px, 4vw, 56px)',
        color: '#fff',
      }}
    >
      {/* ambient orbs */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: -90,
          right: -60,
          width: 320,
          height: 320,
          borderRadius: '50%',
          background: 'rgba(255,255,255,0.09)',
          animation: 'qm-float-b 11s ease-in-out infinite',
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: -130,
          left: -40,
          width: 260,
          height: 260,
          borderRadius: '50%',
          background: 'rgba(255,255,255,0.06)',
          animation: 'qm-float-b 13s 1s ease-in-out infinite',
        }}
      />

      {/* concentric rings */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 640,
          height: 640,
          pointerEvents: 'none',
          opacity: 0.55,
        }}
      >
        <div style={{ position: 'absolute', inset: 60, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.22)' }} />
        <div style={{ position: 'absolute', inset: 140, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.18)' }} />
        <div style={{ position: 'absolute', inset: 220, borderRadius: '50%', border: '1px dashed rgba(255,255,255,0.16)' }} />
      </div>

      {/* brand */}
      <a
        href="/"
        style={{
          position: 'relative',
          zIndex: 2,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 11,
          textDecoration: 'none',
          color: '#fff',
          alignSelf: 'flex-start',
        }}
      >
        <span
          style={{
            width: 36,
            height: 36,
            borderRadius: 11,
            background: 'rgba(255,255,255,0.16)',
            border: '1px solid rgba(255,255,255,0.28)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Database size={21} strokeWidth={2.1} />
        </span>
        <span style={{ fontFamily: L.fontDisplay, fontWeight: 700, fontSize: 22, letterSpacing: '-0.03em' }}>
          QueryMind
        </span>
      </a>

      {/* centerpiece copy */}
      <div style={{ position: 'relative', zIndex: 2, margin: 'auto 0' }}>
        <h2
          style={{
            fontFamily: L.fontDisplay,
            fontWeight: 800,
            fontSize: 'clamp(2.2rem, 3.4vw, 46px)',
            lineHeight: 1.02,
            letterSpacing: '-0.04em',
            margin: '0 0 20px',
          }}
        >
          Talk to your database.
          <br />
          <span
            style={{
              fontFamily: L.fontSerif,
              fontWeight: 400,
              fontStyle: 'italic',
              fontSize: '1.18em',
              color: 'rgba(255,255,255,0.95)',
            }}
          >
            Get answers,
          </span>{' '}
          not queries.
        </h2>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.6,
            color: 'rgba(255,255,255,0.9)',
            maxWidth: 400,
            fontWeight: 500,
            margin: '0 0 36px',
          }}
        >
          Connect your database, ask in plain English, and get clean tables and charts in seconds.
        </p>

        {/* glass mini query card */}
        <div
          aria-hidden="true"
          style={{
            maxWidth: 400,
            background: 'rgba(255,255,255,0.1)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 18,
            padding: 16,
            backdropFilter: 'blur(8px)',
            boxShadow: `0 20px 50px ${glow(L.sky.deep, 0.35)}`,
            animation: 'qm-float-b 9s 0.6s ease-in-out infinite',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
            <span
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'rgba(255,255,255,0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                fontFamily: L.fontDisplay,
                fontWeight: 700,
                fontSize: 13,
              }}
            >
              Q
            </span>
            <span
              style={{
                background: 'rgba(255,255,255,0.16)',
                borderRadius: '11px 11px 11px 3px',
                padding: '9px 13px',
                fontSize: 13.5,
                fontWeight: 600,
              }}
            >
              Top 5 customers by revenue this quarter
            </span>
          </div>
          <div
            style={{
              background: 'rgba(23,26,36,0.65)',
              borderRadius: 11,
              padding: '12px 14px',
              fontFamily: L.fontMono,
              fontSize: 12,
              lineHeight: 1.7,
              color: L.code.text,
            }}
          >
            <span style={{ color: L.code.keyword }}>SELECT</span> name,{' '}
            <span style={{ color: L.code.fn }}>SUM</span>(rev)
            <br />
            <span style={{ color: L.code.keyword }}>FROM</span> orders{' '}
            <span style={{ color: L.code.keyword }}>GROUP BY</span> name
            <br />
            <span style={{ color: L.code.keyword }}>ORDER BY</span> 2{' '}
            <span style={{ color: L.code.keyword }}>DESC LIMIT</span>{' '}
            <span style={{ color: L.code.literal }}>5</span>;
            <span
              style={{
                display: 'inline-block',
                width: 7,
                height: 14,
                background: L.code.ok,
                marginLeft: 3,
                verticalAlign: -2,
                animation: 'qm-blink 1.1s step-end infinite',
              }}
            />
          </div>
        </div>
      </div>

      {/* factual trust line — no fabricated ratings or certifications */}
      <div
        style={{
          position: 'relative',
          zIndex: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          fontSize: 13.5,
          fontWeight: 600,
          color: 'rgba(255,255,255,0.85)',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
          <ShieldCheck size={16} strokeWidth={2} />
          Read-only by default
        </span>
        <span style={{ width: 1, height: 15, background: 'rgba(255,255,255,0.3)' }} />
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
          <Lock size={15} strokeWidth={2} />
          Encrypted in transit
        </span>
      </div>
    </div>
  );
}
