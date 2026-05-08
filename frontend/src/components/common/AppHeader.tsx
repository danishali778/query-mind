import React from 'react';
import { T } from '../dashboard/tokens';

interface AppHeaderProps {
  title: string | React.ReactNode;
  subtitle?: string;
  badge?: {
    text: string;
    color: string;
    icon?: React.ReactNode;
  };
  children?: React.ReactNode; // For page-specific actions/filters
}

export function AppHeader({ title, children }: AppHeaderProps) {
  return (
    <header style={{
      height: 64,
      flexShrink: 0,
      background: T.bg,
      borderBottom: `1px solid rgba(0, 0, 0, 0.1)`,
      display: 'flex',
      alignItems: 'center',
      padding: '0 32px',
      gap: 20,
      zIndex: 50,
      position: 'relative'
    }}>
      {/* Left: Editorial Breadcrumbs */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 12, 
        flex: 1, 
        fontFamily: T.fontMono,
        fontSize: '0.68rem',
        letterSpacing: '0.15em',
        color: T.text3,
        textTransform: 'uppercase'
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
        
        <span>Workspace</span>
        <span style={{ opacity: 0.3 }}>/</span>
        <span>Operations</span>
        <span style={{ opacity: 0.3 }}>/</span>
        <span style={{ 
          fontFamily: T.fontHead, 
          color: T.text, 
          letterSpacing: '0.05em',
          fontWeight: 700,
          fontSize: '0.85rem',
          textTransform: 'none'
        }}>
          {typeof title === 'string' ? title : 'Dashboard'}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, marginLeft: 'auto' }}>
        {children}
      </div>
    </header>
  );
}

// Reusable Icon components for Header Actions
// eslint-disable-next-line react-refresh/only-export-components
export const HeaderIcons = {
  Share: (props: React.SVGProps<SVGSVGElement>) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <polyline points="16 6 12 2 8 6" />
      <line x1="12" y1="2" x2="12" y2="15" />
    </svg>
  ),
  Download: (props: React.SVGProps<SVGSVGElement>) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  ),
  Search: (props: React.SVGProps<SVGSVGElement>) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  Plus: (props: React.SVGProps<SVGSVGElement>) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
};
