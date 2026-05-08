import { useLocation, useNavigate } from 'react-router-dom';
import { T } from './tokens';
import { Activity, Database, Settings, Bell, LayoutGrid, MessageSquare, Library } from 'lucide-react';

type SidebarItem = {
  icon: React.ReactNode;
  label: string;
  path?: string;
  badge?: string;
  badgeColor?: boolean;
};

const NAV_ITEMS: SidebarItem[] = [
  { icon: <MessageSquare size={14} />, label: 'CHAT_PROTOCOL', path: '/chat' },
  { icon: <LayoutGrid size={14} />, label: 'DASHBOARDS', badge: '03', path: '/dashboard' },
  { icon: <Library size={14} />, label: 'QUERY_LIBRARY', badge: '24', path: '/library' },
  { icon: <Activity size={14} />, label: 'LIVE_ANALYTICS', path: '/analytics' },
];

const WORKSPACE_ITEMS: SidebarItem[] = [
  { icon: <Database size={14} />, label: 'NODE_CONNECTIONS', badge: '03', path: '/connections' },
  { icon: <Bell size={14} />, label: 'SYSTEM_ALERTS', badge: '02', badgeColor: true },
  { icon: <Settings size={14} />, label: 'CORE_SETTINGS', path: '/settings' },
];

export function DashboardSidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  const renderItem = (item: SidebarItem, i: number) => {
    const isActive = Boolean(item.path && location.pathname === item.path);

    return (
      <div
        key={i}
        onClick={() => (item.path ? navigate(item.path) : undefined)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          cursor: item.path ? 'pointer' : 'default',
          transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
          color: isActive ? T.text : T.text3,
          fontSize: '0.62rem',
          background: isActive ? T.s2 : 'transparent',
          borderLeft: `2px solid ${isActive ? T.accent : 'transparent'}`,
          fontFamily: T.fontMono,
          fontWeight: 900,
          letterSpacing: '1.5px',
          textTransform: 'uppercase'
        }}
        onMouseEnter={(e) => {
          if (!isActive && item.path) {
            e.currentTarget.style.background = T.s2;
            e.currentTarget.style.color = T.text;
          }
        }}
        onMouseLeave={(e) => {
          if (!isActive && item.path) {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = T.text3;
          }
        }}
      >
        <span style={{ color: isActive ? T.accent : T.text3, opacity: isActive ? 1 : 0.6 }}>
          {item.icon}
        </span>
        {item.label}
        {item.badge && (
          <span
            style={{
              marginLeft: 'auto',
              background: item.badgeColor ? T.red : T.text,
              color: T.bg,
              fontSize: '0.55rem',
              fontFamily: T.fontMono,
              padding: '2px 6px',
              fontWeight: 950
            }}
          >
            {item.badge}
          </span>
        )}
      </div>
    );
  };

  return (
    <aside
      style={{
        width: 240,
        flexShrink: 0,
        background: T.bg,
        borderRight: `1px solid ${T.border}`,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        zIndex: 100
      }}
    >
      {/* Brand Section */}
      <div style={{ padding: '32px 24px', borderBottom: `1px solid ${T.border}` }}>
        <div
          onClick={() => navigate('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontFamily: T.fontHead,
            fontWeight: 950,
            fontSize: '1.3rem',
            letterSpacing: -1,
            color: T.text,
            cursor: 'pointer'
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              background: T.text,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.9rem',
              color: T.bg,
              fontWeight: 950,
              boxShadow: `4px 4px 0px ${T.accent}`
            }}
          >
            Q
          </div>
          QUERY<span style={{ color: T.accent }}>MIND</span>
        </div>
      </div>

      {/* Nav Groups */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 0' }}>
        <div style={{
          fontSize: '0.55rem', fontWeight: 950, letterSpacing: '3px', color: T.accent,
          textTransform: 'uppercase', padding: '0 24px 16px', fontFamily: T.fontMono,
          display: 'flex', alignItems: 'center', gap: 8
        }}>
          <div style={{ width: 12, height: 1, background: T.accent }} />
          CORE_PROTOCOLS
        </div>
        {NAV_ITEMS.map(renderItem)}

        <div style={{
          fontSize: '0.55rem', fontWeight: 950, letterSpacing: '3px', color: T.accent,
          textTransform: 'uppercase', padding: '32px 24px 16px', fontFamily: T.fontMono,
          display: 'flex', alignItems: 'center', gap: 8
        }}>
          <div style={{ width: 12, height: 1, background: T.accent }} />
          WORKSPACE_NODES
        </div>
        {WORKSPACE_ITEMS.map(renderItem)}
      </div>

      {/* Footer / Profile */}
      <div style={{ marginTop: 'auto', padding: '24px', background: T.s2, borderTop: `1px solid ${T.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 36,
              height: 36,
              background: T.text,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              fontWeight: 950,
              color: T.bg,
              boxShadow: `3px 3px 0px ${T.accent}`
            }}
          >
            AK
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 950, color: T.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textTransform: 'uppercase' }}>Ahmad Khan</div>
            <div style={{ fontSize: '0.55rem', color: T.accent, fontFamily: T.fontMono, fontWeight: 950, letterSpacing: 1 }}>PRO_SUBSCRIPTION</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
