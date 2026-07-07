import { useState } from 'react';
import { T } from './tokens';

interface DashboardFilterBarProps {
  filters: Record<string, any>;
  onFiltersChange: (filters: Record<string, any>) => void;
  onApply: () => void;
}

export function DashboardFilterBar({ filters, onFiltersChange, onApply }: DashboardFilterBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const setFilter = (key: string, value: any) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const removeFilter = (key: string) => {
    const newFilters = { ...filters };
    delete newFilters[key];
    onFiltersChange(newFilters);
  };

  const hasFilters = Object.keys(filters).length > 0;

  return (
    <div className="dash-filter-glass" style={{
      background: '#fff',
      border: `1px solid rgba(0, 0, 0, 0.08)`,
      borderRadius: 0,
      padding: '14px 20px',
      marginBottom: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      boxShadow: 'none',
      position: 'relative'
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        pointerEvents: 'none'
      }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(99, 102, 241, 0.1))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.9rem', color: T.accent,
            border: '1px solid rgba(14, 165, 233, 0.15)',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
            </svg>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ 
              fontFamily: T.fontHead, fontWeight: 800, fontSize: '0.9rem',
              color: T.text, letterSpacing: '-0.01em'
            }}>
              Runtime Filters
            </span>
            <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, opacity: 0.7 }}>
              GLOBAL DATA CONSTRAINTS
            </span>
          </div>

          {hasFilters && (
            <div style={{
              background: 'rgba(14, 165, 233, 0.1)', color: T.accent, fontSize: '0.65rem',
              fontWeight: 800, padding: '3px 10px', borderRadius: 20,
              fontFamily: T.fontMono, border: '1px solid rgba(14, 165, 233, 0.2)',
              marginLeft: 4, letterSpacing: '0.05em'
            }}>
              {Object.keys(filters).length} ACTIVE
            </div>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
              background: 'rgba(15, 23, 42, 0.03)', 
              border: '1px solid rgba(15, 23, 42, 0.05)', 
              borderRadius: 8,
              color: T.text2,
              fontSize: '0.7rem', cursor: 'pointer', fontFamily: T.fontMono,
              padding: '6px 12px', fontWeight: 600,
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(15, 23, 42, 0.06)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(15, 23, 42, 0.03)'}
          >
            {isExpanded ? 'COLLAPSE' : 'EDIT FILTERS'}
          </button>
          
          <button 
            onClick={onApply}
            style={{
              background: 'linear-gradient(135deg, #0ea5e9, #6366f1)',
              border: 'none', borderRadius: 10, padding: '8px 20px',
              color: 'white', fontWeight: 700, fontSize: '0.8rem',
              cursor: 'pointer', 
              boxShadow: '0 4px 15px rgba(14, 165, 233, 0.25)',
              transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = 'scale(1.04)';
              e.currentTarget.style.boxShadow = '0 6px 20px rgba(14, 165, 233, 0.35)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.boxShadow = '0 4px 15px rgba(14, 165, 233, 0.25)';
            }}
          >
            Apply Changes
          </button>
        </div>
      </div>

      {isExpanded && (
        <div style={{ 
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 16, paddingTop: 20, borderTop: `1px solid rgba(0,0,0,0.06)`
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.62rem', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, fontWeight: 700 }}>
              Date Range
            </label>
            <select 
              value={filters.date_range || '30'}
              onChange={(e) => setFilter('date_range', e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.5)', border: `1px solid rgba(0,0,0,0.08)`, borderRadius: 10,
                padding: '10px 14px', color: T.text, fontSize: '0.82rem', outline: 'none',
                fontFamily: T.fontBody, appearance: 'none',
              }}
            >
              <option value="7">Last 7 Days</option>
              <option value="30">Last 30 Days</option>
              <option value="90">Last 90 Days</option>
              <option value="all">All Time</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.62rem', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, fontWeight: 700 }}>
              Status Filter
            </label>
            <input 
              placeholder="e.g. active, completed"
              value={filters.status || ''}
              onChange={(e) => setFilter('status', e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.5)', border: `1px solid rgba(0,0,0,0.08)`, borderRadius: 10,
                padding: '10px 14px', color: T.text, fontSize: '0.82rem', outline: 'none',
                fontFamily: T.fontBody,
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.62rem', color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, fontWeight: 700 }}>
              Row Limit
            </label>
            <input 
              type="number"
              placeholder="100"
              value={filters.limit || ''}
              onChange={(e) => setFilter('limit', e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.5)', border: `1px solid rgba(0,0,0,0.08)`, borderRadius: 10,
                padding: '10px 14px', color: T.text, fontSize: '0.82rem', outline: 'none',
                fontFamily: T.fontBody,
              }}
            />
          </div>
        </div>
      )}

      {hasFilters && !isExpanded && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', paddingTop: 4 }}>
          {Object.entries(filters).map(([key, value]) => (
            <div key={key} style={{
              background: 'rgba(255,255,255,0.8)', 
              border: `1px solid rgba(14, 165, 233, 0.15)`, 
              borderRadius: 8,
              padding: '4px 10px', fontSize: '0.72rem', color: T.text2,
              display: 'flex', alignItems: 'center', gap: 8,
              boxShadow: '0 2px 6px rgba(0,0,0,0.02)',
            }}>
              <span style={{ color: T.text3, textTransform: 'uppercase', fontSize: '0.6rem', fontWeight: 700 }}>{key}</span>
              <span style={{ color: T.accent, fontWeight: 700 }}>{String(value)}</span>
              <button 
                onClick={() => removeFilter(key)}
                style={{ 
                  background: 'rgba(239, 68, 68, 0.1)', border: 'none', 
                  color: T.red, cursor: 'pointer', padding: '2px 5px',
                  borderRadius: 4, display: 'flex', alignItems: 'center',
                  fontSize: '0.8rem',
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
