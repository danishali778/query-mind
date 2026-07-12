import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, CircleStop, LoaderCircle, RotateCw } from 'lucide-react';
import { T } from '../dashboard/tokens';
import type { ChatRunEvent, ChatRunStatus } from '../../types/api';

const TERMINAL: ChatRunStatus[] = ['completed', 'failed', 'cancelled'];

export function AgentActivity({
  status,
  label,
  events = [],
  streamState,
  onStop,
}: {
  status: ChatRunStatus;
  label?: string;
  events?: ChatRunEvent[];
  streamState?: 'connecting' | 'connected' | 'reconnecting' | 'closed';
  onStop?: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const isTerminal = TERMINAL.includes(status);
  useEffect(() => {
    if (isTerminal) return;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [isTerminal]);

  const visibleEvents = useMemo(() => {
    const seen = new Set<string>();
    return events.filter(event => {
      if (!['stage.completed', 'tool.completed', 'run.fallback'].includes(event.type)) return false;
      const key = `${event.sequence ?? ''}:${event.type}:${event.stage ?? ''}:${event.label ?? ''}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [events]);

  const displayLabel = status === 'cancel_requested'
    ? 'Stopping response'
    : streamState === 'reconnecting'
      ? 'Reconnecting to live updates'
      : label || 'Preparing your request';

  return (
    <div style={{ border: `1px solid ${T.border}`, background: '#fff', padding: 16, width: '100%' }} aria-live="polite">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {status === 'completed' ? <Check size={18} color={T.green} /> : isTerminal ? <CircleStop size={18} color={status === 'failed' ? T.red : T.text3} /> : <LoaderCircle className="agent-activity-spinner" size={18} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: T.fontMono, fontSize: '0.72rem', fontWeight: 800, color: T.text }}>{displayLabel}</div>
          {!isTerminal && <div style={{ fontFamily: T.fontMono, fontSize: '0.62rem', color: T.text3, marginTop: 3 }}>{elapsed}s elapsed</div>}
        </div>
        {!isTerminal && onStop && (
          <button type="button" onClick={onStop} disabled={status === 'cancel_requested'} aria-label="Stop response" style={{ border: `1px solid ${T.border}`, background: '#fff', padding: '7px 10px', cursor: status === 'cancel_requested' ? 'default' : 'pointer', fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 800 }}>
            {status === 'cancel_requested' ? 'STOPPING' : 'STOP'}
          </button>
        )}
        {visibleEvents.length > 0 && (
          <button type="button" onClick={() => setExpanded(value => !value)} aria-label={expanded ? 'Hide agent activity' : 'Show agent activity'} style={{ border: 0, background: 'transparent', cursor: 'pointer', color: T.text3 }}>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        )}
      </div>
      {expanded && visibleEvents.length > 0 && (
        <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 14, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {visibleEvents.map((event, index) => (
            <div key={`${event.sequence ?? index}-${event.type}`} style={{ display: 'flex', alignItems: 'center', gap: 9, fontFamily: T.fontMono, fontSize: '0.66rem', color: T.text2 }}>
              {event.type === 'run.fallback' ? <RotateCw size={12} color={T.yellow} /> : <Check size={12} color={event.outcome === 'error' ? T.red : T.green} />}
              <span>{event.label || event.stage || event.type}</span>
              {typeof event.duration_ms === 'number' && <span style={{ marginLeft: 'auto', color: T.text3 }}>{Math.round(event.duration_ms)}ms</span>}
            </div>
          ))}
        </div>
      )}
      <style>{`@keyframes agentActivitySpin{to{transform:rotate(360deg)}} .agent-activity-spinner{animation:agentActivitySpin .9s linear infinite}@media(prefers-reduced-motion:reduce){.agent-activity-spinner{animation:none}}`}</style>
    </div>
  );
}
