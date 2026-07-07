import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AppSidebar } from './AppSidebar';
import { AppHeader } from './AppHeader';
import { T } from '../dashboard/tokens';
import { DashboardBackground } from '../layout/DashboardBackground';
import { BREAKPOINTS, useMediaQuery } from '../../hooks/useMediaQuery';

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
  const isMobileNav = useMediaQuery(BREAKPOINTS.lg);
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.style.overflow = navOpen && isMobileNav ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [navOpen, isMobileNav]);

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100%',
      maxWidth: '100vw',
      overflow: 'hidden',
      background: 'transparent',
      fontFamily: T.fontBody,
      color: T.text,
      position: 'relative'
    }}>
      <DashboardBackground />
      {isMobileNav && navOpen && !hideSidebar && (
        <button
          type="button"
          className="app-shell-backdrop"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      )}

      {!hideSidebar && (
        <AppSidebar
          activeId={activeId}
          onDashboardHover={onDashboardHover}
          className={navOpen ? 'app-sidebar app-sidebar--open' : 'app-sidebar'}
          onNavigate={() => setNavOpen(false)}
        />
      )}

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
        {!hideHeader && (
          <AppHeader
            title={title}
            subtitle={subtitle}
            badge={badge}
            onMenuClick={() => setNavOpen(true)}
            showMenuButton={isMobileNav && !hideSidebar}
          >
            {headerActions}
          </AppHeader>
        )}

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
