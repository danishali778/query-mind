import { ClipboardList, Lock, ShieldCheck } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { L, gradient, raisedAccent } from './tokens';
import type { AccentRamp } from './tokens';

type Assurance = {
  icon: LucideIcon;
  ramp: AccentRamp;
  title: string;
  body: string;
};

const ASSURANCES: Assurance[] = [
  {
    icon: ShieldCheck,
    ramp: L.emerald,
    title: 'Read-only by default',
    body: 'Generated queries can never write, update, or delete. Your production data stays untouched.',
  },
  {
    icon: Lock,
    ramp: L.indigo,
    title: 'Encrypted connections',
    body: 'Credentials are encrypted at rest and every database connection runs over TLS.',
  },
  {
    icon: ClipboardList,
    ramp: L.sky,
    title: 'Full query audit log',
    body: 'Every question, generated query, and result — logged and reviewable by admins.',
  },
];

export function SecurityBand() {
  return (
    <section
      id="security"
      style={{
        position: 'relative',
        zIndex: 1,
        background: L.surface,
        borderTop: `1px solid ${L.border}`,
        borderBottom: `1px solid ${L.border}`,
        padding: '78px clamp(20px, 4vw, 48px)',
      }}
    >
      <div
        className="landing-security-grid"
        style={{ maxWidth: 1180, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }}
      >
        {ASSURANCES.map((a, i) => {
          const Icon = a.icon;
          return (
            <div key={a.title} className="reveal" data-reveal data-reveal-delay={i * 120} style={{ display: 'flex', gap: 16 }}>
              <div
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 13,
                  background: gradient(a.ramp),
                  boxShadow: raisedAccent(a.ramp, 0.35),
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                }}
              >
                <Icon size={22} strokeWidth={2} />
              </div>
              <div>
                <h3
                  style={{
                    fontFamily: L.fontDisplay,
                    fontSize: 18,
                    fontWeight: 700,
                    letterSpacing: '-0.02em',
                    margin: '0 0 6px',
                  }}
                >
                  {a.title}
                </h3>
                <p style={{ fontSize: 14.5, lineHeight: 1.55, color: L.text2, margin: 0, fontWeight: 500 }}>{a.body}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
