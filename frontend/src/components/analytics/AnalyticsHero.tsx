import { useEffect, useState } from 'react';
import { Activity, Terminal, Fingerprint } from 'lucide-react';
import { T } from '../dashboard/tokens';

export function AnalyticsHero() {
  const [time, setTime] = useState(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }));

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      gap: 0, 
      marginBottom: 56, 
      borderTop: `4px solid ${T.text}`,
      paddingTop: 32
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 40, flexWrap: 'wrap' }}>
        
        {/* Left: Branding & Headline */}
        <div style={{ flex: '2 1 400px', display: 'flex', flexDirection: 'column', justifyContent: 'center', minHeight: 180 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            <div style={{ 
              background: T.text, color: '#fff', padding: '4px 10px', fontSize: '0.62rem', 
              fontFamily: T.fontMono, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em' 
            }}>
              VOL. 09 / INSIGHT_AI
            </div>
            <div style={{ height: 1, flex: 1, background: 'rgba(0,0,0,0.1)' }} />
          </div>
          
          <h1 style={{ 
            margin: 0, color: T.text, fontFamily: T.fontHead, fontSize: '3.8rem', 
            letterSpacing: -2, fontWeight: 900, lineHeight: 0.95
          }}>
            Usage, health, and output <br />
            <span style={{ fontStyle: 'italic', fontWeight: 400, color: T.text2 }}>across the entire engine</span>
          </h1>
        </div>

        {/* Right: Technical Ledger */}
        <div style={{ 
          flex: '0 1 320px', display: 'flex', flexDirection: 'column', gap: 24, 
          padding: '32px', background: 'rgba(0,0,0,0.02)', border: `1px solid rgba(0,0,0,0.05)`,
          minHeight: 220
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: T.text3 }}>
              <Fingerprint size={14} />
              <span style={{ fontSize: '0.62rem', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Session Hash</span>
            </div>
            <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text, fontWeight: 700 }}>QM_8F2A_9X</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(0,0,0,0.1)', paddingBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: T.text3 }}>
              <Terminal size={14} />
              <span style={{ fontSize: '0.62rem', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Kernel v.</span>
            </div>
            <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text, fontWeight: 700 }}>2.4.0_STABLE</span>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: T.text }}>
              <Activity size={14} className="pulse-slow" />
              <span style={{ fontSize: '0.62rem', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Telemetry Pulse</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <div style={{ fontSize: '1.8rem', fontFamily: T.fontMono, fontWeight: 900, color: T.text }}>{time}</div>
              <div style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, fontWeight: 700 }}>UTC+5</div>
            </div>
          </div>
        </div>
      </div>

      {/* Decorative Bottom Bar */}
      <div style={{ 
        marginTop: 40, height: 16, borderTop: `1px solid ${T.text}`, borderBottom: `1px solid ${T.text}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative'
      }}>
        <div style={{ 
          fontSize: '0.55rem', fontFamily: T.fontMono, color: T.text, textTransform: 'uppercase', 
          letterSpacing: '0.5em', background: '#fff', padding: '0 32px', fontWeight: 900 
        }}>
          INTERNAL_OPERATIONS_LEDGER
        </div>
      </div>

      <style>{`
        @keyframes pulse-slow {
          0% { opacity: 1; }
          50% { opacity: 0.4; }
          100% { opacity: 1; }
        }
        .pulse-slow {
          animation: pulse-slow 2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
