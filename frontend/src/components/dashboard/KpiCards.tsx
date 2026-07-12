import { useState } from 'react';
import { motion } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { Database, Zap, Clock, Link as LinkIcon, TrendingUp, TrendingDown } from 'lucide-react';
import { T } from './tokens';

interface OverviewKpiItem {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  trend: string;
  up: boolean;
  color: string;
  dimColor: string;
  subColor?: string;
  spark?: string;
}

const FALLBACK_KPIS: OverviewKpiItem[] = [
  {
    icon: <Database size={16} />,
    label: 'Saved Queries',
    value: '124',
    sub: 'total library queries in the dashboard system',
    trend: '12.5%',
    up: true,
    color: T.accent,
    dimColor: T.accentDim,
    spark: 'M0,20 L10,18 L20,15 L30,16 L40,12 L50,10 L60,8 L70,6 L80,5 L90,3 L100,2',
  },
  {
    icon: <Zap size={16} />,
    label: 'Total Runs',
    value: '2.8k',
    sub: 'query executions (last 30 days of activity)',
    trend: '8.2%',
    up: true,
    color: T.purple,
    dimColor: T.purpleDim,
    spark: 'M0,22 L10,19 L20,20 L30,17 L40,15 L50,14 L60,12 L70,10 L80,8 L90,6 L100,4',
  },
  {
    icon: <Clock size={16} />,
    label: 'Scheduled Tasks',
    value: '42',
    sub: 'active cadences running in background',
    trend: '4.1%',
    up: true,
    color: T.yellow,
    dimColor: T.yellowDim,
    subColor: T.text3,
  },
  {
    icon: <LinkIcon size={16} />,
    label: 'Data Sources',
    value: '6',
    sub: 'active database connections connected',
    trend: 'Stable',
    up: true,
    color: T.green,
    dimColor: T.greenDim,
    spark: 'M0,18 L10,16 L20,17 L30,14 L40,15 L50,12 L60,11 L70,9 L80,8 L90,6 L100,5',
  },
];

interface KpiCardsProps {
  items?: OverviewKpiItem[];
}

function KpiCardItem({ kpi, index, variants }: { kpi: OverviewKpiItem; index: number; variants: Variants }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.div
      variants={variants}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ 
        y: -5,
        transition: T.spring.stiff
      }}
      style={{
        background: T.glass.bg,
        backdropFilter: T.glass.blur,
        WebkitBackdropFilter: T.glass.blur,
        border: `1px solid ${isHovered ? kpi.color + '40' : T.glass.border}`,
        borderRadius: T.radius.lg,
        padding: '20px',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: isHovered ? `0 12px 24px ${kpi.color}15` : T.shadow.md,
        cursor: 'default',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 200,
        zIndex: isHovered ? 10 : 1,
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
      }}
    >
      {/* Decorative Gradient Glow */}
      <div style={{ 
        position: 'absolute', 
        top: 0, 
        right: 0, 
        width: 120, 
        height: 120, 
        borderRadius: '50%', 
        background: `radial-gradient(circle, ${kpi.dimColor} 0%, transparent 70%)`, 
        transform: 'translate(40px, -40px)',
        opacity: 0.6,
        pointerEvents: 'none',
      }} />

      {/* Icon & Trend Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ 
          width: 38, 
          height: 38, 
          borderRadius: 12, 
          background: kpi.dimColor, 
          border: `1px solid ${kpi.color}20`,
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          color: kpi.color,
          boxShadow: `0 0 15px ${kpi.color}10`,
          flexShrink: 0,
        }}>
          {kpi.icon}
        </div>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 4, 
          fontSize: '0.7rem', 
          fontFamily: T.fontMono, 
          fontWeight: 600,
          padding: '4px 10px', 
          borderRadius: 20, 
          background: kpi.up ? T.greenDim : T.redDim, 
          color: kpi.up ? T.green : T.red,
          border: `1px solid ${kpi.up ? T.green : T.red}15`,
          flexShrink: 0,
        }}>
          {kpi.up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
          {kpi.trend}
        </div>
      </div>

      {/* Value Section */}
      <div style={{ 
        fontFamily: T.fontHead, 
        fontWeight: 800, 
        fontSize: '2rem', 
        letterSpacing: -1.2, 
        color: T.text, 
        lineHeight: 1, 
        marginBottom: 6,
        flexShrink: 0,
      }}>
        {kpi.value}
      </div>
      
      <div style={{ flex: 1 }}>
        <motion.div 
          layout
          style={{ 
            fontSize: '0.82rem', 
            fontWeight: 700,
            color: T.text,
            letterSpacing: -0.2,
            whiteSpace: isHovered ? 'normal' : 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.3,
          }}
        >
          {kpi.label}
        </motion.div>
        <motion.div 
          layout
          style={{ 
            fontSize: '0.68rem', 
            color: kpi.subColor || T.text3, 
            marginTop: 4, 
            fontFamily: T.fontMono,
            letterSpacing: 0.1,
            whiteSpace: isHovered ? 'normal' : 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            lineHeight: 1.4,
          }}
        >
          {kpi.sub}
        </motion.div>
      </div>

      {/* Sparkline Refinement */}
      {kpi.spark && (
        <motion.div layout style={{ marginTop: 16, position: 'relative' }}>
          <svg viewBox="0 0 100 24" style={{ width: '100%', height: 28, overflow: 'visible' }}>
            <defs>
              <linearGradient id={`sg${index}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={kpi.color} stopOpacity={0.2} />
                <stop offset="100%" stopColor={kpi.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <motion.path 
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, delay: 0.5 }}
              d={kpi.spark} 
              fill="none" 
              stroke={kpi.color} 
              strokeWidth={2} 
              strokeLinecap="round" 
              strokeLinejoin="round" 
            />
            <path 
              d={`${kpi.spark} L100,24 L0,24Z`} 
              fill={`url(#sg${index})`} 
              opacity={0.5}
            />
          </svg>
        </motion.div>
      )}
    </motion.div>
  );
}

export function KpiCards({ items = FALLBACK_KPIS }: KpiCardsProps) {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { 
      opacity: 1, 
      y: 0,
      transition: T.spring.gentle
    },
  };

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(4, 1fr)', 
        gap: 20, 
        marginBottom: 24 
      }}
    >
      {items.map((kpi, index) => (
        <KpiCardItem key={index} kpi={kpi} index={index} variants={cardVariants} />
      ))}
    </motion.div>
  );
}
