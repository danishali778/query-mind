import { useScrollReveal } from '../hooks/useScrollReveal';
import { Navbar } from '../components/landing/Navbar';
import { Hero } from '../components/landing/Hero';
import { DatabaseStrip } from '../components/landing/DatabaseStrip';
import { HowItWorks } from '../components/landing/HowItWorks';
import { NlToSqlFeature } from '../components/landing/NlToSqlFeature';
import { VisualizationFeature } from '../components/landing/VisualizationFeature';
import { SecurityBand } from '../components/landing/SecurityBand';
import { CtaBand } from '../components/landing/CtaBand';
import { Footer } from '../components/landing/Footer';
import { L, glow } from '../components/landing/tokens';

export function LandingPage() {
  useScrollReveal();

  return (
    <div
      className="landing-root"
      style={{
        background: L.bg,
        minHeight: '100vh',
        color: L.text,
        fontFamily: L.fontBody,
        overflowX: 'hidden',
        position: 'relative',
      }}
    >
      {/* ambient glow behind the hero */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: -160,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 1100,
          height: 620,
          background: `radial-gradient(ellipse at center, ${glow(L.sky.base, 0.14)}, transparent 62%)`,
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      <Navbar />

      <main>
        <Hero />
        <DatabaseStrip />
        <HowItWorks />
        <NlToSqlFeature />
        <VisualizationFeature />
        <SecurityBand />
        <CtaBand />
      </main>

      <Footer />
    </div>
  );
}
