import { T } from '../dashboard/tokens';
import type { ChatResultsTableProps } from '../../types/chat';

function NullCell() {
  return (
    <span
      title="This field is empty in the database"
      style={{
        color: T.text3,
        fontStyle: 'italic',
        fontSize: '0.72rem',
        opacity: 0.6,
        cursor: 'help',
        userSelect: 'none',
      }}
    >
      -- no value --
    </span>
  );
}

export function ResultsTable({ columns, rows, rowCount, executionTime, truncated }: ChatResultsTableProps) {
  const isNull = (v: unknown) => v === null || v === undefined || v === '';

  const fmt = (v: unknown) => {
    if (typeof v === 'number') {
      return Number.isInteger(v)
        ? v.toLocaleString()
        : parseFloat(v.toFixed(2)).toLocaleString();
    }
    return String(v);
  };

  return (
    <div style={{ borderBottom: `1px solid ${T.border}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', background: T.s2 }}>
        <span style={{
          fontSize: '0.65rem', fontFamily: T.fontMono, fontWeight: 600, letterSpacing: 1,
          color: T.green, background: 'rgba(34,211,165,0.1)', border: '1px solid rgba(34,211,165,0.2)',
          padding: '2px 8px', borderRadius: 4,
        }}>RESULTS</span>
        <span style={{ fontSize: '0.72rem', color: T.text3, fontFamily: T.fontMono, flex: 1 }}>
          <span style={{ color: T.green }}>{rowCount ?? rows.length} rows</span>
          {executionTime != null && ` · ${(executionTime / 1000).toFixed(2)}s`}
          {truncated && ' · limited'}
        </span>

      </div>

      <div style={{ overflowX: 'auto', maxHeight: 200 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr>
              <th style={{
                background: T.s3, padding: '8px 16px', textAlign: 'left',
                fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 600,
                color: T.text3, letterSpacing: 0.5, textTransform: 'uppercase',
                borderBottom: `1px solid ${T.border}`, whiteSpace: 'nowrap',
                position: 'sticky', top: 0, zIndex: 2,
              }}>#</th>
              {columns.map(c => (
                <th key={c} style={{
                  background: T.s3, padding: '8px 16px', textAlign: 'left',
                  fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 600,
                  color: T.text3, letterSpacing: 0.5, textTransform: 'uppercase',
                  borderBottom: `1px solid ${T.border}`, whiteSpace: 'nowrap',
                  position: 'sticky', top: 0, zIndex: 2,
                }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={{ transition: 'background 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = i % 2 === 1 ? 'rgba(255,255,255,0.015)' : 'transparent'; }}
              >
                <td style={{ padding: '8px 16px', borderBottom: `1px solid ${T.border}`, fontFamily: T.fontMono, color: T.text3 }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 20, height: 20, borderRadius: 5, background: T.s4, color: T.text3,
                    fontSize: '0.65rem', fontWeight: 600,
                  }}>{i + 1}</span>
                </td>
                {columns.map(c => (
                  <td key={c} style={{
                    padding: '8px 16px', borderBottom: `1px solid ${T.border}`,
                    color: (typeof row[c] === 'number' || row[c] === '0') ? T.text : T.text2,
                    fontFamily: T.fontMono, whiteSpace: 'nowrap',
                    fontWeight: (typeof row[c] === 'number' || row[c] === '0') ? 600 : 400,
                  }}>{isNull(row[c]) ? <NullCell /> : fmt(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
