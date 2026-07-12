import type { ReactNode } from 'react';

export interface ChartTooltipEntry {
  color?: string;
  fill?: string;
  name?: string | number;
  value?: string | number;
  payload?: {
    fill?: string;
  };
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: ChartTooltipEntry[];
  label?: ReactNode;
}
