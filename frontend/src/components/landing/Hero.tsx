import { useEffect, useRef, useState } from 'react';
import { T } from '../dashboard/tokens';
import { Terminal, Activity } from 'lucide-react';

const QUERY_TEXT = "SELECT total_revenue FROM regional_sales WHERE quarter = 'Q3_2025';";

export function Hero() {
    const typewriterRef = useRef<HTMLSpanElement>(null);
    const [auditLogs, setAuditLogs] = useState<string[]>([]);

    useEffect(() => {
        const el = typewriterRef.current;
        if (!el) return;
        el.textContent = '';
        let i = 0;
        const timeout = setTimeout(() => {
            const iv = setInterval(() => {
                if (i < QUERY_TEXT.length) {
                    el.textContent += QUERY_TEXT[i++];
                } else {
                    clearInterval(iv);
                }
            }, 40);
            return () => clearInterval(iv);
        }, 1500);

        // Mock audit logs
        const logs = [
            'INITIALIZING_CORE_ENGINE...',
            'CONNECTING_TO_NODE_778...',
            'HANDSHAKE_PROTOCOL_SUCCESS',
            'SCHEMA_AUDIT_COMPLETE',
            'LATENCY: 12ms',
            'SECURITY_LEVEL: ALPHA',
        ];
        let logIdx = 0;
        const logIv = setInterval(() => {
          if (logIdx < logs.length) {
            setAuditLogs(prev => [...prev, logs[logIdx++]]);
          } else {
            clearInterval(logIv);
          }
        }, 800);

        return () => {
          clearTimeout(timeout);
          clearInterval(logIv);
        }
    }, []);

    return (
        <section style={{ 
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', 
            padding: '160px 60px 100px', position: 'relative', overflow: 'hidden',
            background: T.bg
        }}>
            {/* Background Grid */}
            <div style={{ 
                position: 'absolute', inset: 0, 
                backgroundImage: `linear-gradient(${T.border} 1px, transparent 1px), linear-gradient(90deg, ${T.border} 1px, transparent 1px)`, 
                backgroundSize: '100px 100px', opacity: 0.2, pointerEvents: 'none' 
            }} />
            
            {/* Tele-Audit Sidebar (WOW Element) */}
            <div style={{ 
              position: 'absolute', top: '20%', left: 40, width: 200, 
              fontFamily: T.fontMono, fontSize: '0.55rem', color: T.text3,
              display: 'flex', flexDirection: 'column', gap: 6, zIndex: 1,
              opacity: 0.6
            }} className="hero-audit">
              <div style={{ fontWeight: 950, color: T.accent, marginBottom: 10, letterSpacing: 2 }}>// LIVE_AUDIT_LOG</div>
              {auditLogs.map((log, i) => (
                <div key={i} style={{ animation: 'fadeIn 0.5s ease forwards' }}>{'>'} {log}</div>
              ))}
            </div>

            {/* Content Container */}
            <div style={{ position: 'relative', zIndex: 2, textAlign: 'center', maxWidth: 1100 }}>
                {/* Status Badge */}
                <div style={{ 
                    display: 'inline-flex', alignItems: 'center', gap: 12, 
                    background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0, 
                    padding: '10px 24px', fontFamily: T.fontMono, fontSize: '0.65rem', 
                    color: T.text, marginBottom: 48, fontWeight: 950, letterSpacing: '4px',
                    textTransform: 'uppercase', boxShadow: `8px 8px 0px ${T.s3}`
                }}>
                    <Activity size={12} color={T.accent} />
                    SYSTEM_PROTOCOL // RELEASE_2.4.0
                </div>

                {/* Main Heading (Editorial Style) */}
                <h1 style={{ 
                    fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(3.5rem, 9vw, 7.5rem)', 
                    lineHeight: 1.05, letterSpacing: '-4px', marginBottom: 48, color: T.text, 
                    textTransform: 'uppercase', fontStyle: 'italic'
                }}>
                    STOP_WRITING_SQL.<br />
                    <span style={{ 
                      color: 'transparent', WebkitTextStroke: `2px ${T.text}`, 
                      opacity: 0.8
                    }}>START_GETTING_</span><br />
                    <span style={{ color: T.accent }}>ANSWERS.</span>
                </h1>

                {/* Sub-headline */}
                <p style={{ 
                    fontSize: '0.85rem', color: T.text2, lineHeight: 2, maxWidth: 680, 
                    margin: '0 auto 64px', fontWeight: 800, fontFamily: T.fontMono, 
                    textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.9
                }}>
                    TRANSFORM NATURAL LANGUAGE INTO PRODUCTION-READY ANALYTICS NODES INSTANTLY. THE NEXT EVOLUTION OF DATA INTELLIGENCE.
                </p>

                {/* Standard Labels CTAs */}
                <div style={{ display: 'flex', gap: 32, justifyContent: 'center', flexWrap: 'wrap' }}>
                    <a href="/auth" style={{ 
                        background: T.text, color: T.bg, padding: '22px 56px', borderRadius: 0, 
                        fontWeight: 950, fontSize: '0.85rem', textDecoration: 'none', 
                        fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '3px',
                        transition: 'all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)',
                        boxShadow: `12px 12px 0px ${T.accent}`
                    }}
                    onMouseEnter={e => { e.currentTarget.style.transform = 'translate(-4px, -4px)'; e.currentTarget.style.boxShadow = `16px 16px 0px ${T.accent}`; }}
                    onMouseLeave={e => { e.currentTarget.style.transform = 'translate(0, 0)'; e.currentTarget.style.boxShadow = `12px 12px 0px ${T.accent}`; }}
                    >
                        GET STARTED FREE
                    </a>
                    <a href="#how" style={{ 
                        background: 'transparent', border: `1px solid ${T.border}`, color: T.text, 
                        padding: '22px 56px', borderRadius: 0, fontWeight: 950, fontSize: '0.85rem', 
                        textDecoration: 'none', fontFamily: T.fontMono, textTransform: 'uppercase', 
                        letterSpacing: '3px', transition: 'all 0.3s' 
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = T.s2; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                        VIEW PROTOCOL
                    </a>
                </div>

                {/* High-Fidelity Preview Node */}
                <div style={{ 
                    marginTop: 120, background: T.s1, border: `2px solid ${T.text}`, 
                    borderRadius: 0, overflow: 'hidden', maxWidth: 900, 
                    marginLeft: 'auto', marginRight: 'auto',
                    boxShadow: `40px 40px 0px ${T.s2}`,
                    textAlign: 'left'
                }}>
                    {/* Header */}
                    <div style={{ 
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '20px 32px', background: T.text, color: T.bg
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                          <Terminal size={16} color={T.accent} />
                          <span style={{ fontFamily: T.fontMono, fontSize: '0.7rem', fontWeight: 950, letterSpacing: '2px' }}>
                            QUERY_TERMINAL // NODE_ALPHA
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <div style={{ width: 8, height: 8, background: T.accent }} />
                          <div style={{ width: 8, height: 8, background: T.s3 }} />
                        </div>
                    </div>
                    
                    {/* Terminal Body */}
                    <div style={{ padding: '40px', fontFamily: T.fontMono }}>
                        <div style={{ display: 'flex', gap: 24, marginBottom: 40 }}>
                          <div style={{ 
                            padding: '6px 14px', background: T.accent, color: '#000', 
                            fontSize: '0.65rem', fontWeight: 950, letterSpacing: '2px' 
                          }}>INPUT</div>
                          <span ref={typewriterRef} style={{ fontSize: '1rem', fontWeight: 800, color: T.text }} />
                        </div>
                        
                        <div style={{ 
                          padding: '32px', background: T.s2, border: `1px solid ${T.border}`,
                          fontSize: '0.85rem', color: T.text2, lineHeight: 2, position: 'relative'
                        }}>
                          <div style={{ position: 'absolute', top: 12, right: 24, fontSize: '0.55rem', color: T.accent, fontWeight: 950 }}>EXECUTING_SQL...</div>
                          <code style={{ color: T.text }}>
                            <span style={{ color: T.accent }}>SELECT</span> region, <span style={{ color: T.accent }}>SUM</span>(revenue)<br />
                            <span style={{ color: T.accent }}>FROM</span> sales_nodes<br />
                            <span style={{ color: T.accent }}>WHERE</span> quarter = <span style={{ color: T.green }}>'Q3_2025'</span><br />
                            <span style={{ color: T.accent }}>GROUP BY</span> 1;
                          </code>
                        </div>
                    </div>
                </div>
            </div>

            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateX(-10px); }
                    to { opacity: 1; transform: translateX(0); }
                }
                @media (max-width: 1200px) {
                  .hero-audit { display: none; }
                }
            `}</style>
        </section>
    );
}
