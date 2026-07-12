import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { T } from '../dashboard/tokens';
import type { SchemaTable } from '../../types/api';

interface ErdDiagramProps {
  tables: SchemaTable[];
}

const TABLE_WIDTH = 220;
const HEADER_H = 32;
const ROW_H = 22;
const GAP_X = 120;
const GAP_Y = 80;
const COLS = 3;

function getTableHeight(table: SchemaTable) {
  return HEADER_H + table.columns.length * ROW_H + 4;
}

function computeLayout(tables: SchemaTable[]): Record<string, { x: number; y: number }> {
  // Sort: tables with most foreign key references (from other tables) first — they're central
  const refCount: Record<string, number> = {};
  for (const t of tables) {
    for (const fk of t.foreign_keys) {
      refCount[fk.referred_table] = (refCount[fk.referred_table] || 0) + 1;
    }
  }
  const sorted = [...tables].sort((a, b) => (refCount[b.name] || 0) - (refCount[a.name] || 0));

  const positions: Record<string, { x: number; y: number }> = {};
  let rowMaxH = 0;
  let x = 40;
  let y = 40;
  let col = 0;

  for (const t of sorted) {
    const h = getTableHeight(t);
    positions[t.name] = { x, y };
    rowMaxH = Math.max(rowMaxH, h);
    col++;
    if (col >= COLS) {
      col = 0;
      x = 40;
      y += rowMaxH + GAP_Y;
      rowMaxH = 0;
    } else {
      x += TABLE_WIDTH + GAP_X;
    }
  }
  return positions;
}

interface Relationship {
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
}

function getRelationships(tables: SchemaTable[]): Relationship[] {
  const rels: Relationship[] = [];
  for (const t of tables) {
    for (const fk of t.foreign_keys) {
      rels.push({
        fromTable: t.name,
        fromColumn: fk.column,
        toTable: fk.referred_table,
        toColumn: fk.referred_column,
      });
    }
  }
  return rels;
}

function getColumnY(table: SchemaTable, colName: string): number {
  const idx = table.columns.findIndex(c => c.name === colName);
  return HEADER_H + (idx >= 0 ? idx : 0) * ROW_H + ROW_H / 2;
}

