import { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar } from 'recharts';
import { BarChart3, Database, Layers, Layout, Activity } from 'lucide-react';
import { MainShell } from '../components/common/MainShell';
import { AnalyticsHero } from '../components/analytics/AnalyticsHero';
import { AnalyticsSectionCard } from '../components/analytics/AnalyticsSectionCard';
import { AnalyticsStatCard } from '../components/analytics/AnalyticsStatCard';
import { AnalyticsQueryTable } from '../components/analytics/AnalyticsQueryTable';
import { T } from '../components/dashboard/tokens';
import { getAnalyticsOverview } from '../services/api';
import type { AnalyticsOverviewResponse } from '../types/api';

const HEALTH_COLORS = [T.green, T.red];

function AnalyticsEmptyState() {
  return (
    <div style={{ 
      border: `1px solid rgba(0,0,0,0.08)`, 
      borderRadius: 0, 
      padding: '100px 40px', 
      background: '#fff', 
      textAlign: 'center',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 24
    }}>
      <div style={{ 
        width: 80, 
        height: 80, 
        borderRadius: 0, 
        background: 'rgba(0,0,0,0.02)', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        color: T.text3,
        border: '1px solid rgba(0,0,0,0.05)'
      }}>
        <BarChart3 size={40} strokeWidth={1.5} />
      </div>
      <div style={{ maxWidth: 480 }}>
        <h2 style={{ fontFamily: T.fontHead, fontSize: '1.8rem', color: T.text, marginBottom: 12, fontWeight: 900, fontStyle: 'italic' }}>Zero Instrumentation Found</h2>
        <p style={{ color: T.text3, lineHeight: 1.8, fontSize: '0.85rem', marginBottom: 32, fontFamily: T.fontMono, textTransform: 'uppercase' }}>
          Your analytics ledger is currently vacant. Execution telemetry is harvested from live query history and active dashboard distribution.
        </p>
        <a 
          href="/chat" 
          style={{ 
            display: 'inline-flex',
            alignItems: 'center',
            padding: '14px 32px',
            borderRadius: 0,
            background: T.text,
            color: '#fff',
            fontWeight: 900,
            textDecoration: 'none',
            fontSize: '0.75rem',
            fontFamily: T.fontMono,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            transition: 'all 0.2s'
          }}
          onMouseOver={(e) => { e.currentTarget.style.opacity = '0.9'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
          onMouseOut={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)'; }}
        >
          INITIATE FIRST QUERY
        </a>
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await getAnalyticsOverview();
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load analytics.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const overview = data?.overview;
  const queryHealth = data?.query_health;
  const library = data?.library;
  const dashboards = data?.dashboards;
  const healthData = queryHealth
    ? [
        { name: 'Successful', value: queryHealth.successful },
        { name: 'Failed', value: queryHealth.failed },
      ]
    : [];

  return (
    <MainShell
      title="Analytical Intelligence"
      subtitle="Universal telemetry across all infrastructure"
      badge={{
        text: 'LIVE LEDGER',
        color: T.text,
        icon: <div style={{ width: 6, height: 6, borderRadius: 0, background: T.text }} />
      }}
    >
      <div style={{ flex: 1, minWidth: 0, overflowY: 'auto', overflowX: 'hidden', padding: '0 2px 40px' }} className="custom-scroll">
        <AnalyticsHero />

        {loading ? (
          <div style={{ padding: '120px 0', textAlign: 'center', color: T.text3, fontFamily: T.fontMono, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Synchronizing telemetry...
          </div>
        ) : error ? (
          <div style={{ padding: '120px 0', textAlign: 'center', color: T.red, fontFamily: T.fontMono, fontSize: '0.72rem', textTransform: 'uppercase' }}>
            Transmission Error: {error}
          </div>
        ) : overview && overview.total_queries === 0 ? (
          <AnalyticsEmptyState />
        ) : overview ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16, marginBottom: 24 }}>
              <AnalyticsStatCard label="Active Nodes" value={String(overview.active_connections)} hint="Synchronized databases" />
              <AnalyticsStatCard label="Execution Volume" value={String(overview.total_queries)} hint={`${overview.success_rate}% success threshold`} tone="green" />
              <AnalyticsStatCard label="Asset Density" value={String(overview.saved_queries)} hint={`${overview.scheduled_queries} automated tasks`} tone="purple" />
              <AnalyticsStatCard label="Interface Assets" value={String(overview.dashboards)} hint={`${overview.total_widgets} active components`} tone="yellow" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
              <AnalyticsSectionCard eyebrow="Reliability metrics" title="Execution Quality">
                <div style={{ height: 260, width: '100%', display: 'flex', alignItems: 'center' }}>
                  <ResponsiveContainer width="45%" height="100%">
                    <PieChart>
                      <Pie data={healthData} innerRadius={60} outerRadius={85} paddingAngle={0} dataKey="value" stroke="none">
                        {healthData.map((_entry, index) => (
                          <Cell key={`cell-${index}`} fill={HEALTH_COLORS[index % HEALTH_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ background: '#fff', border: `1px solid ${T.text}`, borderRadius: 0, fontSize: '0.68rem', fontFamily: T.fontMono, boxShadow: 'none' }}
                        itemStyle={{ color: T.text, fontWeight: 700 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  
                  <div style={{ flex: 1, paddingLeft: 40, borderLeft: '1px solid rgba(0,0,0,0.05)' }}>
                    <div style={{ fontSize: '3.2rem', fontFamily: T.fontHead, color: T.text, fontWeight: 900, fontStyle: 'italic', lineHeight: 1 }}>{overview.success_rate}%</div>
                    <div style={{ color: T.text3, fontSize: '0.62rem', marginTop: 8, letterSpacing: '0.15em', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase' }}>AGGREGATE RELIABILITY</div>
                    
                    <div style={{ marginTop: 32, display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ width: 8, height: 8, borderRadius: 0, background: T.green }} />
                          <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 800, textTransform: 'uppercase' }}>Successful</span>
                        </div>
                        <span style={{ fontSize: '0.85rem', color: T.text, fontWeight: 900, fontFamily: T.fontMono }}>{queryHealth?.successful}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ width: 8, height: 8, borderRadius: 0, background: T.red }} />
                          <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 800, textTransform: 'uppercase' }}>Failed</span>
                        </div>
                        <span style={{ fontSize: '0.85rem', color: T.text, fontWeight: 900, fontFamily: T.fontMono }}>{queryHealth?.failed}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </AnalyticsSectionCard>

              <AnalyticsSectionCard eyebrow="Infrastructure" title="Asset Inventory">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingTop: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ color: T.text3, fontSize: '0.62rem', fontWeight: 900, letterSpacing: '0.1em', marginBottom: 8, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Library Density</div>
                      <div style={{ fontSize: '1.8rem', fontFamily: T.fontHead, fontWeight: 900, fontStyle: 'italic' }}>{library?.total_queries || 0} <span style={{ fontSize: '0.8rem', fontStyle: 'normal', fontWeight: 400, color: T.text3 }}>QUERIES</span></div>
                    </div>
                    <div style={{ height: 44, width: 80, opacity: 0.8 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={[{v: 4}, {v: 7}, {v: 5}, {v: 9}, {v: 6}, {v: 8}]}>
                          <Bar dataKey="v" fill={T.text} radius={0} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                  
                  <div style={{ height: 1, background: 'rgba(0,0,0,0.05)' }} />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ color: T.text3, fontSize: '0.62rem', fontWeight: 900, letterSpacing: '0.1em', marginBottom: 8, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Visualization Distribution</div>
                      <div style={{ fontSize: '1.8rem', fontFamily: T.fontHead, fontWeight: 900, fontStyle: 'italic' }}>{dashboards?.total_widgets || 0} <span style={{ fontSize: '0.8rem', fontStyle: 'normal', fontWeight: 400, color: T.text3 }}>WIDGETS</span></div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {Object.entries(dashboards?.viz_breakdown || {}).slice(0, 4).map(([key, val]) => (
                        <div key={key} title={`${key}: ${val}`} style={{ 
                          width: 32, height: 32, borderRadius: 0, background: '#fff', 
                          display: 'flex', alignItems: 'center', justifyContent: 'center', 
                          color: T.text, border: `1px solid rgba(0,0,0,0.1)`,
                          transition: 'all 0.15s'
                        }} onMouseEnter={e => e.currentTarget.style.borderColor = T.text}
                           onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'}
                        >
                          {key === 'table' ? <Layers size={14} /> : key === 'bar' ? <BarChart3 size={14} /> : <Layout size={14} />}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
                    <div style={{ flex: 1, padding: '16px', background: 'rgba(0,0,0,0.02)', borderLeft: `2px solid ${T.text}` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: T.text3, marginBottom: 4 }}>
                        <Database size={12} />
                        <span style={{ fontSize: '0.58rem', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Storage</span>
                      </div>
                      <div style={{ fontSize: '0.9rem', fontWeight: 900, color: T.text, fontFamily: T.fontMono }}>{overview.active_connections} NODES</div>
                    </div>
                    <div style={{ flex: 1, padding: '16px', background: 'rgba(0,0,0,0.02)', borderLeft: `2px solid ${T.text}` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: T.text3, marginBottom: 4 }}>
                        <Activity size={12} />
                        <span style={{ fontSize: '0.58rem', fontWeight: 900, fontFamily: T.fontMono, textTransform: 'uppercase' }}>Uptime</span>
                      </div>
                      <div style={{ fontSize: '0.9rem', fontWeight: 900, color: T.text, fontFamily: T.fontMono }}>99.9% LIVE</div>
                    </div>
                  </div>
                </div>
              </AnalyticsSectionCard>
            </div>

            <AnalyticsQueryTable queries={data?.recent_queries || []} />
          </>
        ) : null}
      </div>

      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 2px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); }
      `}</style>
    </MainShell>
  );
}
