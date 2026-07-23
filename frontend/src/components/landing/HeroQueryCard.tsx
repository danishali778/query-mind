import { Check, User } from 'lucide-react';
import { L, gradient } from './tokens';

const ROWS = [
  { region: 'NA', revenue: '$1.2M' },
  { region: 'EMEA', revenue: '$860K' },
  { region: 'APAC', revenue: '$540K' },
];

const BARS = [
  { height: '88%', color: gradient(L.sky), delay: '1.0s' },
  { height: '62%', color: gradient(L.indigo), delay: '1.15s' },
  { height: '40%', color: gradient(L.emerald), delay: '1.3s' },
];

/** The floating "ask → SQL → result" card beneath the hero headline. */
export function HeroQueryCard() {
  return (
    <div
      className="landing-enter"
      style={{
        position: 'relative',
        zIndex: 2,
        maxWidth: 640,
        margin: '58px auto 0',
        animation: 'qm-fade 0.9s 0.55s both',
      }}
    >
      <div
        className="landing-hero-card"
        style={{
          background: L.surface,
          borderRadius: 22,
          padding: 22,
          border: `1px solid ${L.border}`,
          boxShadow: L.float,
          textAlign: 'left',
        }}
      >
        {/* the question */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 15 }}>
          <span
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              background: gradient(L.indigo),
              boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.5)',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
            }}
          >
            <User size={17} />
          </span>
          <span
            style={{
              background: L.surfaceSunken,
              borderRadius: '13px 13px 13px 4px',
              padding: '11px 15px',
              fontSize: 14.5,
              fontWeight: 600,
              color: L.text2,
            }}
          >
            Show me monthly revenue by region for 2026
          </span>
        </div>

        {/* the generated SQL */}
        <div
          style={{
            background: L.code.bg,
            borderRadius: 13,
            padding: '15px 17px',
            fontFamily: L.fontMono,
            fontSize: 13,
            lineHeight: 1.75,
            color: L.code.text,
            boxShadow: L.insetDark,
            marginBottom: 15,
          }}
        >
          <span style={{ color: L.code.keyword }}>SELECT</span> region,{' '}
          <span style={{ color: L.code.fn }}>SUM</span>(amount)
          <br />
          <span style={{ color: L.code.keyword }}>FROM</span> orders{' '}
          <span style={{ color: L.code.keyword }}>WHERE</span> year ={' '}
          <span style={{ color: L.code.literal }}>2026</span>
          <br />
          <span style={{ color: L.code.keyword }}>GROUP BY</span> region;
          <span
            style={{
              display: 'inline-block',
              width: 8,
              height: 15,
              background: L.code.ok,
              marginLeft: 3,
              verticalAlign: -2,
              animation: 'qm-blink 1.1s step-end infinite',
            }}
          />
        </div>

        {/* the result — calm surfaces, no material behind the data */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 13 }}>
          <div
            style={{
              background: L.surface,
              border: `1px solid ${L.border}`,
              borderRadius: 12,
              overflow: 'hidden',
              fontSize: 12.5,
            }}
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                background: L.surfaceSunken,
                padding: '8px 13px',
                fontWeight: 700,
                color: L.text3,
                fontFamily: L.fontMono,
                fontSize: 11,
              }}
            >
              <span>region</span>
              <span>revenue</span>
            </div>
            {ROWS.map((row) => (
              <div
                key={row.region}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  padding: '8px 13px',
                  borderTop: `1px solid ${L.border}`,
                  fontWeight: 600,
                }}
              >
                <span>{row.region}</span>
                <span style={{ fontFamily: L.fontMono, color: L.emerald.deep, fontVariantNumeric: 'tabular-nums' }}>
                  {row.revenue}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              background: L.surface,
              border: `1px solid ${L.border}`,
              borderRadius: 12,
              padding: 14,
              display: 'flex',
              alignItems: 'flex-end',
              gap: 9,
            }}
            aria-hidden="true"
          >
            {BARS.map((bar) => (
              <div
                key={bar.delay}
                style={{
                  flex: 1,
                  height: bar.height,
                  background: bar.color,
                  borderRadius: '6px 6px 0 0',
                  transformOrigin: 'bottom',
                  animation: `qm-grow 0.8s ${bar.delay} ${L.ease} both`,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* executed pill */}
      <div
        className="landing-hero-pill"
        style={{
          position: 'absolute',
          bottom: -18,
          right: -14,
          background: L.surface,
          borderRadius: 14,
          padding: '11px 15px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          border: `1px solid ${L.border}`,
          boxShadow: L.raisedLg,
        }}
      >
        <span
          style={{
            width: 28,
            height: 28,
            borderRadius: 9,
            background: gradient(L.emerald),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            flexShrink: 0,
          }}
        >
          <Check size={15} strokeWidth={3} />
        </span>
        <span>
          <span style={{ display: 'block', fontSize: 13, fontWeight: 800 }}>Query executed</span>
          <span style={{ display: 'block', fontSize: 11, color: L.text3, fontFamily: L.fontMono }}>3 rows · 0.42s</span>
        </span>
      </div>
    </div>
  );
}
