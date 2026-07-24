import { BarChart3, Link2, MessageSquare } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { L, gradient, raisedAccent } from './tokens';
import type { AccentRamp } from './tokens';

type Step = {
  icon: LucideIcon;
  ramp: AccentRamp;
  step: string;
  title: string;
  body: string;
};

const STEPS: Step[] = [
  {
    icon: Link2,
    ramp: L.indigo,
    step: 'STEP 01',
    title: 'Connect your database',
    body: 'Paste a connection string or use a one-click connector. Read-only by default — your data never leaves your warehouse.',
  },
  {
    icon: MessageSquare,
    ramp: L.sky,
    step: 'STEP 02',
    title: 'Ask in plain English',
    body: "Type your question like you'd ask a teammate. QueryMind understands your schema and writes correct, optimized SQL.",
  },
  {
    icon: BarChart3,
    ramp: L.emerald,
    step: 'STEP 03',
    title: 'Get tables & charts',
    body: 'Results arrive as clean tables and auto-generated charts. Save them, share them, or keep drilling with follow-ups.',
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      style={{
        position: 'relative',
        zIndex: 1,
        background: L.surface,
        borderTop: `1px solid ${L.border}`,
        borderBottom: `1px solid ${L.border}`,
        padding: '92px clamp(20px, 4vw, 48px)',
      }}
    >
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div className="reveal" data-reveal style={{ textAlign: 'center', marginBottom: 60 }}>
          <p
            style={{
              fontSize: 12.5,
              fontWeight: 800,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: L.sky.base,
              margin: '0 0 14px',
            }}
          >
            How it works
          </p>
          <h2
            style={{
              fontFamily: L.fontDisplay,
              fontSize: 'clamp(2rem, 4.5vw, 44px)',
              fontWeight: 700,
              letterSpacing: '-0.035em',
              margin: 0,
              lineHeight: 1.05,
            }}
          >
            From question to insight{' '}
            <span
              style={{
                fontFamily: L.fontSerif,
                fontStyle: 'italic',
                fontWeight: 400,
                color: L.sky.base,
                fontSize: '1.14em',
              }}
            >
              in three steps
            </span>
          </h2>
        </div>

        <div
          className="landing-steps-grid"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 26, position: 'relative' }}
        >
          {/* dashed connector behind the cards */}
          <div
            className="landing-steps-connector"
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 42,
              left: '16%',
              right: '16%',
              height: 2,
              background: `repeating-linear-gradient(90deg, ${L.border} 0 8px, transparent 8px 16px)`,
              zIndex: 0,
            }}
          />

          {STEPS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div
                key={s.step}
                className="reveal landing-step-card"
                data-reveal
                data-reveal-delay={i * 130}
                style={{
                  position: 'relative',
                  zIndex: 1,
                  background: L.bg,
                  borderRadius: 20,
                  padding: 32,
                  border: `1px solid ${L.border}`,
                  boxShadow: L.raisedLg,
                }}
              >
                <div
                  style={{
                    width: 54,
                    height: 54,
                    borderRadius: 16,
                    background: gradient(s.ramp),
                    boxShadow: raisedAccent(s.ramp),
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    marginBottom: 22,
                  }}
                >
                  <Icon size={26} strokeWidth={2} />
                </div>
                <div
                  style={{ fontFamily: L.fontMono, fontSize: 12, fontWeight: 600, color: s.ramp.deep, marginBottom: 8 }}
                >
                  {s.step}
                </div>
                <h3
                  style={{
                    fontFamily: L.fontDisplay,
                    fontSize: 22,
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    margin: '0 0 10px',
                  }}
                >
                  {s.title}
                </h3>
                <p style={{ fontSize: 15, lineHeight: 1.62, color: L.text2, margin: 0, fontWeight: 500 }}>{s.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
