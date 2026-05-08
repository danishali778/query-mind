import { useState } from 'react';
import { 
  DollarSign, 
  User, 
  TrendingDown, 
  Users, 
  ShoppingCart, 
  Megaphone, 
  Box, 
  Clipboard, 
  Globe, 
  FileText, 
  Calendar,
  Terminal,
  Activity
} from 'lucide-react';
import { T } from '../dashboard/tokens';
import { highlightSqlInline } from '../../utils/sqlHighlight';
import type { LibraryQuery } from '../../types/library';

interface QueryCardProps {
  data: LibraryQuery;
  isSelected?: boolean;
  onClick?: () => void;
  onScheduleClick?: () => void;
  index?: number;
}

function timeAgo(ts: string | null): string {
  if (!ts) return 'Never';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const TAG_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  revenue: { bg: 'rgba(0,0,0,0.02)', color: T.text, border: 'rgba(0,0,0,0.1)' },
  churn: { bg: 'rgba(248, 113, 113, 0.05)', color: T.red, border: 'rgba(248, 113, 113, 0.15)' },
  users: { bg: 'rgba(34, 211, 165, 0.05)', color: T.green, border: 'rgba(34, 211, 165, 0.15)' },
  daily: { bg: 'rgba(245, 158, 11, 0.05)', color: T.yellow, border: 'rgba(245, 158, 11, 0.15)' },
  critical: { bg: 'rgba(248, 113, 113, 0.05)', color: T.red, border: 'rgba(248, 113, 113, 0.15)' },
  customers: { bg: 'rgba(124, 58, 255, 0.05)', color: T.purple, border: 'rgba(124, 58, 255, 0.15)' },
  funnel: { bg: 'rgba(245, 158, 11, 0.05)', color: T.yellow, border: 'rgba(245, 158, 11, 0.15)' },
  marketing: { bg: 'rgba(0,0,0,0.02)', color: T.text3, border: 'rgba(0,0,0,0.1)' },
};
const DEFAULT_TAG = { bg: 'rgba(0,0,0,0.02)', color: T.text3, border: 'rgba(0,0,0,0.08)' };

function inferIcon(data: LibraryQuery): { icon: React.ReactNode; bg: string; color: string } {
  const s = `${data.title} ${data.sql} ${data.tags.join(' ')}`.toLowerCase();
  if (s.includes('revenue') || s.includes('sales')) return { icon: <DollarSign size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text };
  if (s.includes('customer') || s.includes('user') || s.includes('client')) return { icon: <User size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text };
  if (s.includes('churn') || s.includes('cancel')) return { icon: <TrendingDown size={16} />, bg: 'rgba(248,113,113,0.05)', color: T.red };
  if (s.includes('dau') || s.includes('active user') || s.includes('session')) return { icon: <Users size={16} />, bg: 'rgba(34,211,165,0.05)', color: T.green };
  if (s.includes('cart') || s.includes('funnel') || s.includes('conversion')) return { icon: <ShoppingCart size={16} />, bg: 'rgba(245,158,11,0.05)', color: T.yellow };
  if (s.includes('marketing') || s.includes('signup') || s.includes('utm')) return { icon: <Megaphone size={16} />, bg: 'rgba(124,58,255,0.05)', color: T.purple };
  if (s.includes('product') || s.includes('inventory')) return { icon: <Box size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text };
  if (s.includes('order') || s.includes('shipment')) return { icon: <Clipboard size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text };
  if (s.includes('region') || s.includes('country') || s.includes('geo')) return { icon: <Globe size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text };
  return { icon: <FileText size={16} />, bg: 'rgba(0,0,0,0.03)', color: T.text3 };
}

