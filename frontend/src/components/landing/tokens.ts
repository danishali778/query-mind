/**
 * Landing-page tokens.
 *
 * Colors are derived from the app palette in `components/dashboard/tokens.ts` —
 * the landing page must not introduce a second color scheme. What lives here is
 * only the landing-specific surface treatment: gradient ramps for each accent,
 * the raised/inset shadow recipes, and the display typography.
 */
import { T } from '../dashboard/tokens';

/** A light→deep ramp around one of the app's accent colors. */
export type AccentRamp = {
  light: string;
  base: string;
  deep: string;
};

/** Gradient ramps built from the app accents (sky / indigo / emerald). */
const ramp: Record<'sky' | 'indigo' | 'emerald', AccentRamp> = {
  sky: { light: '#38bdf8', base: T.accent, deep: '#0284c7' },
  indigo: { light: '#818cf8', base: T.purple, deep: '#4f46e5' },
  emerald: { light: '#34d399', base: T.green, deep: '#059669' },
};

export const L = {
  // ---- Palette (app scheme) ----
  bg: T.bg,
  surface: T.s1,
  surfaceSunken: T.s2,
  border: T.border,
  text: T.text,
  text2: T.text2,
  text3: T.text3,

  sky: ramp.sky,
  indigo: ramp.indigo,
  emerald: ramp.emerald,

  /** Dark panel used behind SQL — treated as an inset object, not a data surface. */
  code: {
    bg: '#171a24',
    text: '#d7dbe6',
    keyword: '#7dd3fc',
    fn: '#a5b4fc',
    literal: '#fbbf24',
    ok: '#34d399',
  },

  // ---- Typography ----
  fontDisplay: "'Bricolage Grotesque', 'Inter', sans-serif",
  fontSerif: "'Instrument Serif', Georgia, serif",
  fontBody: "'Manrope', 'Inter', sans-serif",
  fontMono: "'JetBrains Mono', 'DM Mono', monospace",

  // ---- Depth recipes (single top light source) ----
  /** Raised surface: white, top highlight, soft shadow below. */
  raised:
    'inset 0 1px 1px rgba(255,255,255,0.9), 0 4px 12px rgba(28,34,58,0.07)',
  raisedLg:
    'inset 0 1px 1px rgba(255,255,255,0.9), 0 12px 30px rgba(28,34,58,0.09)',
  raisedHover:
    'inset 0 1px 1px rgba(255,255,255,0.9), 0 20px 40px rgba(28,34,58,0.13)',
  /** Floating hero card — the one place depth goes deep. */
  float:
    '0 2px 4px rgba(28,34,58,0.06), 0 30px 70px rgba(28,34,58,0.14)',
  /** Recessed well: darker fill + inner top shadow. */
  inset: 'inset 0 2px 5px rgba(28,34,58,0.08), inset 0 -1px 0 rgba(255,255,255,0.9)',
  insetDark: 'inset 0 2px 8px rgba(0,0,0,0.4)',

  ease: 'cubic-bezier(0.2, 0.7, 0.3, 1)',
} as const;

/** Gradient fill + matching glow for a colored control or icon tile. */
export function gradient(c: AccentRamp) {
  return `linear-gradient(150deg, ${c.light}, ${c.deep})`;
}

export function glow(hex: string, alpha = 0.35) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Raised shadow for an accent-filled control (highlight + colored glow). */
export function raisedAccent(c: AccentRamp, strength = 0.4) {
  return `inset 0 1px 1.5px rgba(255,255,255,0.5), 0 6px 16px ${glow(c.base, strength)}`;
}