export function ErdDiagram({ tables }: ErdDiagramProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const initialPositions = useMemo(() => computeLayout(tables), [tables]);
  const relationships = useMemo(() => getRelationships(tables), [tables]);
  const tableMap = useMemo(() => {
    const m: Record<string, SchemaTable> = {};
    for (const t of tables) m[t.name] = t;
    return m;
  }, [tables]);

  const [positions, setPositions] = useState(initialPositions);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [scale, setScale] = useState(1);
  const [dragging, setDragging] = useState<string | null>(null);
  const [panning, setPanning] = useState(false);
  const [hoveredTable, setHoveredTable] = useState<string | null>(null);
  const dragStart = useRef({ x: 0, y: 0 });
  const panStart = useRef({ x: 0, y: 0, ox: 0, oy: 0 });

  // Reset positions when tables change
  useEffect(() => {
    setPositions(computeLayout(tables));
  }, [tables]);

  // Fit to view on mount
  useEffect(() => {
    if (!containerRef.current || tables.length === 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const allPos = Object.values(initialPositions);
    const maxX = Math.max(...allPos.map(p => p.x)) + TABLE_WIDTH + 40;
    const maxY = Math.max(...allPos.map(p => p.y)) + 200;
    const s = Math.min(rect.width / maxX, rect.height / maxY, 1);
    setScale(Math.max(s, 0.4));
  }, [initialPositions, tables]);

  const handleMouseDown = useCallback((e: React.MouseEvent, tableName?: string) => {
    if (tableName) {
      setDragging(tableName);
      dragStart.current = { x: e.clientX - positions[tableName].x * scale, y: e.clientY - positions[tableName].y * scale };
      e.stopPropagation();
    } else {
      setPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
    }
  }, [positions, scale, offset]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging) {
      setPositions(prev => ({
        ...prev,
        [dragging]: {
          x: (e.clientX - dragStart.current.x) / scale,
          y: (e.clientY - dragStart.current.y) / scale,
        },
      }));
    } else if (panning) {
      setOffset({
        x: panStart.current.ox + (e.clientX - panStart.current.x),
        y: panStart.current.oy + (e.clientY - panStart.current.y),
      });
    }
  }, [dragging, panning, scale]);

  const handleMouseUp = useCallback(() => {
    setDragging(null);
    setPanning(false);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale(prev => Math.min(2, Math.max(0.3, prev - e.deltaY * 0.001)));
  }, []);

  // Build FK relationship paths
  const renderRelationships = () => {
    return relationships.map((rel, i) => {
      const fromPos = positions[rel.fromTable];
      const toPos = positions[rel.toTable];
      if (!fromPos || !toPos || !tableMap[rel.fromTable] || !tableMap[rel.toTable]) return null;

      const fromY = fromPos.y + getColumnY(tableMap[rel.fromTable], rel.fromColumn);
      const toY = toPos.y + getColumnY(tableMap[rel.toTable], rel.toColumn);

      // Determine which sides to connect
      const fromCenterX = fromPos.x + TABLE_WIDTH / 2;
      const toCenterX = toPos.x + TABLE_WIDTH / 2;
      let sx: number, ex: number;

      if (fromCenterX <= toCenterX) {
        sx = fromPos.x + TABLE_WIDTH;
        ex = toPos.x;
      } else {
        sx = fromPos.x;
        ex = toPos.x + TABLE_WIDTH;
      }
      const sy = fromY;
      const ey = toY;

      const dx = Math.abs(ex - sx) * 0.5;
      const path = `M ${sx} ${sy} C ${sx + (ex > sx ? dx : -dx)} ${sy}, ${ex + (ex > sx ? -dx : dx)} ${ey}, ${ex} ${ey}`;

      const isHighlighted = hoveredTable === rel.fromTable || hoveredTable === rel.toTable;

      return (
        <g key={i}>
          <path
            d={path}
            fill="none"
            stroke={isHighlighted ? T.accent : T.purple}
            strokeWidth={isHighlighted ? 2 : 1.2}
            strokeDasharray={isHighlighted ? 'none' : '6 3'}
            opacity={isHighlighted ? 0.9 : 0.4}
            style={{ transition: 'opacity 0.2s, stroke-width 0.2s' }}
          />
          {/* Cardinality labels */}
          <text x={sx + (ex > sx ? 8 : -8)} y={sy - 6} fill={T.text3} fontSize="9" fontFamily={T.fontMono} textAnchor={ex > sx ? 'start' : 'end'}>n</text>
          <text x={ex + (ex > sx ? -8 : 8)} y={ey - 6} fill={T.text3} fontSize="9" fontFamily={T.fontMono} textAnchor={ex > sx ? 'end' : 'start'}>1</text>
          {/* Arrow at target */}
          <circle cx={ex} cy={ey} r={3} fill={isHighlighted ? T.accent : T.purple} opacity={isHighlighted ? 0.9 : 0.5} />
        </g>
      );
    });
  };

  const renderTable = (table: SchemaTable) => {
    const pos = positions[table.name];
    if (!pos) return null;
    const h = getTableHeight(table);
    const isHovered = hoveredTable === table.name;
    const fkCols = new Set(table.foreign_keys.map(fk => fk.column));

    return (
      <g
        key={table.name}
        transform={`translate(${pos.x}, ${pos.y})`}
        onMouseEnter={() => setHoveredTable(table.name)}
        onMouseLeave={() => setHoveredTable(null)}
        style={{ cursor: dragging === table.name ? 'grabbing' : 'grab' }}
      >
        {/* Shadow */}
        <rect x={2} y={2} width={TABLE_WIDTH} height={h} rx={8} ry={8} fill="rgba(0,0,0,0.3)" />
        {/* Body */}
        <rect
          width={TABLE_WIDTH} height={h} rx={8} ry={8}
          fill={T.s1}
          stroke={isHovered ? T.accent : T.border2}
          strokeWidth={isHovered ? 1.5 : 1}
          style={{ transition: 'stroke 0.2s' }}
        />
        {/* Header */}
        <rect width={TABLE_WIDTH} height={HEADER_H} rx={8} ry={8} fill={T.s2} />
        <rect y={HEADER_H - 8} width={TABLE_WIDTH} height={8} fill={T.s2} />
        <line x1={0} y1={HEADER_H} x2={TABLE_WIDTH} y2={HEADER_H} stroke={T.border2} strokeWidth={1} />
        {/* Header text + drag handle */}
        <rect
          width={TABLE_WIDTH} height={HEADER_H} rx={8} ry={8}
          fill="transparent"
          onMouseDown={e => handleMouseDown(e, table.name)}
          style={{ cursor: dragging === table.name ? 'grabbing' : 'grab' }}
        />
        <text x={12} y={HEADER_H / 2 + 1} fill={T.accent} fontSize="12" fontWeight="700" fontFamily={T.fontHead} dominantBaseline="middle">
          {table.name}
        </text>
        <text x={TABLE_WIDTH - 10} y={HEADER_H / 2 + 1} fill={T.text3} fontSize="9" fontFamily={T.fontMono} dominantBaseline="middle" textAnchor="end">
          {table.row_count != null ? `${table.row_count.toLocaleString()} rows` : ''}
        </text>

        {/* Columns */}
        {table.columns.map((col, ci) => {
          const cy = HEADER_H + ci * ROW_H;
          const isPk = col.primary_key;
          const isFk = fkCols.has(col.name);
          const colType = col.type.split('(')[0].toUpperCase();

          return (
            <g key={col.name} transform={`translate(0, ${cy})`}>
              {/* Row hover bg */}
              <rect x={1} y={1} width={TABLE_WIDTH - 2} height={ROW_H - 1} fill="transparent" rx={2} />
              {/* PK/FK badge */}
              {isPk && (
                <rect x={8} y={4} width={18} height={14} rx={3} fill="rgba(245,158,11,0.15)" stroke="rgba(245,158,11,0.3)" strokeWidth={0.5} />
              )}
              {isPk && (
                <text x={17} y={13} fill={T.yellow} fontSize="7.5" fontFamily={T.fontMono} fontWeight="600" textAnchor="middle">PK</text>
              )}
              {isFk && !isPk && (
                <rect x={8} y={4} width={18} height={14} rx={3} fill="rgba(124,58,255,0.15)" stroke="rgba(124,58,255,0.3)" strokeWidth={0.5} />
              )}
              {isFk && !isPk && (
                <text x={17} y={13} fill={T.purple} fontSize="7.5" fontFamily={T.fontMono} fontWeight="600" textAnchor="middle">FK</text>
              )}
              {/* Column name */}
              <text x={isPk || isFk ? 32 : 12} y={13} fill={isPk ? T.yellow : isFk ? T.purple : T.text2} fontSize="10.5" fontFamily={T.fontMono} dominantBaseline="middle">
                {col.name}
              </text>
              {/* Column type */}
              <text x={TABLE_WIDTH - 10} y={13} fill={T.text3} fontSize="9" fontFamily={T.fontMono} textAnchor="end" dominantBaseline="middle">
                {colType}
              </text>
            </g>
          );
        })}
      </g>
    );
  };

  if (tables.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400, color: T.text3, fontSize: '0.82rem' }}>
        No tables found — connect a database first
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', minHeight: 500, background: T.bg, borderRadius: 12, overflow: 'hidden', border: `1px solid ${T.border}` }}>
      {/* Zoom controls */}
      <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10, display: 'flex', gap: 4 }}>
        <button onClick={() => setScale(s => Math.min(2, s + 0.15))} style={zoomBtnStyle}>+</button>
        <button onClick={() => setScale(s => Math.max(0.3, s - 0.15))} style={zoomBtnStyle}>−</button>
        <button onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }} style={zoomBtnStyle}>⊡</button>
      </div>
      {/* Scale indicator */}
      <div style={{ position: 'absolute', bottom: 10, left: 12, zIndex: 10, fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, background: T.s2, padding: '2px 6px', borderRadius: 4 }}>
        {Math.round(scale * 100)}%
      </div>
      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 10, right: 12, zIndex: 10, display: 'flex', gap: 12, fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, background: T.s2, padding: '4px 10px', borderRadius: 4 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: 'rgba(245,158,11,0.3)' }} />PK</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: 'rgba(124,58,255,0.3)' }} />FK</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ display: 'inline-block', width: 16, height: 2, background: T.purple, opacity: 0.5 }} />Relationship</span>
      </div>

      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        style={{ cursor: panning ? 'grabbing' : 'default' }}
        onMouseDown={e => handleMouseDown(e)}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        {/* Grid pattern */}
        <defs>
          <pattern id="erd-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.5" fill={T.text3} opacity="0.15" />
          </pattern>
        </defs>
        <rect width="10000" height="10000" fill="url(#erd-grid)" />

        <g transform={`translate(${offset.x}, ${offset.y}) scale(${scale})`}>
          {renderRelationships()}
          {tables.map(t => renderTable(t))}
        </g>
      </svg>
    </div>
  );
}

const zoomBtnStyle: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.s2, color: T.text2, fontSize: '0.85rem', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontFamily: T.fontMono,
};
