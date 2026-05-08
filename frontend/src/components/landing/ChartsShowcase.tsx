import { T } from '../dashboard/tokens';

export function ChartsShowcase() {
    return (
        <section id="charts" style={{ background: T.s1, padding: '120px 60px', borderTop: `1px solid ${T.border}` }}>
            <div style={{ textAlign: 'center', marginBottom: 80 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginBottom: 20 }}>
                  <div style={{ width: 40, height: 1, background: T.accent }} />
                  <span style={{ fontFamily: T.fontMono, fontSize: '0.65rem', color: T.accent, letterSpacing: 4, textTransform: 'uppercase', fontWeight: 950 }}>DATA_VISUALIZATION_NODE</span>
                </div>
                <h2 style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: 'clamp(2.5rem, 5vw, 4rem)', letterSpacing: -3, lineHeight: 0.9, color: T.text, textTransform: 'uppercase' }}>
                    ENGINEERED_INSIGHTS
                </h2>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 1, background: T.border, maxWidth: 1200, margin: '0 auto' }}>
                {/* Featured: Line Chart */}
                <div style={{ background: T.bg, padding: 40 }}>
                    <div style={{ fontFamily: T.fontMono, fontSize: '0.6rem', color: T.accent, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8, letterSpacing: 2, fontWeight: 950 }}>
                        <div style={{ width: 8, height: 8, background: T.accent }} /> SYSTEM_TELEMETRY // REVENUE_STREAM
                    </div>
                    <div style={{ fontFamily: T.fontHead, fontWeight: 950, fontSize: '1.2rem', marginBottom: 32, color: T.text, letterSpacing: '-1px', textTransform: 'uppercase' }}>MONTHLY_REVENUE_METRIC</div>
                    <svg style={{ width: '100%', height: 260, overflow: 'visible' }} viewBox="0 0 480 200">
                        {[40, 80, 120, 160].map(y => (
                            <line key={y} x1="0" y1={y} x2="480" y2={y} stroke={T.border} strokeWidth="1" strokeDasharray="4,4" />
                        ))}
                        <path d="M 0,140 L 40,128 L 80,118 L 120,122 L 160,105 L 200,90 L 240,82 L 280,72 L 320,65 L 360,55 L 400,48 L 440,42 L 480,36" fill="none" stroke={T.accent} strokeWidth="3" />
                        <path d="M 0,140 L 40,128 L 80,118 L 120,122 L 160,105 L 200,90 L 240,82 L 280,72 L 320,65 L 360,55 L 400,48 L 440,42 L 480,36 L 480,200 L 0,200 Z" fill={T.accent} opacity={0.05} />
                        
                        {['JAN', 'MAR', 'MAY', 'JUL', 'SEP', 'NOV'].map((m, i) => (
                            <text key={m} x={i * 80} y="195" fill={T.text3} fontSize="9" fontFamily={T.fontMono} fontWeight={950}>{m}</text>
                        ))}
                    </svg>
                </div>

                <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 1, background: T.border }}>
                    {/* Bar Chart */}
                    <div style={{ background: T.bg, padding: 32 }}>
                        <div style={{ fontFamily: T.fontMono, fontSize: '0.6rem', color: T.text3, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, letterSpacing: 1, fontWeight: 800 }}>
                             REGIONAL_DISTRIBUTION
                        </div>
                        <svg style={{ width: '100%', height: 120, overflow: 'visible' }} viewBox="0 0 220 120">
                            {[
                                { x: 8, y: 20, h: 80, label: 'NA' },
                                { x: 48, y: 40, h: 60, label: 'EU' },
                                { x: 88, y: 30, h: 70, label: 'AS' },
                                { x: 128, y: 60, h: 40, label: 'SA' },
                                { x: 168, y: 70, h: 30, label: 'AF' },
                            ].map(b => (
                                <g key={b.label}>
                                    <rect x={b.x} y={b.y} width="24" height={b.h} fill={T.s2} stroke={T.border} />
                                    <rect x={b.x} y={b.y} width="24" height={b.h} fill={T.accent} opacity={0.2} />
                                    <text x={b.x + 12} y="115" fill={T.text3} fontSize="8" fontFamily={T.fontMono} fontWeight={950} textAnchor="middle">{b.label}</text>
                                </g>
                            ))}
                        </svg>
                    </div>

                    {/* Donut */}
                    <div style={{ background: T.bg, padding: 32 }}>
                         <div style={{ fontFamily: T.fontMono, fontSize: '0.6rem', color: T.text3, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, letterSpacing: 1, fontWeight: 800 }}>
                             RESOURCE_ALLOCATION
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                            <svg viewBox="0 0 110 110" style={{ width: 80, flexShrink: 0 }}>
                                <circle cx="55" cy="55" r="45" fill="none" stroke={T.border} strokeWidth="12" />
                                <circle cx="55" cy="55" r="45" fill="none" stroke={T.accent} strokeWidth="12" strokeDasharray="120 280" transform="rotate(-90 55 55)" />
                            </svg>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {[
                                    { color: T.accent, text: 'CORE_ENGINE' },
                                    { color: T.text2, text: 'NODE_ACCESS' },
                                    { color: T.text3, text: 'LEGACY_SYNC' },
                                ].map(l => (
                                    <div key={l.text} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.55rem', color: T.text2, fontFamily: T.fontMono, fontWeight: 950 }}>
                                        <div style={{ width: 6, height: 6, background: l.color }} />
                                        {l.text}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