export function QueryCard({ data, isSelected, onClick, onScheduleClick, index = 0 }: QueryCardProps) {
  const [hovered, setHovered] = useState(false);
  const connectionLabel = data.connection_id || 'No connection';
  const folderLabel = data.folder_name || 'Uncategorized';
  const isScheduled = Boolean(data.schedule_label);
  const visual = inferIcon(data);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: '#fff',
        border: `1px solid ${isSelected ? T.text : hovered ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.08)'}`,
        borderRadius: 0,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative',
        boxShadow: isSelected ? '0 12px 40px rgba(0,0,0,0.08)' : 'none',
        animation: `fadeUp 0.35s ease both`,
        animationDelay: `${index * 0.03}s`,
      }}
    >
      {/* Header */}
      <div style={{ padding: '18px 20px 12px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, background: visual.bg, color: visual.color
        }}>
          {visual.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.1rem', color: T.text,
            marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            fontStyle: 'italic', letterSpacing: -0.5
          }}>
            {data.title}
          </div>
          <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {folderLabel} <span style={{ opacity: 0.3 }}>/</span> {connectionLabel}
          </div>
        </div>
      </div>

      {/* SQL Preview */}
      <div style={{
        margin: '0 20px', padding: '14px',
        background: T.s2, border: `1px solid rgba(0,0,0,0.05)`, borderRadius: 0,
        fontFamily: T.fontMono, fontSize: '0.7rem', lineHeight: 1.6,
        overflow: 'hidden', maxHeight: 90, position: 'relative',
        color: T.text2,
      }}>
        <div style={{ position: 'absolute', right: 8, top: 6, opacity: 0.2 }}><Terminal size={12} /></div>
        {highlightSqlInline(data.sql, 'card')}
        {/* Fade gradient */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 32,
          background: `linear-gradient(transparent, ${T.s2})`, pointerEvents: 'none',
        }} />
      </div>

      {/* Meta row 1: connection + tags + run count */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 20px 10px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 6, flex: 1, flexWrap: 'wrap' }}>
          {data.tags.slice(0, 3).map((t) => {
            const colors = TAG_COLORS[t] || DEFAULT_TAG;
            return (
              <span key={t} style={{
                padding: '2px 8px', borderRadius: 0, fontSize: '0.58rem', fontFamily: T.fontMono,
                border: `1px solid ${colors.border}`, background: colors.bg, color: colors.color,
                fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em'
              }}>{t}</span>
            );
          })}
        </div>
        <div style={{ 
          display: 'flex', alignItems: 'center', gap: 5,
          fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, marginLeft: 'auto',
          fontWeight: 700
        }}>
          <Activity size={10} /> {data.run_count} RUNS
        </div>
      </div>

      {/* Meta row 2: schedule + timestamp */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 20px 18px' }}>
        {isScheduled && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.62rem', fontFamily: T.fontMono,
            color: T.text, background: '#fff', fontWeight: 800,
            border: '1px solid rgba(0,0,0,0.15)', borderRadius: 0, padding: '2px 8px', whiteSpace: 'nowrap',
          }}>
            <Calendar size={10} /> {data.schedule_label?.toUpperCase()}
          </div>
        )}
        <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, marginLeft: 'auto', fontWeight: 600 }}>
          LAST RUN: {timeAgo(data.last_run_at || data.updated_at).toUpperCase()}
        </span>
      </div>

      {/* Action bar */}
      <div style={{ display: 'flex', alignItems: 'center', borderTop: `1px solid rgba(0,0,0,0.08)`, background: 'rgba(0,0,0,0.01)' }}>
        <ActionBtn label="CONFIGURE TASK" icon={<Calendar size={12} />} hoverColor={T.text} onClick={onScheduleClick} isLast />
      </div>

      <style>{`
        @keyframes fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

function ActionBtn({ label, icon, hoverColor, isLast, onClick }: { label: string; icon: React.ReactNode; hoverColor?: string; isLast?: boolean; onClick?: () => void }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick?.(); }}
      style={{
        flex: 1, padding: '10px 12px', background: 'transparent', border: 'none',
        color: T.text3, fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer', transition: 'all 0.15s ease',
        fontFamily: T.fontMono, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        borderRight: isLast ? 'none' : `1px solid rgba(0,0,0,0.08)`,
        letterSpacing: '0.05em'
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.color = hoverColor || T.text; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = T.text3; }}
    >
      {icon} {label}
    </button>
  );
}
