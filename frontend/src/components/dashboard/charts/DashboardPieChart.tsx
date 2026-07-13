import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { T } from '../tokens';
import type { DashboardWidgetItem, WidgetSize } from '../../../types/dashboard';
import type { ChartTooltipProps } from './chartTooltipTypes';

const COLORS = [
  '#00e5ff', '#7c3aff', '#22d3a5', '#f59e0b', '#f87171',
  '#a29bfe', '#fab1a0', '#81ecec', '#34d399', '#fb923c',
  '#e879f9', '#facc15', '#38bdf8', '#4ade80', '#f472b6',
];

const TT_STYLE = {
  borderRadius: 12, border: `1px solid ${T.border}`,
  boxShadow: '0 8px 32px rgba(0,0,0,0.12)', fontSize: '0.75rem',
  background: 'rgba(255, 255, 255, 0.8)', backdropFilter: 'blur(10px)',
  color: T.text, padding: '12px 16px',
};

const CustomTooltip = ({ active, payload }: ChartTooltipProps) => {
  if (active && payload && payload.length) {
    const p = payload[0];
    return (
      <div style={TT_STYLE}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.payload?.fill }} />
          <span style={{ fontWeight: 800, color: T.text, fontSize: '0.8rem', fontFamily: T.fontHead }}>
            {p.name}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20 }}>
          <span style={{ color: T.text2, fontSize: '0.7rem' }}>Value</span>
          <span style={{ fontWeight: 700, color: T.text, fontFamily: T.fontMono, fontSize: '0.75rem' }}>
            {formatVal(Number(p.value) || 0)}
          </span>
        </div>
      </div>
    );
  }
  return null;
};

function formatVal(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  if (abs < 10 && abs !== 0) return v.toFixed(1);
  return String(Math.round(v));
}

export function DashboardPieChart({ widget }: { widget: DashboardWidgetItem; size: WidgetSize }) {
  const isDonut = widget.viz_type === 'donut';
  const xCol = widget.chart_config?.x_column || widget.columns[0];
  let yCols: string[] = widget.chart_config?.y_columns?.length ? widget.chart_config.y_columns : [];

  if (yCols.length === 0 && widget.rows.length > 0) {
    const firstRow = widget.rows[0];
    yCols = widget.columns.filter(c => c !== xCol && typeof firstRow[c] === 'number');
    if (yCols.length === 0) yCols = [widget.columns[1]].filter(Boolean);
  } else if (yCols.length === 0) {
    yCols = [widget.columns[1]].filter(Boolean);
  }

  const data = widget.rows.map(row => {
    const v = row[yCols[0]];
    return {
      name: String(row[xCol] || 'Unknown'),
      value: typeof v === 'number' ? v : parseFloat(String(v)) || 0,
    };
  }).filter(item => item.value > 0);

  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;

  const chartHeight = 220;
  const outerRadius = "88%";
  const innerRadius = isDonut ? "62%" : 0;

  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '16px 16px 8px', gap: 12, height: 270, boxSizing: 'border-box' }}>
      {/* Left: pie / donut chart + total */}
      <div style={{ flex: '0 0 52%', minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              paddingAngle={4}
              cornerRadius={6}
              strokeWidth={0}
              isAnimationActive={true}
              animationDuration={1200}
            >
              {data.map((_, i) => (
                <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ 
          position: 'absolute', top: '50%', left: '50%', 
          transform: 'translate(-55%, -80%)', // Centered in the donut
          textAlign: 'center', pointerEvents: 'none',
          display: 'flex', flexDirection: 'column', alignItems: 'center'
        }}>
          <div style={{ fontSize: '0.55rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: 1 }}>Total</div>
          <div style={{ fontSize: '1.1rem', color: T.text, fontWeight: 800, fontFamily: T.fontHead }}>{formatVal(total)}</div>
        </div>
      </div>

      {/* Right: dot + name + % */}
      <div className="hide-scrollbar" style={{ flex: 1, minWidth: 0, maxHeight: chartHeight, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {data.map((item, i) => {
          const pct = (item.value / total * 100).toFixed(1);
          const color = COLORS[i % COLORS.length];
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
              <span style={{ fontSize: '0.7rem', color: T.text2, fontFamily: T.fontMono, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.name}
              </span>
              <span style={{ fontSize: '0.7rem', color: color, fontFamily: T.fontMono, flexShrink: 0, fontWeight: 600 }}>
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
