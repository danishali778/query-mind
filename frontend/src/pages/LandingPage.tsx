import { Navbar } from '../components/landing/Navbar';
import { Hero } from '../components/landing/Hero';
import { Stats } from '../components/landing/Stats';
import { Integrations } from '../components/landing/Integrations';
import { LandingOverlay } from '../components/landing/LandingOverlay';
import { T } from '../components/dashboard/tokens';
import { Shield, Zap, Lock, Cpu, Globe } from 'lucide-react';

const features = [
  { icon: <Zap size={24} />, title: 'RAPID_INGESTION', desc: 'Connect any database node in under 30 seconds. No drivers, no boilerplate.' },
  { icon: <Shield size={24} />, title: 'ALPHA_SECURITY', desc: 'Enterprise-grade encryption with zero-trust architecture at every endpoint.' },
  { icon: <Cpu size={24} />, title: 'NEURAL_TRANSLATION', desc: 'Proprietary LLM translation layer optimized for complex SQL query nodes.' },
  { icon: <Globe size={24} />, title: 'GLOBAL_STABILITY', desc: 'Edge-distributed processing ensures 99.99% uptime for your data pipelines.' },
];

export function LandingPage() {
  return (
    <div style={{ background: T.bg, minHeight: '100vh', color: T.text, scrollBehavior: 'smooth' }}>
      <LandingOverlay />
      <Navbar />
      
      <main>
        <Hero />
        <Stats />
        
        {/* Features Section (Feature Nodes) */}
        <section id="features" style={{ padding: '160px 60px', background: T.bg, borderBottom: `1px solid ${T.border}` }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 100, alignItems: 'center' }}>
              <div>
                <div style={{ fontFamily: T.fontMono, fontSize: '0.65rem', color: T.accent, letterSpacing: 4, fontWeight: 950, marginBottom: 24 }}>[ 01_CAPABILITIES ]</div>
                <h2 style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(3rem, 6vw, 5rem)', letterSpacing: -3, lineHeight: 0.95, textTransform: 'uppercase', fontStyle: 'italic', marginBottom: 40 }}>
                  THE_FUTURE_OF_DATA_EXFILTRATION.
                </h2>
                <p style={{ fontFamily: T.fontMono, fontSize: '0.85rem', color: T.text2, lineHeight: 2, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 48 }}>
                  WE DECONSTRUCT COMPLEX ANALYTICS INTO HUMAN-READABLE SIGNALS. QUERYMIND IS THE COMMAND CENTER FOR YOUR ENTIRE DATA ESTATE.
                </p>
                <div style={{ display: 'flex', gap: 24 }}>
                  <div style={{ width: 40, height: 40, background: T.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Lock size={18} color="#000" />
                  </div>
                  <div>
                    <div style={{ fontFamily: T.fontMono, fontSize: '0.7rem', fontWeight: 950, letterSpacing: 1 }}>ENCRYPTED_ENDPOINTS</div>
                    <div style={{ fontSize: '0.6rem', color: T.text3, marginTop: 4 }}>AES-256_STRICT_PROTOCOL</div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
                {features.map((f, i) => (
                  <div key={i} style={{ padding: '40px', background: T.s1, border: `1px solid ${T.border}`, transition: 'transform 0.3s' }}>
                    <div style={{ color: T.accent, marginBottom: 24 }}>{f.icon}</div>
                    <div style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: '1rem', marginBottom: 12, letterSpacing: 1 }}>{f.title}</div>
                    <div style={{ fontSize: '0.7rem', color: T.text2, lineHeight: 1.8, fontFamily: T.fontMono }}>{f.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <Integrations />

        {/* Final CTA Section */}
        <section style={{ padding: '160px 60px', textAlign: 'center', background: T.text, color: T.bg, position: 'relative', overflow: 'hidden' }}>
          <div style={{ 
            position: 'absolute', inset: 0, 
            backgroundImage: `radial-gradient(${T.accent} 2px, transparent 2px)`, 
            backgroundSize: '30px 30px', opacity: 0.1 
          }} />
          <div style={{ position: 'relative', zIndex: 1 }}>
            <h2 style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(3rem, 8vw, 6.5rem)', letterSpacing: -4, lineHeight: 0.9, textTransform: 'uppercase', fontStyle: 'italic', marginBottom: 48 }}>
              READY_TO_UPGRADE?<br />
              <span style={{ color: T.accent }}>INITIALIZE_NOW.</span>
            </h2>
            <a href="/auth" style={{ 
              background: T.accent, color: '#000', padding: '24px 72px', borderRadius: 0, 
              fontWeight: 950, fontSize: '1rem', textDecoration: 'none', 
              fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '4px',
              display: 'inline-block', boxShadow: `12px 12px 0px rgba(0,0,0,0.3)`
            }}>
              GET STARTED FREE
            </a>
          </div>
        </section>
      </main>

      <footer style={{ padding: '80px 60px', background: T.bg, borderTop: `1px solid ${T.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: '1.2rem', letterSpacing: '-1px', color: T.text, textTransform: 'uppercase', marginBottom: 24 }}>
            QUERY<span style={{ color: T.accent }}>MIND</span>
          </div>
          <div style={{ fontFamily: T.fontMono, fontSize: '0.6rem', color: T.text3, letterSpacing: 2 }}>
            © 2026 // INSIGHT_AI_CORP<br />
            ALL_RIGHTS_RESERVED // SYSTEM_V2.4
          </div>
        </div>
        <div style={{ display: 'flex', gap: 48, fontFamily: T.fontMono, fontSize: '0.65rem', fontWeight: 950, letterSpacing: 2 }}>
          <a href="#" style={{ color: T.text, textDecoration: 'none' }}>PRIVACY_PROTOCOL</a>
          <a href="#" style={{ color: T.text, textDecoration: 'none' }}>SYSTEM_TERMS</a>
          <a href="#" style={{ color: T.text, textDecoration: 'none' }}>STATUS_NODE</a>
        </div>
      </footer>
    </div>
  );
}
