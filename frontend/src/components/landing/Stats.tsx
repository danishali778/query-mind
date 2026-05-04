import { useEffect, useState } from 'react';
import { T } from '../dashboard/tokens';

const stats = [
    { num: 10, suffix: 'X', label: 'ACCELERATED_WORKFLOW', sub: 'LATENCY_BUFFER: -88%' },
    { num: 50, suffix: '+', label: 'DB_INTEGRATIONS', sub: 'PROTOCOL: UNIVERSAL' },
    { num: 99.2, suffix: '%', label: 'QUERY_ACCURACY', sub: 'ERROR_RATE: <0.08%' },
    { num: 2, suffix: 'S', label: 'RESPONSE_LATENCY', sub: 'SYNC_STABILITY: ALPHA' },
];

export function Stats() {
    const [counts, setCounts] = useState(stats.map(() => 0));

    useEffect(() => {
        const duration = 2000;
        const steps = 60;
        const interval = duration / steps;
        
        let currentStep = 0;
        const iv = setInterval(() => {
            currentStep++;
            setCounts(stats.map(s => {
                const target = s.num;
                const val = (target / steps) * currentStep;
                return val > target ? target : val;
            }));
            
            if (currentStep >= steps) clearInterval(iv);
        }, interval);
        
        return () => clearInterval(iv);
    }, []);

    return (
        <div style={{ 
            display: 'flex', justifyContent: 'center', 
            borderTop: `1px solid ${T.border}`, 
            borderBottom: `1px solid ${T.border}`, 
            background: T.s2,
            flexWrap: 'wrap'
        }}>
            {stats.map((s, i) => (
                <div
                    key={i}
                    style={{
                        flex: 1,
                        minWidth: 250,
                        padding: '64px 48px',
                        textAlign: 'left',
                        borderRight: i < stats.length - 1 ? `1px solid ${T.border}` : 'none',
                        fontFamily: T.fontMono,
                        position: 'relative'
                    }}
                >
                    <div style={{ fontSize: '0.55rem', color: T.accent, fontWeight: 950, marginBottom: 16, letterSpacing: 2 }}>METRIC_NODE_0{i+1}</div>
                    <div style={{ fontSize: '3.5rem', fontWeight: 950, color: T.text, letterSpacing: '-4px', lineHeight: 1 }}>
                        {s.num % 1 === 0 ? Math.floor(counts[i]) : counts[i].toFixed(1)}{s.suffix}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: T.text, marginTop: 20, fontWeight: 950, letterSpacing: '2px', textTransform: 'uppercase' }}>{s.label}</div>
                    <div style={{ fontSize: '0.55rem', color: T.text3, marginTop: 8, fontWeight: 800, letterSpacing: '1px' }}>{s.sub}</div>
                    
                    {/* Decorative Corner */}
                    <div style={{ position: 'absolute', bottom: 0, right: 0, width: 20, height: 20, borderRight: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}` }} />
                </div>
            ))}
        </div>
    );
}
