/* QueryMind Design Tokens — Comprehensive Design System */
export const T = {
  // ============ COLORS ============

  // BACKGROUNDS (8 depth layers)
  bg: '#fcfaf7',        // Editorial Background (Warm Cream)
  s1: '#ffffff',        // Surface layer 1
  s2: '#f6f3ed',        // Surface layer 2
  s3: '#ece8e0',        // Surface layer 3
  s4: '#e0dbd0',        // Surface layer 4
  s5: '#d4cec0',        // Surface layer 5

  // ACCENT COLORS (Primary palette)
  accent: '#0ea5e9',    // Sky Blue
  accentDim: 'rgba(14, 165, 233, 0.08)',
  purple: '#6366f1',    // Indigo
  purpleDim: 'rgba(99, 102, 241, 0.08)',
  green: '#10b981',     // Emerald
  greenDim: 'rgba(16, 185, 129, 0.08)',
  yellow: '#f59e0b',    // Amber
  yellowDim: 'rgba(245, 158, 11, 0.08)',
  red: '#ef4444',       // Rose
  redDim: 'rgba(239, 68, 68, 0.08)',
  orange: '#f97316',    // Orange
  orangeDim: 'rgba(249, 115, 22, 0.08)',

  // TEXT COLORS (Editorial Hierarchy)
  text: '#1a1a1a',      // Primary text (Ink/Coal)
  text2: '#4a4a4a',     // Secondary text (Slate)
  text3: '#8a8a8a',     // Tertiary text (Muted)

  // BORDERS
  border: '#e2e8f0',    // Subtle border
  border2: '#cbd5e1',   // Standard border

  // STATUS COLORS
  statusOnline: '#22d3a5',    // Online/connected
  statusLoading: '#f59e0b',   // Loading/pending
  statusError: '#f87171',     // Error/offline
  statusWarning: '#f59e0b',   // Warning

  // ============ TYPOGRAPHY ============
  fontHead: "'Playfair Display', serif",    // Editorial Serif
  fontMono: "'DM Mono', monospace",         // Technical Mono
  fontBody: "'Inter', sans-serif",          // Clean Sans

  // ============ SPACING (8px base unit) ============
  space: {
    0: 0,
    1: 4,      // xs
    2: 8,      // sm
    3: 12,     // md
    4: 16,     // lg
    5: 20,     // xl
    6: 24,     // 2xl
    8: 32,     // 3xl
  },

  // ============ SIZING (Component heights) ============
  size: {
    xs: 28,    // Small button/input
    sm: 32,    // Medium button/input
    md: 40,    // Standard button/input
    lg: 48,    // Large button/input
    xl: 56,    // Extra large button
  },

  // ============ BORDER RADIUS ============
  radius: {
    sm: 8,     // Subtle rounding
    md: 12,    // Standard rounding
    lg: 16,    // Large rounding
    xl: 20,    // Extra large rounding
    full: 9999, // Fully rounded (pills)
  },

  // ============ SHADOWS ============
  shadow: {
    none: 'none',
    sm: '0 2px 8px rgba(0,0,0,0.03)',
    md: '0 4px 16px rgba(0,0,0,0.05)',
    lg: '0 12px 32px rgba(0,0,0,0.08)',
    xl: '0 20px 48px rgba(0,0,0,0.12)',
    glow: '0 0 20px rgba(14, 165, 233, 0.1)',
    glowIntense: '0 0 40px rgba(14, 165, 233, 0.15)',
    accent: '0 0 20px rgba(14, 165, 233, 0.15)',
    accentIntense: '0 0 40px rgba(14, 165, 233, 0.25)',
  },

  // ============ GLASSMORPHISM ============
  glass: {
    bg: 'rgba(255, 255, 255, 0.7)',
    bgDark: 'rgba(15, 23, 42, 0.8)',
    border: 'rgba(255, 255, 255, 0.1)',
    blur: 'blur(12px) saturate(180%)',
  },

  // ============ TRANSITIONS ============
  transition: '180ms cubic-bezier(0.4, 0, 0.2, 1)',
  transitionShort: '100ms cubic-bezier(0.4, 0, 0.2, 1)',
  transitionLong: '300ms cubic-bezier(0.4, 0, 0.2, 1)',

  // ============ ANIMATION SPRINGS (Framer Motion) ============
  spring: {
    gentle: { type: 'spring' as const, stiffness: 100, damping: 20 },
    bouncy: { type: 'spring' as const, stiffness: 300, damping: 15 },
    stiff: { type: 'spring' as const, stiffness: 500, damping: 30 },
  },

  // ============ COMPONENT-SPECIFIC TOKENS ============

  // Button Tokens
  button: {
    padding: { sm: '6px 12px', md: '8px 16px', lg: '12px 20px' },
    fontSize: { sm: '0.875rem', md: '1rem', lg: '1.125rem' },
    fontWeight: 500,
  },

  // Card Tokens
  card: {
    padding: 20,
    gap: 16,
    borderRadius: 12,
    shadow: 'rgba(0,0,0,0.3)',
  },

  // Badge Tokens
  badge: {
    height: 24,
    padding: '4px 8px',
    fontSize: '0.75rem',
    borderRadius: 6,
  },

  // Input Tokens
  input: {
    height: 40,
    padding: '10px 14px',
    fontSize: '0.9375rem',
    borderRadius: 8,
  },

  // Status Indicator
  statusIndicator: {
    size: 12,
    animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
  },
} as const;
