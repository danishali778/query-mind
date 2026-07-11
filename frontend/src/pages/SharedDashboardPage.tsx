import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import 'react-grid-layout/css/styles.css';

import { getSharedDashboard, getSharedDashboardWidgets } from '../services/api';
import { exportToPNG, exportToCSV } from '../utils/exportUtils';
import type { DashboardSummary, DashboardWidget } from '../types/api';
import { T } from '../components/dashboard/tokens';
import { resolveWidgetSize } from '../types/dashboard';

import { DashboardBarChart } from '../components/dashboard/charts/DashboardBarChart';
import { DashboardLineChart } from '../components/dashboard/charts/DashboardLineChart';
import { DashboardAreaChart } from '../components/dashboard/charts/DashboardAreaChart';
import { DashboardPieChart } from '../components/dashboard/charts/DashboardPieChart';

const ResponsiveGridLayout = WidthProvider(Responsive);

function formatMetric(value: unknown) {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toLocaleString();
  }
  return String(value ?? '-');
}

function KpiCard({ widget }: { widget: DashboardWidget }) {
  const metricCol = (widget.chart_config?.y_columns || []).find(Boolean)
    || widget.columns.find((c) => widget.rows.some((r) => typeof r[c] === 'number'));
  const labelCol = widget.chart_config?.x_column || widget.columns.find((c) => c !== metricCol);
  const primaryRow = widget.rows[widget.rows.length - 1] || widget.rows[0] || {};
  const metric = metricCol ? primaryRow[metricCol] : undefined;
  const label = labelCol ? String(primaryRow[labelCol] ?? '') : '';

  return (
    <div style={{
      background: T.s1, border: `1px solid ${T.border}`, borderRadius: 16, overflow: 'hidden', height: '100%',
      boxShadow: '0 4px 12px rgba(0,0,0,0.03)', padding: 16
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 10,
          background: 'linear-gradient(135deg, rgba(0,229,255,0.1), rgba(124,58,255,0.08))',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.accent, fontWeight: 700
        }}>
          $
        </div>
        <div>
          <div style={{ fontFamily: T.fontHead, fontWeight: 700, fontSize: '0.9rem', color: T.text }}>{widget.title}</div>
          <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, marginTop: 1 }}>{label || 'metric'}</div>
        </div>
      </div>
      <div>
        <div style={{ fontFamily: T.fontHead, fontWeight: 800, fontSize: '2.2rem', color: T.text, lineHeight: 1.1 }}>
          {formatMetric(metric)}
        </div>
        <div style={{ fontSize: '0.72rem', color: T.text3, marginTop: 2 }}>{metricCol || 'value'}</div>
      </div>
    </div>
  );
}

function ReadOnlyWidget({ widget }: { widget: DashboardWidget }) {
  const size = resolveWidgetSize(widget.size, widget.viz_type, widget.rows.length);
  if (widget.viz_type === 'kpi') {
    return <KpiCard widget={widget} />;
  }

  return (
    <div style={{
      background: T.s1, border: `1px solid ${T.border}`, borderRadius: 16, overflow: 'hidden',
      display: 'flex', flexDirection: 'column', height: '100%',
      boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', padding: '13px 16px 11px',
        borderBottom: `1px solid ${T.border}`
      }}>
        <div style={{ flex: 1, fontFamily: T.fontHead, fontWeight: 700, fontSize: '0.93rem', color: T.text }}>
          {widget.title}
        </div>
        {widget.rows && widget.rows.length > 0 && (
          <button
            onClick={() => exportToCSV(widget.rows, `${widget.title}_export`)}
            title="Download CSV"
            style={{
              background: 'transparent', border: 'none', color: T.text3, cursor: 'pointer', padding: 4
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </button>
        )}
      </div>
      <div style={{ flex: 1, padding: '12px 16px 16px' }}>
        {widget.viz_type === 'bar' && <DashboardBarChart widget={widget as any} size={size} />}
        {widget.viz_type === 'line' && <DashboardLineChart widget={widget as any} size={size} />}
        {widget.viz_type === 'area' && <DashboardAreaChart widget={widget as any} size={size} />}
        {(widget.viz_type === 'pie' || widget.viz_type === 'donut') && <DashboardPieChart widget={widget as any} size={size} />}
      </div>
    </div>
  );
}

export function SharedDashboardPage() {
  const { token } = useParams<{ token: string }>();
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [widgets, setWidgets] = useState<DashboardWidget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      if (!token) return;
      try {
        const [dash, wlist] = await Promise.all([
          getSharedDashboard(token),
          getSharedDashboardWidgets(token),
        ]);
        setDashboard(dash);
        setWidgets(wlist);
      } catch (err) {
        setError('Dashboard not found or not public.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const layouts = useMemo(() => {
    return {
      lg: widgets.map(w => ({
        i: w.id,
        x: w.x,
        y: w.y,
        w: w.viz_type === 'kpi' ? 5 : w.w,
        h: w.viz_type === 'kpi' ? 5 : (w.viz_type === 'table' ? w.h : 7),
        static: true // Make grid non-draggable in shared mode
      }))
    };
  }, [widgets]);

  if (loading) return <div style={{ padding: 40, color: T.text, background: T.bg, minHeight: '100vh' }}>Loading dashboard...</div>;
  if (error || !dashboard) return <div style={{ padding: 40, color: T.red, background: T.bg, minHeight: '100vh' }}>{error}</div>;

  return (
    <div style={{ background: T.bg, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        padding: '24px 40px', borderBottom: `1px solid ${T.border}`, background: T.s1,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, background: 'linear-gradient(135deg, rgba(0,229,255,0.1), rgba(124,58,255,0.1))',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem'
          }}>{dashboard.icon || '📊'}</div>
          <div>
            <h1 style={{ margin: 0, fontFamily: T.fontHead, fontSize: '1.4rem', color: T.text }}>{dashboard.name}</h1>
            <div style={{ fontSize: '0.8rem', color: T.text3, marginTop: 4 }}>Last updated {new Date(dashboard.created_at).toLocaleDateString()}</div>
          </div>
        </div>
        <button
          onClick={() => exportToPNG('shared-dashboard-grid', `${dashboard.name}_Export`)}
          style={{
            padding: '8px 16px', background: T.accent, color: '#fff', border: 'none', borderRadius: 8,
            fontFamily: T.fontBody, fontWeight: 600, cursor: 'pointer'
          }}
        >
          Download PNG
        </button>
      </header>

      <main style={{ flex: 1, padding: 32, overflowY: 'auto' }}>
        <div id="shared-dashboard-grid" style={{ padding: 20 }}>
          {widgets.length > 0 ? (
            <ResponsiveGridLayout
              layouts={layouts}
              breakpoints={{ lg: 1024, md: 996, sm: 768, xs: 480, xxs: 0 }}
              cols={{ lg: 20, md: 15, sm: 10, xs: 5, xxs: 2 }}
              rowHeight={30}
              margin={[20, 20]}
              isDraggable={false}
              isResizable={false}
            >
              {widgets.map(w => (
                <div key={w.id}>
                  <ReadOnlyWidget widget={w} />
                </div>
              ))}
            </ResponsiveGridLayout>
          ) : (
            <div style={{ textAlign: 'center', color: T.text3, padding: 60 }}>No widgets to display.</div>
          )}
        </div>
      </main>
    </div>
  );
}
