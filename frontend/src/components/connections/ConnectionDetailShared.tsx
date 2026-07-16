import type { ReactNode } from 'react';

import { T } from '../dashboard/tokens';
import { timeAgo } from './connectionDetailUtils';

export function InfoRow({ label, value, noBorder }: { label: string; value: ReactNode; noBorder?: boolean }) {
  return <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, padding: '10px 0', borderBottom: noBorder ? 'none' : `1px solid ${T.border}`, fontSize: '.68rem' }}>
    <span style={{ color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{label}</span>
    <span style={{ color: T.text2, fontFamily: T.fontMono, fontWeight: 700, textAlign: 'right', wordBreak: 'break-word' }}>{value}</span>
  </div>;
}

export function SummaryCard({ value, label, detail, color = T.accent }: { value: string; label: string; detail: string; color?: string }) {
  return <div style={{ position: 'relative', padding: '20px 22px', background: T.s1, border: `1px solid ${T.border}` }}>
    <div style={{ position: 'absolute', inset: '0 auto 0 0', width: 2, background: color }} />
    <div style={{ color, font: `900 1.45rem ${T.fontHead}`, marginBottom: 5 }}>{value}</div>
    <div style={{ color: T.text, font: `800 .63rem ${T.fontMono}`, letterSpacing: 1 }}>{label}</div>
    <div style={{ color: T.text3, font: `600 .61rem ${T.fontMono}`, marginTop: 5 }}>{detail}</div>
  </div>;
}

export function SectionCard({ title, badge, action, children }: { title: string; badge?: string; action?: ReactNode; children: ReactNode }) {
  return <section style={{ overflow: 'hidden', background: T.s1, border: `1px solid ${T.border}` }}>
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '13px 18px', background: T.s2, borderBottom: `1px solid ${T.border}` }}>
      <span style={{ color: T.text, font: `800 .68rem ${T.fontMono}`, letterSpacing: 1 }}>{title}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {badge && <span style={{ color: T.accent, font: `800 .58rem ${T.fontMono}` }}>{badge}</span>}
        {action}
      </div>
    </header>
    {children}
  </section>;
}

export function StateBlock({ title, body, actionLabel, onAction, tone = 'neutral' }: { title: string; body: string; actionLabel?: string; onAction?: () => Promise<void> | void; tone?: 'neutral' | 'error' }) {
  const color = tone === 'error' ? T.red : T.text3;
  return <div style={{ padding: '34px 24px', textAlign: 'center', background: tone === 'error' ? T.redDim : T.s1, border: `1px solid ${tone === 'error' ? T.red : T.border}`, fontFamily: T.fontMono }}>
    <div style={{ color, fontSize: '.72rem', fontWeight: 900, letterSpacing: 1, marginBottom: 10 }}>{title}</div>
    <div style={{ color: T.text3, fontSize: '.68rem', lineHeight: 1.7 }}>{body}</div>
    {actionLabel && onAction && <button onClick={onAction} style={{ marginTop: 18, padding: '8px 16px', border: `1px solid ${color}`, background: 'transparent', color, font: `900 .62rem ${T.fontMono}`, cursor: 'pointer' }}>{actionLabel}</button>}
  </div>;
}

export function ActivityRow({ success, query, duration, timestamp }: { success: boolean; query: string; duration: string; timestamp: string }) {
  return <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 18px', borderBottom: `1px solid ${T.border}` }}>
    <span aria-label={success ? 'Successful query' : 'Failed query'} style={{ width: 8, height: 8, flexShrink: 0, background: success ? T.green : T.red }} />
    <span style={{ minWidth: 0, flex: 1, overflow: 'hidden', color: success ? T.text2 : T.red, font: `600 .7rem ${T.fontMono}`, textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{query}</span>
    <span style={{ color: success ? T.green : T.red, font: `700 .61rem ${T.fontMono}` }}>{duration}</span>
    <span style={{ color: T.text3, font: `600 .61rem ${T.fontMono}` }}>{timeAgo(timestamp)}</span>
  </div>;
}

export function Accordion({ id, title, description, open, onToggle, children }: { id: string; title: string; description: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  return <section style={{ background: T.s1, border: `1px solid ${T.border}` }}>
    <button type="button" aria-expanded={open} aria-controls={`${id}-panel`} onClick={onToggle} style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 16, padding: '16px 18px', textAlign: 'left', background: 'transparent', border: 0, color: T.text, cursor: 'pointer' }}>
      <span><strong style={{ display: 'block', font: `800 .68rem ${T.fontMono}`, letterSpacing: 1 }}>{title}</strong><span style={{ display: 'block', color: T.text3, font: `500 .63rem/1.5 ${T.fontMono}`, marginTop: 5 }}>{description}</span></span>
      <span aria-hidden="true" style={{ color: T.accent, fontFamily: T.fontMono }}>{open ? '−' : '+'}</span>
    </button>
    {open && <div id={`${id}-panel`} style={{ padding: '0 18px 18px', borderTop: `1px solid ${T.border}` }}>{children}</div>}
  </section>;
}
