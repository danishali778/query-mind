import type { ReactNode } from 'react';

export interface ChartTooltipEntry {
  color?: string;
  fill?: string;
  name?: string | number;
  value?: string | number | null;
  payload?: {
    fill?: string;
    __xLabel?: string;
    __series?: string;
    __color?: string;
  };
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: ChartTooltipEntry[];
  label?: ReactNode;
}
