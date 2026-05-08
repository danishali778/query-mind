import { T } from '../dashboard/tokens';
import { Database, Shield } from 'lucide-react';

const tools = [
    { name: 'POSTGRESQL', type: 'DATABASE', id: 'PSQL_01' },
    { name: 'SNOWFLAKE', type: 'WAREHOUSE', id: 'SNFK_04' },
    { name: 'BIGQUERY', type: 'WAREHOUSE', id: 'BQRY_09' },
    { name: 'MONGODB', type: 'NOSQL', id: 'MGDB_02' },
    { name: 'MYSQL', type: 'DATABASE', id: 'MSQL_07' },
    { name: 'EXCEL', type: 'FLAT_FILE', id: 'EXCL_03' },
    { name: 'GSHEETS', type: 'CLOUD_FILE', id: 'GSH_05' },
    { name: 'AIRTABLE', type: 'LOW_CODE', id: 'ARTB_08' },
    { name: 'CLICKHOUSE', type: 'OLAP', id: 'CKHS_06' },
    { name: 'DATABRICKS', type: 'LAKEHOUSE', id: 'DBKS_10' },
];

export function Integrations() {
    return (
        <section id="integrations" style={{ background: T.bg, padding: '160px 60px', borderTop: `1px solid ${T.border}` }}>
            <div style={{ maxWidth: 1200, margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: 100 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginBottom: 24 }}>
                      <div style={{ width: 60, height: 1, background: T.accent }} />
                      <span style={{ fontFamily: T.fontMono, fontSize: '0.65rem', color: T.accent, letterSpacing: 5, textTransform: 'uppercase', fontWeight: 950 }}>ECOSYSTEM_TOPOLOGY</span>
                      <div style={{ width: 60, height: 1, background: T.accent }} />
                    </div>
                    <h2 style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(2.5rem, 5vw, 4.5rem)', letterSpacing: -3, lineHeight: 0.9, color: T.text, textTransform: 'uppercase', fontStyle: 'italic' }}>
                        UNIVERSAL_NODE_ACCESS.
                    </h2>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 1, background: T.border, border: `1px solid ${T.border}` }}>
                    {tools.map((t) => (
                        <div
                            key={t.name}
                            style={{
                                background: T.bg,
                                padding: '56px 32px',
                                textAlign: 'left',
                                cursor: 'default',
                                position: 'relative',
                                overflow: 'hidden',
                                transition: 'all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)',
                            }}
                            onMouseEnter={e => { 
                              e.currentTarget.style.background = T.s1;
                              const overlay = e.currentTarget.querySelector('.node-overlay') as HTMLDivElement;
                              if (overlay) overlay.style.opacity = '1';
                            }}
                            onMouseLeave={e => { 
                              e.currentTarget.style.background = T.bg;
                              const overlay = e.currentTarget.querySelector('.node-overlay') as HTMLDivElement;
                              if (overlay) overlay.style.opacity = '0';
                            }}
                        >
                            {/* Technical Overlay */}
                            <div className="node-overlay" style={{ 
                              position: 'absolute', inset: 0, background: `${T.accent}05`, 
                              opacity: 0, transition: 'opacity 0.4s', pointerEvents: 'none' 
                            }} />

                            <div style={{ position: 'absolute', top: 20, right: 20, fontFamily: T.fontMono, fontSize: '0.5rem', color: T.text3, fontWeight: 950 }}>
                              NODE_{t.id}
                            </div>

                            <div style={{ 
                              width: 56, height: 56, background: T.s2, border: `1px solid ${T.border}`, 
                              display: 'flex', alignItems: 'center', justifyContent: 'center', 
                              marginBottom: 32, position: 'relative'
                            }}>
                                <Database size={20} color={T.accent} />
                                <div style={{ position: 'absolute', bottom: -4, right: -4, width: 8, height: 8, background: T.green }} />
                            </div>

                            <div style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: '0.95rem', color: T.text, textTransform: 'uppercase', marginBottom: 8 }}>{t.name}</div>
                            <div style={{ fontSize: '0.6rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 800, letterSpacing: '1.5px' }}>{t.type}</div>
                            
                            <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ flex: 1, height: 1, background: T.border }} />
                              <Shield size={10} color={T.text3} />
                              <div style={{ flex: 1, height: 1, background: T.border }} />
                            </div>
                        </div>
                    ))}
                </div>
                
                <div style={{ marginTop: 64, textAlign: 'center' }}>
                  <p style={{ fontFamily: T.fontMono, fontSize: '0.65rem', color: T.text3, fontWeight: 800, letterSpacing: '2px', textTransform: 'uppercase' }}>
                    + 40_ADDITIONAL_CONNECTORS_AVAILABLE // <a href="/auth" style={{ color: T.accent, textDecoration: 'none' }}>REQUEST_NODE_ACCESS</a>
                  </p>
                </div>
            </div>
        </section>
    );
}
