import { ArrowRight, BarChart3, Cloud, Database, Play, Server, Sparkles, Table, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { L, gradient, raisedAccent } from './tokens';
import { HeroQueryCard } from './HeroQueryCard';

type Chip = {
  icon: LucideIcon;
  color: string;
  /** Position within the 1000×1000 orbit box. */
  pos: { top: number; left?: number; right?: number };
  size: number;
  /** Entrance delay + float duration, staggered so the chips never move in unison. */
  enter: string;
  float: string;
};

const CHIPS: Chip[] = [
  { icon: Database, color: L.sky.base, pos: { top: 150, left: 150 }, size: 60, enter: '0.30s', float: '7s 0.2s' },
  { icon: Server, color: L.indigo.base, pos: { top: 110, right: 190 }, size: 56, enter: '0.44s', float: '8s 1.1s' },
  { icon: Cloud, color: L.emerald.base, pos: { top: 330, left: 70 }, size: 58, enter: '0.58s', float: '9s 0.6s' },
  { icon: BarChart3, color: L.sky.base, pos: { top: 360, right: 100 }, size: 60, enter: '0.68s', float: '7.6s 1.4s' },
  { icon: Table, color: L.indigo.base, pos: { top: 560, left: 200 }, size: 54, enter: '0.8s', float: '8.4s 0.9s' },
  { icon: Zap, color: L.emerald.base, pos: { top: 600, right: 210 }, size: 52, enter: '0.9s', float: '7.2s 1.7s' },
];

export function Hero() {
  return (
    <section
      style={{
        position: 'relative',
        zIndex: 1,
        maxWidth: 1180,
        margin: '0 auto',
        padding: '72px clamp(20px, 4vw, 48px) 40px',
        textAlign: 'center',
      }}
    >
      {/* orbit rings + floating source chips (decorative) */}
      <div
        className="landing-orbit"
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: 40,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 1000,
          height: 1000,
          pointerEvents: 'none',
          zIndex: 0,
        }}
      >
        <div style={{ position: 'absolute', inset: 120, borderRadius: '50%', border: `1px solid ${L.border}` }} />
        <div style={{ position: 'absolute', inset: 210, borderRadius: '50%', border: `1px solid ${L.border}` }} />
        <div style={{ position: 'absolute', inset: 300, borderRadius: '50%', border: `1px dashed ${L.border}` }} />

        {CHIPS.map((chip, i) => {
          const Icon = chip.icon;
          return (
            <div
              key={i}
              className="landing-enter"
              style={{
                position: 'absolute',
                ...chip.pos,
                animation: `qm-fade-up 0.8s ${chip.enter} ${L.ease} both`,
              }}
            >
              <div
                style={{
                  width: chip.size,
                  height: chip.size,
                  borderRadius: 18,
                  background: L.surface,
                  border: `1px solid ${L.border}`,
                  boxShadow: L.raisedLg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: chip.color,
                  animation: `qm-float ${chip.float} ease-in-out infinite`,
                }}
              >
                <Icon size={Math.round(chip.size * 0.43)} strokeWidth={1.9} />
              </div>
            </div>
          );
        })}
      </div>

      {/* headline */}
      <div style={{ position: 'relative', zIndex: 2, maxWidth: 760, margin: '0 auto' }}>
        <div
          className="landing-enter"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 26,
            padding: '8px 16px',
            borderRadius: 999,
            background: L.surface,
            border: `1px solid ${L.border}`,
            boxShadow: L.raised,
            fontSize: 13.5,
            fontWeight: 700,
            color: L.text2,
            animation: `qm-fade-up 0.7s 0.05s ${L.ease} both`,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: L.emerald.base,
              boxShadow: `0 0 0 3px ${L.emerald.light}33`,
            }}
          />
          Postgres, MySQL, Snowflake, BigQuery &amp; more
        </div>

        <h1
          className="landing-hero-title landing-enter"
          style={{
            fontFamily: L.fontDisplay,
            fontWeight: 800,
            fontSize: 'clamp(2.5rem, 6.5vw, 66px)',
            lineHeight: 1.0,
            letterSpacing: '-0.045em',
            margin: '0 0 22px',
            animation: `qm-fade-up 0.75s 0.15s ${L.ease} both`,
          }}
        >
          Talk to your database.
          <br />
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, verticalAlign: 'baseline' }}>
            <Sparkles
              size={42}
              strokeWidth={1.7}
              color={L.sky.base}
              style={{ animation: 'qm-drift 4s ease-in-out infinite', flexShrink: 0 }}
              aria-hidden="true"
            />
            <span
              className="landing-hero-serif"
              style={{
                fontFamily: L.fontSerif,
                fontWeight: 400,
                fontStyle: 'italic',
                fontSize: 'clamp(2.9rem, 7.5vw, 76px)',
                letterSpacing: '-0.01em',
                color: L.sky.base,
              }}
            >
              Get answers,
            </span>
          </span>
          <br />
          <span style={{ color: L.text3 }}>not queries.</span>
        </h1>

        <p
          className="landing-enter"
          style={{
            fontSize: 19,
            lineHeight: 1.6,
            color: L.text2,
            margin: '0 auto 34px',
            maxWidth: 520,
            fontWeight: 500,
            animation: `qm-fade-up 0.75s 0.28s ${L.ease} both`,
          }}
        >
          Connect your database, ask in plain English, and QueryMind writes the SQL, runs it, and returns clean tables
          and charts — in seconds.
        </p>

        <div
          className="landing-enter"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            flexWrap: 'wrap',
            animation: `qm-fade-up 0.75s 0.4s ${L.ease} both`,
          }}
        >
          <a
            href="/auth"
            className="landing-btn-primary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 9,
              fontSize: 16,
              fontWeight: 700,
              color: '#fff',
              padding: '16px 30px',
              borderRadius: 14,
              textDecoration: 'none',
              background: gradient(L.sky),
              boxShadow: raisedAccent(L.sky, 0.45),
            }}
          >
            Start free
            <ArrowRight size={16} strokeWidth={2.4} />
          </a>
          <a
            href="#how-it-works"
            className="landing-btn-secondary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 16,
              fontWeight: 700,
              color: L.text,
              padding: '16px 26px',
              borderRadius: 14,
              textDecoration: 'none',
              background: L.surface,
              border: `1px solid ${L.border}`,
              boxShadow: L.raised,
            }}
          >
            <span
              style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                background: L.surfaceSunken,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: L.sky.base,
              }}
            >
              <Play size={12} fill="currentColor" strokeWidth={0} />
            </span>
            See how it works
          </a>
        </div>
      </div>

      <HeroQueryCard />
    </section>
  );
}
