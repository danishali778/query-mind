import { ArrowRight, BarChart3, Table } from 'lucide-react';
import { L, gradient } from './tokens';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];

const BARS = [
  { height: '45%', ramp: L.indigo },
  { height: '62%', ramp: L.indigo },
  { height: '52%', ramp: L.indigo },
  { height: '80%', ramp: L.sky },
  { height: '70%', ramp: L.indigo },
  { height: '94%', ramp: L.emerald },
];

export function VisualizationFeature() {
  return (
    <section
      className="landing-split landing-split-reverse"
      style={{
        position: 'relative',
        zIndex: 1,
        maxWidth: 1180,
        margin: '0 auto',
        padding: '0 clamp(20px, 4vw, 48px) 100px',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 64,
        alignItems: 'center',
      }}
    >
      <div className="reveal" data-reveal>
        <p
          style={{
            fontSize: 12.5,
            fontWeight: 800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: L.indigo.base,
            margin: '0 0 14px',
          }}
        >
          Instant visualization
        </p>
        <h2
          style={{
            fontFamily: L.fontDisplay,
            fontSize: 'clamp(1.9rem, 4vw, 40px)',
            fontWeight: 700,
            letterSpacing: '-0.035em',
            margin: '0 0 20px',
            lineHeight: 1.08,
          }}
        >
          Answers arrive as tables and charts,{' '}
          <span
            style={{
              fontFamily: L.fontSerif,
              fontStyle: 'italic',
              fontWeight: 400,
              color: L.indigo.base,
              fontSize: '1.15em',
            }}
          >
            not raw rows
          </span>
        </h2>
        <p style={{ fontSize: 17, lineHeight: 1.62, color: L.text2, margin: '0 0 26px', fontWeight: 500 }}>
          QueryMind picks the right visualization for your result — bar, line, or pie — and pairs it with a sortable
          table. One click to switch views, export, or pin to a dashboard.
        </p>
        <a
          href="/auth"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 15.5,
            fontWeight: 700,
            color: L.indigo.deep,
            textDecoration: 'none',
          }}
        >
          Explore the dashboard
          <ArrowRight size={16} strokeWidth={2.4} />
        </a>
      </div>

      <div
        className="reveal"
        data-reveal
        data-reveal-delay={120}
        style={{
          background: L.surface,
          borderRadius: 22,
          padding: 24,
          border: `1px solid ${L.border}`,
          boxShadow: L.float,
        }}
      >
        {/* view toggle — inset track, raised active segment */}
        <div
          style={{
            display: 'inline-flex',
            gap: 4,
            marginBottom: 20,
            padding: 4,
            borderRadius: 12,
            background: L.surfaceSunken,
            boxShadow: L.inset,
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 15px',
              borderRadius: 9,
              background: gradient(L.indigo),
              color: '#fff',
              fontSize: 13,
              fontWeight: 700,
              boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.4)',
            }}
          >
            <BarChart3 size={13} strokeWidth={2.2} />
            Chart
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 15px',
              borderRadius: 9,
              color: L.text2,
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            <Table size={13} strokeWidth={2} />
            Table
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '8px 15px',
              borderRadius: 9,
              color: L.text2,
              fontSize: 13,
              fontWeight: 700,
              fontFamily: L.fontMono,
            }}
          >
            SQL
          </span>
        </div>

        {/* chart canvas stays calm — no material behind the data */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, height: 196, padding: '0 6px' }} aria-hidden="true">
          {BARS.map((bar, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: bar.height,
                background: gradient(bar.ramp),
                borderRadius: '8px 8px 0 0',
                transformOrigin: 'bottom',
                animation: `qm-grow 0.9s ${0.1 + i * 0.1}s ${L.ease} both`,
              }}
            />
          ))}
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '12px 6px 0',
            fontFamily: L.fontMono,
            fontSize: 11,
            color: L.text3,
          }}
        >
          {MONTHS.map((m) => (
            <span key={m}>{m}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
