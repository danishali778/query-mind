import { Check, MessageSquare, Sparkles } from 'lucide-react';
import { L } from './tokens';

const POINTS = [
  'Schema-aware — knows your tables and joins',
  'Every query shown before execution',
  'Read-only mode keeps production safe',
];

export function NlToSqlFeature() {
  return (
    <section
      id="features"
      className="landing-split"
      style={{
        position: 'relative',
        zIndex: 1,
        maxWidth: 1180,
        margin: '0 auto',
        padding: '100px clamp(20px, 4vw, 48px)',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 64,
        alignItems: 'center',
      }}
    >
      <div
        className="reveal"
        data-reveal
        style={{
          background: L.surface,
          borderRadius: 22,
          padding: 24,
          border: `1px solid ${L.border}`,
          boxShadow: L.float,
        }}
      >
        <div
          style={{
            fontFamily: L.fontMono,
            fontSize: 12,
            fontWeight: 600,
            color: L.text3,
            marginBottom: 11,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
          }}
        >
          <MessageSquare size={14} strokeWidth={2} />
          you ask
        </div>
        <div
          style={{
            background: L.surfaceSunken,
            borderRadius: 13,
            padding: '14px 16px',
            fontSize: 15,
            fontWeight: 600,
            color: L.text,
            boxShadow: L.inset,
            marginBottom: 22,
          }}
        >
          "Which customers churned in Q2 but had over $10k lifetime spend?"
        </div>

        <div
          style={{
            fontFamily: L.fontMono,
            fontSize: 12,
            fontWeight: 600,
            color: L.sky.base,
            marginBottom: 11,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
          }}
        >
          <Sparkles size={14} strokeWidth={1.8} />
          querymind writes
        </div>
        <div
          style={{
            background: L.code.bg,
            borderRadius: 13,
            padding: '16px 18px',
            fontFamily: L.fontMono,
            fontSize: 13,
            lineHeight: 1.8,
            color: L.code.text,
            boxShadow: L.insetDark,
          }}
        >
          <span style={{ color: L.code.keyword }}>SELECT</span> c.name, c.ltv
          <br />
          <span style={{ color: L.code.keyword }}>FROM</span> customers c
          <br />
          <span style={{ color: L.code.keyword }}>JOIN</span> churn_events e{' '}
          <span style={{ color: L.code.keyword }}>ON</span> e.cid = c.id
          <br />
          <span style={{ color: L.code.keyword }}>WHERE</span> e.quarter ={' '}
          <span style={{ color: L.code.literal }}>'2026-Q2'</span>
          <br />
          &nbsp;&nbsp;<span style={{ color: L.code.keyword }}>AND</span> c.ltv &gt;{' '}
          <span style={{ color: L.code.literal }}>10000</span>;
        </div>
      </div>

      <div className="reveal" data-reveal data-reveal-delay={120}>
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
          Natural language → SQL
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
          Everyone on your team is now a{' '}
          <span
            style={{
              fontFamily: L.fontSerif,
              fontStyle: 'italic',
              fontWeight: 400,
              color: L.sky.base,
              fontSize: '1.15em',
            }}
          >
            SQL expert
          </span>
        </h2>
        <p style={{ fontSize: 17, lineHeight: 1.62, color: L.text2, margin: '0 0 26px', fontWeight: 500 }}>
          QueryMind reads your schema, understands joins and relationships, and translates any question into correct
          SQL. Review it before it runs, or trust it and go straight to the answer.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {POINTS.map((point) => (
            <div key={point} style={{ display: 'flex', alignItems: 'center', gap: 13, fontSize: 15.5, fontWeight: 600 }}>
              <span
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: 9,
                  background: `${L.emerald.light}26`,
                  color: L.emerald.deep,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Check size={15} strokeWidth={3} />
              </span>
              {point}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
