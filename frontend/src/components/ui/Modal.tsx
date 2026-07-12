import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: string | number;
}

export function Modal({ isOpen, onClose, children, width = 440 }: ModalProps) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let visibilityTimer: ReturnType<typeof setTimeout> | undefined;
    let unmountTimer: ReturnType<typeof setTimeout> | undefined;
    let animationFrame: number | undefined;
    if (isOpen) {
      visibilityTimer = setTimeout(() => {
        setMounted(true);
        animationFrame = requestAnimationFrame(() => setVisible(true));
      }, 0);
    } else {
      visibilityTimer = setTimeout(() => setVisible(false), 0);
      unmountTimer = setTimeout(() => setMounted(false), 300);
    }
    return () => {
      if (visibilityTimer) clearTimeout(visibilityTimer);
      if (unmountTimer) clearTimeout(unmountTimer);
      if (animationFrame) cancelAnimationFrame(animationFrame);
    };
  }, [isOpen]);

  if (!mounted) return null;

  return createPortal(
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
      style={{ backdropFilter: visible ? 'blur(12px) saturate(1.2)' : 'blur(0) saturate(1)', backgroundColor: 'rgba(2, 6, 12, 0.7)' }}
      onClick={onClose}
    >
      <div 
        className={`relative w-full overflow-hidden rounded-2xl border border-white/10 shadow-2xl transition-all duration-300 transform ${visible ? 'scale-100 translate-y-0 opacity-100' : 'scale-95 translate-y-4 opacity-0'}`}
        style={{ 
          maxWidth: width, 
          background: 'linear-gradient(135deg, rgba(13, 20, 32, 0.95), rgba(11, 17, 32, 0.98))',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(0, 229, 255, 0.05)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Animated accent bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-linear-to-r from-cyan-400 via-indigo-500 to-emerald-400 opacity-60" />
        
        <div className="p-1">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
