import { useCallback, useRef, useState } from 'react';
import { ResultsTable } from './ResultsTable';
import { BaseChartContainer } from '../charts/BaseChartContainer';
import { T } from '../dashboard/tokens';
import { Layout, Table2, X } from 'lucide-react';
import type { ChatResultsPanelProps } from '../../types/chat';

export function ResultsPanel({
    rows,
    columns,
    rowCount,
    truncated,
    executionTimeMs,
    chartRecommendation,
    onClose,
    panelHeight,
    onResize,
    column_metadata
}: ChatResultsPanelProps) {
    const [tabSelection, setTabSelection] = useState<{
        rows: ChatResultsPanelProps['rows'];
        chart: ChatResultsPanelProps['chartRecommendation'];
        tab: 'table' | 'chart';
    }>(() => ({
        rows,
        chart: chartRecommendation,
        tab: chartRecommendation ? 'chart' : 'table',
    }));
    const isDragging = useRef(false);
    const startY = useRef(0);
    const startHeight = useRef(0);

    const hasChart = chartRecommendation && (rows.length > 1 || chartRecommendation.type === 'kpi');
    const defaultTab = hasChart ? 'chart' : 'table';
    const activeTab = tabSelection.rows === rows && tabSelection.chart === chartRecommendation
        ? tabSelection.tab
        : defaultTab;
    const selectTab = (tab: 'table' | 'chart') => setTabSelection({ rows, chart: chartRecommendation, tab });

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        isDragging.current = true;
        startY.current = e.clientY;
        startHeight.current = panelHeight;
        document.body.style.cursor = 'row-resize';
        document.body.style.userSelect = 'none';

        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging.current) return;
            const diff = startY.current - e.clientY;
            const newHeight = Math.max(180, Math.min(window.innerHeight * 0.7, startHeight.current + diff));
            onResize(newHeight);
        };

        const handleMouseUp = () => {
            isDragging.current = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }, [panelHeight, onResize]);

    return (
        <div style={{
            height: panelHeight,
            borderTop: `1px solid ${T.border}`,
            background: T.s1,
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
            fontFamily: T.fontBody,
            boxShadow: '0 -8px 32px rgba(0,0,0,0.06)',
            zIndex: 100,
        }}>
            {/* Drag handle */}
            <div
                onMouseDown={handleMouseDown}
                style={{
                    height: 8,
                    background: T.bg,
                    cursor: 'row-resize',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    borderBottom: `1px solid ${T.border}`,
                }}
            >
                <div style={{
                    width: 48,
                    height: 4,
                    borderRadius: 2,
                    background: T.border2,
                    opacity: 0.6,
                    transition: 'background 0.15s',
                }} />
            </div>

            {/* Header bar */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 24px',
                borderBottom: `1px solid ${T.border}`,
                background: T.s1,
                flexShrink: 0,
            }}>
                {/* Left: tabs */}
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <button
                        onClick={() => selectTab('table')}
                        style={{
                            padding: '8px 16px',
                            borderRadius: 12,
                            fontSize: '0.8rem',
                            fontWeight: 700,
                            cursor: 'pointer',
                            border: 'none',
                            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                            background: activeTab === 'table' ? T.accentDim : 'transparent',
                            color: activeTab === 'table' ? T.accent : T.text3,
                            display: 'flex', alignItems: 'center', gap: 8,
                        }}
                    >
                        <Table2 size={14} />
                        Table
                        <span style={{
                            padding: '2px 8px',
                            borderRadius: 8,
                            fontSize: '0.7rem',
                            background: activeTab === 'table' ? 'rgba(14, 165, 233, 0.1)' : T.bg,
                            color: activeTab === 'table' ? T.accent : T.text3,
                            fontWeight: 700,
                            fontFamily: T.fontMono,
                        }}>
                            {rowCount}
                        </span>
                    </button>

                    {hasChart && (
                        <button
                            onClick={() => selectTab('chart')}
                            style={{
                                padding: '8px 16px',
                                borderRadius: 12,
                                fontSize: '0.8rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                border: 'none',
                                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                background: activeTab === 'chart' ? T.accentDim : 'transparent',
                                color: activeTab === 'chart' ? T.accent : T.text3,
                                display: 'flex', alignItems: 'center', gap: 8,
                            }}
                        >
                            <Layout size={14} />
                            Chart
                        </button>
                    )}
                </div>

                {/* Right: meta + close */}
                <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    {executionTimeMs !== undefined && executionTimeMs > 0 && (
                        <span style={{
                            fontSize: '0.7rem',
                            color: T.text3,
                            fontFamily: T.fontMono,
                            background: T.bg,
                            padding: '4px 8px',
                            borderRadius: 6,
                        }}>
                            ⚡ {executionTimeMs}ms
                        </span>
                    )}
                    <button
                        onClick={onClose}
                        style={{
                            width: 32,
                            height: 32,
                            borderRadius: 10,
                            border: `1px solid ${T.border}`,
                            background: T.s1,
                            color: T.text3,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'all 0.2s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.background = `${T.red}10`; e.currentTarget.style.color = T.red; e.currentTarget.style.borderColor = `${T.red}40`; }}
                        onMouseLeave={e => { e.currentTarget.style.background = T.s1; e.currentTarget.style.color = T.text3; e.currentTarget.style.borderColor = T.border; }}
                        title="Close panel"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Body */}
            <div style={{ flex: 1, overflowY: 'auto', overflowX: 'auto' }}>
                {activeTab === 'table' && (
                    <div style={{ padding: '0' }}>
                        <ResultsTable
                            columns={columns}
                            rows={rows}
                            rowCount={rowCount}
                            truncated={truncated}
                        />
                    </div>
                )}

                {activeTab === 'chart' && hasChart && (
                    <div style={{ padding: '0' }}>
                        <BaseChartContainer
                            recommendation={chartRecommendation!}
                            rows={rows}
                            columns={columns}
                            column_metadata={column_metadata}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
