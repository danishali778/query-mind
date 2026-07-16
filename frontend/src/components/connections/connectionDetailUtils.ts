import type { CSSProperties } from 'react';

import { T } from '../dashboard/tokens';

export function timeAgo(dateStr: string) {
  const date = new Date(dateStr);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${Math.max(0, seconds)}S AGO`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}M AGO`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}H AGO`;
  return date.toLocaleDateString();
}

export function formatTimestamp(value?: string | null) {
  if (!value) return 'Never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

export function formatLatency(value?: number | null) {
  return value == null ? 'N/A' : `${Math.round(value)} ms`;
}

export const controlStyle: CSSProperties = { boxSizing: 'border-box', width: '100%', padding: '10px 12px', background: T.s2, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.fontMono };

export const secondaryButtonStyle: CSSProperties = { padding: '8px 14px', background: 'transparent', border: `1px solid ${T.border}`, color: T.text2, cursor: 'pointer', font: `800 .62rem ${T.fontMono}` };

export const primaryButtonStyle: CSSProperties = { padding: '9px 16px', background: T.accent, border: `1px solid ${T.accent}`, color: '#000', cursor: 'pointer', font: `900 .63rem ${T.fontMono}` };
