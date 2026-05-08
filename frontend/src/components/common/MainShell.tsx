import React from 'react';
import { AppSidebar } from './AppSidebar';
import { AppHeader } from './AppHeader';
import { T } from '../dashboard/tokens';
import { DashboardBackground } from '../layout/DashboardBackground';

interface MainShellProps {
  title: string;
  subtitle?: string;
  badge?: {
    text: string;
    color: string;
    icon?: React.ReactNode;
  };
  headerActions?: React.ReactNode;
  children: React.ReactNode;
  onDashboardHover?: (hovering: boolean) => void;
  hideSidebar?: boolean;
  activeId?: string;
  hideHeader?: boolean;
}

export function MainShell({
  title,
  subtitle,
  badge,
  headerActions,
  children,
  onDashboardHover,
  hideSidebar = false,
  activeId,
  hideHeader = false
}: MainShellProps) {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      overflow: 'hidden',
      background: 'transparent', // Let mesh background show through
      fontFamily: T.fontBody,
      color: T.text,
      position: 'relative'
    }}>
      <DashboardBackground />
      {/* Main Sidebar */}
      {!hideSidebar && <AppSidebar activeId={activeId} onDashboardHover={onDashboardHover} />}

      {/* Page Container */}
      <main
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          transition: 'padding-left 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Universal Header */}
        {!hideHeader && (
          <AppHeader
            title={title}
            subtitle={subtitle}
            badge={badge}
          >
            {headerActions}
          </AppHeader>
        )}

        {/* Page Content */}
        <main style={{
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}>
          {children}
        </main>
      </main>
    </div>
  );
}
