import { ArrowRight } from 'lucide-react';
import { L, glow } from './tokens';

export function CtaBand() {
  return (
    <section
      style={{
        position: 'relative',
        zIndex: 1,
        maxWidth: 1180,
        margin: '0 auto',
        padding: '100px clamp(20px, 4vw, 48px)',
      }}
    >
      <div
        className="reveal landing-cta"
        data-reveal
        style={{
          background: `linear-gradient(135deg, ${L.sky.light}, ${L.sky.deep})`,
          borderRadius: 28,
          padding: 'clamp(40px, 6vw, 68px)',
          display: 'grid',
          gridTemplateColumns: '1fr auto',
          gap: 44,
          alignItems: 'center',
          boxShadow: `inset 0 1px 2px rgba(255,255,255,0.35), 0 30px 70px ${glow(L.sky.base, 0.42)}`,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: -80,
            right: -60,
            width: 280,
            height: 280,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.09)',
            animation: 'qm-float-b 10s ease-in-out infinite',
          }}
        />
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            bottom: -120,
            left: '20%',
            width: 220,
            height: 220,
            borderRadius: '50%',
            background: 'rgba(255,255,255,0.06)',
            animation: 'qm-float-b 12s 1s ease-in-out infinite',
          }}
        />

        <div style={{ position: 'relative' }}>
          <h2
            style={{
              fontFamily: L.fontDisplay,
              fontSize: 'clamp(1.9rem, 4.2vw, 42px)',
              fontWeight: 700,
              letterSpacing: '-0.035em',
              color: '#fff',
              margin: '0 0 16px',
              lineHeight: 1.05,
            }}
          >
            Ready to{' '}
            <span style={{ fontFamily: L.fontSerif, fontStyle: 'italic', fontWeight: 400, fontSize: '1.14em' }}>
              talk to your data?
            </span>
          </h2>
          <p
            style={{
              fontSize: 17,
              lineHeight: 1.6,
              color: 'rgba(255,255,255,0.92)',
              margin: 0,
              maxWidth: 500,
              fontWeight: 500,
            }}
          >
            Connect a database and ask your first question in under five minutes. Free to start, no credit card
            required.
          </p>
        </div>

        <a
          href="/auth"
          className="landing-btn-secondary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 9,
            fontSize: 17,
            fontWeight: 800,
            color: L.sky.deep,
            padding: '19px 36px',
            borderRadius: 16,
            textDecoration: 'none',
            background: '#fff',
            boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.9), 0 10px 26px rgba(28,34,58,0.22)',
            whiteSpace: 'nowrap',
            position: 'relative',
          }}
        >
          Start free
          <ArrowRight size={16} strokeWidth={2.6} />
        </a>
      </div>
    </section>
  );
}
