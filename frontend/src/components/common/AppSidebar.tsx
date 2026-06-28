import { useLocation, useNavigate } from 'react-router-dom';
import { 
  MessageSquare, 
  LayoutDashboard, 
  Library, 
  BarChart3, 
  Database, 
  Settings,
  ShieldCheck,
  ChevronRight
} from 'lucide-react';
import { T } from '../dashboard/tokens';
import { useSettingsStore } from '../../store/settingsStore';

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  path?: string;
  active?: boolean;
  onMouseEnter?: (e: React.MouseEvent) => void;
  onMouseLeave?: (e: React.MouseEvent) => void;
}

function NavItem({ icon, label, path, active, onMouseEnter, onMouseLeave }: NavItemProps) {
  const navigate = useNavigate();
  const clickable = Boolean(path);

  return (
    <div
      onClick={() => { if (path) navigate(path); }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        borderRadius: 0,
        cursor: clickable ? 'pointer' : 'default',
        transition: 'all 0.15s ease',
        marginBottom: 2,
        color: active ? T.text : T.text3,
        fontSize: '0.82rem',
        fontWeight: active ? 700 : 500,
        background: active ? '#fff' : 'transparent',
        border: `1px solid ${active ? 'rgba(0,0,0,0.08)' : 'transparent'}`,
        fontFamily: T.fontBody,
        position: 'relative',
      }}
      onMouseEnter={e => {
        if (!active && clickable) {
          e.currentTarget.style.background = 'rgba(0,0,0,0.02)';
          e.currentTarget.style.color = T.text;
        }
        onMouseEnter?.(e);
      }}
      onMouseLeave={e => {
        if (!active && clickable) {
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.color = T.text3;
        }
        onMouseLeave?.(e);
      }}
    >
      {/* Active Indicator Strip */}
      {active && (
        <div style={{
          position: 'absolute',
          left: -1,
          top: 0,
          bottom: 0,
          width: 2,
          background: T.text,
        }} />
      )}

      <span style={{
        width: 18,
        height: 18,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: active ? 1 : 0.6,
      }}>
        {icon}
      </span>
      <span style={{ flex: 1 }}>{label}</span>
      {active && <ChevronRight size={12} style={{ opacity: 0.3 }} />}
    </div>
  );
}

const sectionLabel: React.CSSProperties = {
  fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.15em',
  color: T.text3, textTransform: 'uppercase',
  padding: '24px 14px 8px', fontFamily: T.fontMono,
};

/** Just the nav items — usable inside other sidebars (e.g. Chat) */
export function NavSection({ onDashboardHover }: { onDashboardHover?: (hovering: boolean) => void }) {
  const location = useLocation();
  const p = location.pathname;

  return (
    <div style={{ padding: '0 8px' }}>
      <div style={sectionLabel}>General</div>
      <NavItem icon={<MessageSquare size={16} />} label="Chat" path="/chat" active={p === '/chat'} />
      <NavItem 
        icon={<LayoutDashboard size={16} />} 
        label="Dashboards" 
        path="/dashboard" 
        active={p === '/dashboard'} 
        onMouseEnter={() => onDashboardHover?.(true)}
        onMouseLeave={() => onDashboardHover?.(false)}
      />
      <NavItem icon={<Library size={16} />} label="Library" path="/library" active={p === '/library'} />
      <NavItem icon={<BarChart3 size={16} />} label="Analytics" path="/analytics" active={p === '/analytics'} />

      <div style={{ ...sectionLabel, paddingTop: 32 }}>Infrastructure</div>
      <NavItem icon={<Database size={16} />} label="Connections" path="/connections" active={p === '/connections'} />
      <NavItem icon={<Settings size={16} />} label="Settings" path="/settings" active={p === '/settings'} />
    </div>
  );
}

/** Full app sidebar — used by Dashboard, Library, Connections, Analytics */
export function AppSidebar({ onDashboardHover }: { onDashboardHover?: (hovering: boolean) => void, activeId?: string }) {
  const { settings } = useSettingsStore();
  const displayName = settings?.full_name || 'User';
  const avatarInitials = displayName.substring(0, 1).toUpperCase();

  return (
    <aside style={{
      width: 260, flexShrink: 0,
      background: T.bg, 
      borderRight: `1px solid rgba(0,0,0,0.08)`,
      display: 'flex', flexDirection: 'column',
      height: '100vh', overflow: 'hidden',
      fontFamily: T.fontBody,
      zIndex: 100,
    }}>
      {/* Logo Section */}
      <div style={{ padding: '32px 20px 12px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14,
          fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.4rem',
          letterSpacing: -1, padding: '4px 0', marginBottom: 24, color: T.text,
          fontStyle: 'italic'
        }}>
          {/* Black Square Logo */}
          <div style={{ 
            width: 32, height: 32, 
            background: T.text,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '1rem', fontWeight: 900, flexShrink: 0
          }}>
            Q
          </div>
          query-mind
        </div>

        <NavSection onDashboardHover={onDashboardHover} />
      </div>

      {/* User Footer - Editorial Style */}
      <div style={{ marginTop: 'auto', padding: '24px 20px', borderTop: `1px solid rgba(0,0,0,0.05)`, background: 'rgba(0,0,0,0.01)' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '12px',
          borderRadius: 0, cursor: 'pointer', transition: 'all 0.2s',
          border: '1px solid transparent',
          background: 'transparent'
        }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#fff';
            e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = 'transparent';
          }}
        >
          <div style={{
            width: 36, height: 36, borderRadius: 0, flexShrink: 0,
            background: T.text,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.9rem', fontWeight: 900, color: '#fff',
            fontFamily: T.fontHead, fontStyle: 'italic'
          }}>{avatarInitials}</div>
          
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ 
              fontSize: '0.8rem', fontWeight: 800, color: T.text, 
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              fontFamily: T.fontHead, fontStyle: 'italic'
            }}>
              {displayName}
            </div>
            <div style={{ 
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: '0.62rem', color: T.accent, fontWeight: 700, 
              textTransform: 'uppercase', letterSpacing: '0.05em',
              fontFamily: T.fontMono
            }}>
              <ShieldCheck size={10} /> PRO MEMBER
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
