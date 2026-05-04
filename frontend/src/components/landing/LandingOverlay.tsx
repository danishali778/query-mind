import React from 'react';

export const LandingOverlay: React.FC = () => {
  return (
    <>
      {/* The System Scanline */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '2px',
        background: 'rgba(14, 165, 233, 0.15)',
        zIndex: 9999,
        pointerEvents: 'none',
        boxShadow: '0 0 15px rgba(14, 165, 233, 0.4)',
        animation: 'scanline 8s linear infinite'
      }} />

      {/* Global Noise Filter */}
      <div style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9998,
        pointerEvents: 'none',
        opacity: 0.03,
        background: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
      }} />

      <style>{`
        @keyframes scanline {
          0% { transform: translateY(-100vh); }
          100% { transform: translateY(100vh); }
        }
      `}</style>
    </>
  );
};
