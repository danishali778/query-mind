import { useEffect, useState, useRef } from 'react';
import { T } from '../dashboard/tokens';
import type { ChatInputProps } from '../../types/chat';

export function ChatInput({ connections, activeConnectionId, onConnectionChange, onSend, draft, onDraftChange, focusRequest = 0, loading, disabled = false, disabledReason }: ChatInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (focusRequest > 0) textRef.current?.focus();
  }, [focusRequest]);

  const activeConn = connections.find(c => c.id === activeConnectionId);
  const sendDisabled = disabled || loading || !draft.trim();
  const selectorDisabled = connections.length === 0;

  const handleSend = () => {
    if (!draft.trim() || loading || disabled) return;
    onSend(draft.trim());
    onDraftChange('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); handleSend(); }
  };

  return (
    <div style={{ 
      borderTop: `1px solid rgba(0,0,0,0.08)`,
      background: '#fff',
      padding: '12px 24px 16px',
      flexShrink: 0,
      zIndex: 10,
    }}>
      <div style={{
        maxWidth: 1000,
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 16,
          background: '#fff',
          border: `1.5px solid ${isFocused ? '#1a1a1a' : 'rgba(0,0,0,0.1)'}`,
          borderRadius: 0,
          padding: '12px 16px',
          transition: 'all 0.2s ease',
        }}>
          {/* DB Selector (Professional Style) */}
          <div style={{ position: 'relative', marginTop: 2 }}>
            <button
              onClick={() => { if (!selectorDisabled) setShowDropdown(!showDropdown); }}
              disabled={selectorDisabled}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: 'transparent',
                border: `1px solid rgba(0,0,0,0.1)`,
                borderRadius: 0,
                padding: '6px 12px',
                cursor: selectorDisabled ? 'default' : 'pointer',
                color: T.text,
                fontSize: '0.68rem',
                fontFamily: T.fontMono,
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#1a1a1a'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'; }}
            >
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: activeConn ? '#1a1a1a' : '#ef4444' }} />
              {activeConn?.database || disabledReason || 'SELECT DB'}
              <span style={{ fontSize: '0.5rem', color: T.text3, marginLeft: 2 }}>▼</span>
            </button>

            {showDropdown && (
              <div style={{
                position: 'absolute', bottom: 'calc(100% + 12px)', left: 0,
                background: '#fff',
                border: `1px solid rgba(0,0,0,0.15)`,
                borderRadius: 0,
                padding: 4,
                minWidth: 220,
                boxShadow: '0 12px 32px rgba(0,0,0,0.1)',
                zIndex: 100,
              }}>
                {connections.length === 0 && (
                  <div style={{ padding: '10px 14px', fontSize: '0.72rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    NO DATABASES AVAILABLE
                  </div>
                )}
                {connections.map(c => (
                  <div key={c.id} onClick={e => { e.stopPropagation(); onConnectionChange(c.id); setShowDropdown(false); }}
                    style={{
                      padding: '10px 14px', borderRadius: 0, cursor: 'pointer',
                      fontSize: '0.72rem', color: T.text,
                      background: c.id === activeConnectionId ? 'rgba(0,0,0,0.03)' : 'transparent',
                      display: 'flex', alignItems: 'center', gap: 10, transition: 'all 0.15s',
                      fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em'
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,0,0,0.03)'}
                    onMouseLeave={e => e.currentTarget.style.background = c.id === activeConnectionId ? 'rgba(0,0,0,0.03)' : 'transparent'}
                  >
                    <div style={{ width: 4, height: 4, borderRadius: '50%', background: c.status === 'connected' ? '#1a1a1a' : '#ef4444' }} />
                    <span>{c.database}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <textarea
            ref={textRef}
            value={draft}
            onChange={e => onDraftChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={disabledReason || 'What would you like to know?'}
            disabled={disabled}
            maxLength={2048}
            rows={2}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: T.text,
              fontFamily: T.fontBody,
              fontSize: '1rem',
              resize: 'none',
              height: 48,
              overflowY: 'auto',
              padding: '2px 0',
              lineHeight: 1.6,
              scrollbarWidth: 'none',
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
             <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{draft.length} / 2048</span>
             <button
              onClick={handleSend}
              disabled={sendDisabled}
              aria-label="Send message"
              style={{
                width: 40,
                height: 40,
                borderRadius: 0,
                background: !sendDisabled ? '#1a1a1a' : 'rgba(0,0,0,0.05)',
                border: 'none',
                cursor: !sendDisabled ? 'pointer' : 'default',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s',
              }}
            >
              {loading ? (
                <div style={{ width: 14, height: 14, border: `2px solid rgba(255,255,255,0.3)`, borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Hints */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 16, opacity: 0.6 }}>
           <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono }}>
              <span style={{ background: T.s4, padding: '1px 4px', borderRadius: 3 }}>⌘ ↵</span> to send
           </div>
           <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono }}>
              <span style={{ background: T.s4, padding: '1px 4px', borderRadius: 3 }}>/</span> for commands
           </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
