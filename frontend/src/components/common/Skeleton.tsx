import type { CSSProperties } from 'react';
import { T } from '../dashboard/tokens';

interface SkeletonProps {
  /** Additional Tailwind classes for sizing/layout, e.g. "w-24 h-4" or "flex-1". */
  className?: string;
  style?: CSSProperties;
}

/**
 * Minimal pulsing placeholder block for content that hasn't loaded yet
 * (auth resolving, page data in flight, etc). Deliberately unopinionated
 * about size/shape — compose that via `className`/`style` at the call site,
 * matching the square-edged, editorial look used across the app.
 */
export function Skeleton({ className = '', style }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse ${className}`}
      style={{ background: T.s3, ...style }}
    />
  );
}
