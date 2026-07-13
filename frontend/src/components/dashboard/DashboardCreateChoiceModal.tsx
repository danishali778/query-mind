import { T } from './tokens';

interface DashboardCreateChoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onChooseAi: () => void;
  onChooseManual: () => void;
}

export function DashboardCreateChoiceModal({
  isOpen,
  onClose,
  onChooseAi,
  onChooseManual,
}: DashboardCreateChoiceModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="dash-create-choice-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
        background: 'rgba(26, 26, 26, 0.45)',
        backdropFilter: 'blur(6px)',
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 560,
          background: T.s1,
          border: `1px solid ${T.border}`,
          borderRadius: T.radius.lg,
          padding: '28px 28px 24px',
          boxShadow: T.shadow.lg,
        }}
      >
        <div
          id="dash-create-choice-title"
          style={{
            fontFamily: T.fontHead,
            fontWeight: 900,
            fontSize: 'clamp(1.35rem, 2.5vw, 1.7rem)',
            color: T.text,
            marginBottom: 8,
          }}
        >
          New dashboard
        </div>
        <div style={{ fontFamily: T.fontBody, fontSize: '0.9rem', color: T.text2, marginBottom: 24, lineHeight: 1.55 }}>
          Generate a draft from a prompt, or start with an empty canvas.
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          <button
            type="button"
            onClick={onChooseAi}
            style={{
              textAlign: 'left',
              padding: '18px 18px',
              borderRadius: T.radius.md,
              border: `1px solid ${T.border}`,
              background: T.s2,
              cursor: 'pointer',
              transition: T.transition,
            }}
          >
            <div style={{ fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.08em', color: T.accent, marginBottom: 6 }}>
              GENERATE WITH AI
            </div>
            <div style={{ fontFamily: T.fontHead, fontWeight: 700, fontSize: '1.05rem', color: T.text, marginBottom: 4 }}>
              Prompt to dashboard
            </div>
            <div style={{ fontFamily: T.fontBody, fontSize: '0.82rem', color: T.text3, lineHeight: 1.5 }}>
              Describe the outcome you want. Review a plan, then watch widgets generate on a draft board.
            </div>
          </button>

          <button
            type="button"
            onClick={onChooseManual}
            style={{
              textAlign: 'left',
              padding: '18px 18px',
              borderRadius: T.radius.md,
              border: `1px solid ${T.border}`,
              background: T.s1,
              cursor: 'pointer',
              transition: T.transition,
            }}
          >
            <div style={{ fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.08em', color: T.text3, marginBottom: 6 }}>
              CREATE MANUALLY
            </div>
            <div style={{ fontFamily: T.fontHead, fontWeight: 700, fontSize: '1.05rem', color: T.text, marginBottom: 4 }}>
              Empty dashboard
            </div>
            <div style={{ fontFamily: T.fontBody, fontSize: '0.82rem', color: T.text3, lineHeight: 1.5 }}>
              Name a blank dashboard and add widgets from Chat when you are ready.
            </div>
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '8px 14px',
              borderRadius: T.radius.sm,
              border: `1px solid ${T.border}`,
              background: 'transparent',
              color: T.text2,
              fontFamily: T.fontBody,
              fontSize: '0.82rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
