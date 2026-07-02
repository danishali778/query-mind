import { AlertTriangle } from 'lucide-react';
import { T } from '../dashboard/tokens';
import type { ConnectionListItem } from '../../types/connections';

export function DisconnectConnectionModal({
  connection,
  isDisconnecting,
  error,
  onCancel,
  onConfirm,
}: {
  connection: ConnectionListItem | null;
  isDisconnecting: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!connection) return null;

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(26,26,26,0.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div role="dialog" aria-modal="true" aria-labelledby="disconnect-title" style={{ width: 'min(520px, 100%)', background: T.s1, border: `1px solid ${T.border}`, boxShadow: T.shadow.xl }}>
        <div style={{ padding: '22px 24px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', background: T.redDim, color: T.red }}>
            <AlertTriangle size={18} />
          </div>
          <div>
            <div id="disconnect-title" style={{ fontFamily: T.fontHead, fontSize: '1.2rem', fontWeight: 900, color: T.text, fontStyle: 'italic' }}>Disconnect Source</div>
            <div style={{ fontFamily: T.fontMono, fontSize: '0.62rem', color: T.text3, textTransform: 'uppercase', letterSpacing: '1px' }}>{connection.name}</div>
          </div>
        </div>

        <div style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <p style={{ margin: 0, color: T.text2, fontSize: '0.78rem', lineHeight: 1.7 }}>
            This removes the saved connection from query-mind. Saved queries, dashboards, generated templates, and chat flows tied to this source may stop working until they are reconnected.
          </p>
          <div style={{ padding: '12px 14px', background: T.redDim, border: `1px solid ${T.red}`, color: T.red, fontFamily: T.fontMono, fontSize: '0.66rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            This action cannot be undone from the app UI.
          </div>
          {error && (
            <div style={{ padding: '10px 12px', background: T.s2, border: `1px solid ${T.red}`, color: T.red, fontFamily: T.fontMono, fontSize: '0.66rem', fontWeight: 800 }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ padding: '18px 24px', borderTop: `1px solid ${T.border}`, display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button onClick={onCancel} disabled={isDisconnecting} style={{ padding: '10px 18px', border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 800, cursor: isDisconnecting ? 'not-allowed' : 'pointer' }}>
            CANCEL
          </button>
          <button onClick={onConfirm} disabled={isDisconnecting} style={{ padding: '10px 18px', border: `1px solid ${T.red}`, background: T.red, color: '#fff', fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 900, cursor: isDisconnecting ? 'not-allowed' : 'pointer' }}>
            {isDisconnecting ? 'DISCONNECTING...' : 'CONFIRM DISCONNECT'}
          </button>
        </div>
      </div>
    </div>
  );
}