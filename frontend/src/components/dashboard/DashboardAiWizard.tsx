import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { T } from './tokens';
import { DashboardCreateForm } from './DashboardCreateForm';
import { useDashboardGenerationRun } from '../../hooks/useDashboardGenerationRun';
import * as api from '../../services/api';
import type {
  DashboardGenerationRun,
  DashboardPlan,
  DatabaseConnection,
  WidgetPlan,
} from '../../types/api';
import {
  PROMPT_MAX_LENGTH,
  WIDGET_COUNT_DEFAULT,
  WIDGET_COUNT_MAX,
  WIDGET_COUNT_MIN,
  applyDashboardGenerationEvent,
  createEmptyWidgetPlan,
  isDescribeFormValid,
  normalizePlan,
  rememberGenerationRun,
  validateDescribeForm,
} from '../../utils/dashboardGeneration';
import { SuggestionGrid } from '../suggestions/SuggestionGrid';
import { useNavigate } from 'react-router-dom';
import { isLlmSetupError } from '../../services/llmSettings';

type WizardStep = 'describe' | 'planning' | 'review';
type ModalMode = 'manual' | 'ai';

interface DashboardAiWizardProps {
  isOpen: boolean;
  mode: ModalMode;
  onClose: () => void;
  onApproved: (dashboardId: string, runId: string) => void;
  onManualCreate: (name: string) => Promise<void>;
  creatingManual?: boolean;
  initialConnectionId?: string;
  initialPrompt?: string;
}

const VISUALIZATIONS = ['auto', 'kpi', 'bar', 'line', 'area', 'pie', 'donut', 'table'] as const;
const SIZES = ['quarter', 'half', 'three-quarter', 'full'] as const;

const fieldStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: T.radius.sm,
  border: `1px solid ${T.border}`,
  background: T.s1,
  color: T.text,
  fontFamily: T.fontBody,
  fontSize: '0.88rem',
  outline: 'none',
  boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontFamily: T.fontMono,
  fontSize: '0.62rem',
  fontWeight: 800,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: T.text3,
  marginBottom: 6,
};

export function DashboardAiWizard({
  isOpen,
  mode,
  onClose,
  onApproved,
  onManualCreate,
  creatingManual = false,
  initialConnectionId,
  initialPrompt,
}: DashboardAiWizardProps) {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>('describe');
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [connectionId, setConnectionId] = useState('');
  const [prompt, setPrompt] = useState('');
  const [widgetCount, setWidgetCount] = useState(WIDGET_COUNT_DEFAULT);
  const [timePeriod, setTimePeriod] = useState('');
  const [extraInstructions, setExtraInstructions] = useState('');
  const [manualName, setManualName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [setupRequired, setSetupRequired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [savingPlan, setSavingPlan] = useState(false);
  const [approving, setApproving] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<DashboardGenerationRun | null>(null);
  const [planDraft, setPlanDraft] = useState<DashboardPlan | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const initialStateAppliedRef = useRef(false);

  const describeValues = useMemo(() => ({
    connectionId,
    prompt,
    widgetCount,
    timePeriod,
    extraInstructions,
  }), [connectionId, prompt, widgetCount, timePeriod, extraInstructions]);

  const describeErrors = useMemo(() => validateDescribeForm(describeValues), [describeValues]);

  const reset = useCallback(() => {
    setStep('describe');
    setPrompt('');
    setWidgetCount(WIDGET_COUNT_DEFAULT);
    setTimePeriod('');
    setExtraInstructions('');
    setManualName('');
    setError(null);
    setSetupRequired(false);
    setSubmitting(false);
    setSavingPlan(false);
    setApproving(false);
    setRunId(null);
    setSnapshot(null);
    setPlanDraft(null);
    setShowErrors(false);
  }, []);

  const { startPlanning, cancel, disconnect } = useDashboardGenerationRun({
    onEvent: (event) => {
      setSnapshot((current) => applyDashboardGenerationEvent(current, event));
    },
    onSnapshot: (next) => {
      setSnapshot(next);
      if (next.plan_json) setPlanDraft(normalizePlan(next.plan_json));
      if (next.status === 'awaiting_approval') setStep('review');
      if (next.status === 'failed') {
        setError(next.failure_message || 'Planning failed');
        setStep('describe');
      }
      if (next.status === 'cancelled') {
        setError('Generation cancelled');
        setStep('describe');
      }
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Stream connection failed');
    },
  });

  useEffect(() => {
    if (!isOpen || mode !== 'ai') return;
    let cancelled = false;
    listConnectionsSafe().then((items) => {
      if (cancelled) return;
      setConnections(items);
      const hasRequestedConnection = !initialConnectionId || items.some((item) => item.id === initialConnectionId);
      const requested = initialConnectionId && hasRequestedConnection ? initialConnectionId : '';
      if (!connectionId && (requested || items[0])) setConnectionId(requested || items[0].id);
      if (!initialStateAppliedRef.current) {
        initialStateAppliedRef.current = true;
        if (initialConnectionId && !hasRequestedConnection) {
          setError('The selected database connection is no longer available.');
        } else if (initialPrompt) {
          setPrompt(initialPrompt.slice(0, PROMPT_MAX_LENGTH));
        }
      }
    });
    return () => { cancelled = true; };
  }, [isOpen, mode, connectionId, initialConnectionId, initialPrompt]);

  useEffect(() => {
    if (!isOpen) {
      disconnect();
      reset();
      initialStateAppliedRef.current = false;
    }
  }, [isOpen, disconnect, reset]);

  if (!isOpen) return null;

  const handleStartPlanning = async () => {
    setShowErrors(true);
    if (!isDescribeFormValid(describeValues)) return;
    setSubmitting(true);
    setError(null);
    setStep('planning');
    try {
      const accepted = await startPlanning({
        connection_id: connectionId,
        prompt: prompt.trim(),
        requested_widget_count: widgetCount,
        default_time_range: timePeriod.trim() || null,
        extra_instructions: extraInstructions.trim() || null,
        client_request_id: crypto.randomUUID(),
      });
      setRunId(accepted.run_id);
    } catch (err) {
      setSetupRequired(isLlmSetupError(err));
      setError(err instanceof Error ? err.message : 'Failed to start planning');
      setStep('describe');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSavePlan = async () => {
    if (!runId || !planDraft || !snapshot) return;
    setSavingPlan(true);
    setError(null);
    try {
      const next = await api.updateDashboardGenerationPlan(runId, {
        expected_revision: snapshot.plan_revision,
        plan: planDraft,
      });
      setSnapshot(next);
      setPlanDraft(normalizePlan(next.plan_json));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save plan');
    } finally {
      setSavingPlan(false);
    }
  };

  const handleApprove = async () => {
    if (!runId || !snapshot) return;
    setApproving(true);
    setError(null);
    try {
      if (planDraft) {
        const saved = await api.updateDashboardGenerationPlan(runId, {
          expected_revision: snapshot.plan_revision,
          plan: planDraft,
        });
        setSnapshot(saved);
        const approved = await api.approveDashboardGeneration(runId, {
          expected_revision: saved.plan_revision,
        });
        if (!approved.dashboard_id) throw new Error('Approve did not return a dashboard id');
        rememberGenerationRun(approved.dashboard_id, approved.run_id);
        onApproved(approved.dashboard_id, approved.run_id);
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve plan');
    } finally {
      setApproving(false);
    }
  };

  const handleCancel = async () => {
    if (!runId) {
      onClose();
      return;
    }
    try {
      await cancel(runId);
    } catch {
      // Still close the wizard.
    }
    onClose();
  };

  const handleRegeneratePlan = async () => {
    if (runId) {
      try { await cancel(runId); } catch { /* ignore */ }
    }
    disconnect();
    setRunId(null);
    setSnapshot(null);
    setPlanDraft(null);
    setStep('describe');
    setError(null);
  };

  const updateWidget = (index: number, patch: Partial<WidgetPlan>) => {
    setPlanDraft((prev) => {
      if (!prev) return prev;
      const widgets = prev.widgets.map((widget, i) => (i === index ? { ...widget, ...patch } : widget));
      return { ...prev, widgets };
    });
  };

  const moveWidget = (index: number, direction: -1 | 1) => {
    setPlanDraft((prev) => {
      if (!prev) return prev;
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= prev.widgets.length) return prev;
      const widgets = [...prev.widgets];
      const [item] = widgets.splice(index, 1);
      widgets.splice(nextIndex, 0, item);
      return { ...prev, widgets };
    });
  };

  const title = mode === 'manual'
    ? 'Create manually'
    : step === 'review'
      ? 'Review plan'
      : step === 'planning'
        ? 'Planning dashboard'
        : 'Generate with AI';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="dash-ai-wizard-title"
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
          maxWidth: mode === 'ai' && step === 'review' ? 820 : 560,
          maxHeight: '90vh',
          overflowY: 'auto',
          background: T.s1,
          border: `1px solid ${T.border}`,
          borderRadius: T.radius.lg,
          padding: '28px 28px 22px',
          boxShadow: T.shadow.lg,
        }}
      >
        <div
          id="dash-ai-wizard-title"
          style={{
            fontFamily: T.fontHead,
            fontWeight: 900,
            fontSize: 'clamp(1.25rem, 2.4vw, 1.6rem)',
            color: T.text,
            marginBottom: 6,
          }}
        >
          {title}
        </div>

        {mode === 'manual' && (
          <div style={{ marginTop: 18 }}>
            <DashboardCreateForm
              value={manualName}
              onChange={setManualName}
              onCreate={() => onManualCreate(manualName)}
              onCancel={onClose}
              creating={creatingManual}
              ctaLabel="Create"
            />
          </div>
        )}

        {mode === 'ai' && step === 'describe' && (
          <div style={{ display: 'grid', gap: 16, marginTop: 16 }}>
            <div>
              <label style={labelStyle} htmlFor="dash-gen-connection">Connection</label>
              <select
                id="dash-gen-connection"
                value={connectionId}
                onChange={(e) => setConnectionId(e.target.value)}
                style={fieldStyle}
              >
                <option value="">Select connection…</option>
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>{conn.name}</option>
                ))}
              </select>
              {showErrors && describeErrors.connectionId && (
                <FieldError>{describeErrors.connectionId}</FieldError>
              )}
            </div>

            <div>
              <label style={labelStyle} htmlFor="dash-gen-prompt">
                Prompt ({prompt.length}/{PROMPT_MAX_LENGTH})
              </label>
              <textarea
                id="dash-gen-prompt"
                value={prompt}
                maxLength={PROMPT_MAX_LENGTH}
                rows={5}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="What should this dashboard help you understand?"
                style={{ ...fieldStyle, resize: 'vertical', minHeight: 120 }}
              />
              {showErrors && describeErrors.prompt && (
                <FieldError>{describeErrors.prompt}</FieldError>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={labelStyle} htmlFor="dash-gen-count">Widgets</label>
                <input
                  id="dash-gen-count"
                  type="number"
                  min={WIDGET_COUNT_MIN}
                  max={WIDGET_COUNT_MAX}
                  value={widgetCount}
                  onChange={(e) => setWidgetCount(Number(e.target.value))}
                  style={fieldStyle}
                />
                {showErrors && describeErrors.widgetCount && (
                  <FieldError>{describeErrors.widgetCount}</FieldError>
                )}
              </div>
              <div>
                <label style={labelStyle} htmlFor="dash-gen-period">Time period (optional)</label>
                <input
                  id="dash-gen-period"
                  value={timePeriod}
                  onChange={(e) => setTimePeriod(e.target.value)}
                  placeholder="Last 90 days"
                  style={fieldStyle}
                />
              </div>
            </div>

            <div>
              <label style={labelStyle} htmlFor="dash-gen-extra">Extra instructions (optional)</label>
              <textarea
                id="dash-gen-extra"
                value={extraInstructions}
                rows={3}
                maxLength={2000}
                onChange={(e) => setExtraInstructions(e.target.value)}
                placeholder="Emphasize executive KPIs, avoid raw tables…"
                style={{ ...fieldStyle, resize: 'vertical' }}
              />
            </div>

            {connectionId ? (
              <SuggestionGrid
                connectionId={connectionId}
                surface="dashboard"
                onSelect={(suggestion) => setPrompt(suggestion.prompt)}
                primaryLabel="Fill prompt"
                compact
              />
            ) : (
              <div style={{ color: T.text3, fontSize: '0.75rem' }}>
                Select a database connection to see schema-aware dashboard ideas.
              </div>
            )}

            {error && <FieldError>{error}</FieldError>}
            {setupRequired && (
              <button type="button" style={{ border: `1px solid ${T.accent}`, background: T.s2, color: T.accent, padding: '9px 12px', cursor: 'pointer' }} onClick={() => navigate('/settings', { state: { section: 'ai', returnTo: '/dashboards', connectionId, prompt } })}>
                Configure AI provider
              </button>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <SecondaryButton onClick={onClose}>Cancel</SecondaryButton>
              <PrimaryButton onClick={handleStartPlanning} disabled={submitting}>
                {submitting ? 'Starting…' : 'Generate plan'}
              </PrimaryButton>
            </div>
          </div>
        )}

        {mode === 'ai' && step === 'planning' && (
          <div style={{ marginTop: 24, textAlign: 'center' }}>
            <div style={{
              width: 36,
              height: 36,
              margin: '0 auto 16px',
              border: `3px solid ${T.border}`,
              borderTopColor: T.accent,
              borderRadius: '50%',
              animation: 'spin 0.9s linear infinite',
            }} />
            <div style={{ fontFamily: T.fontHead, fontWeight: 700, fontSize: '1.05rem', color: T.text, marginBottom: 8 }}>
              {snapshot?.current_stage_label || 'Reading the dashboard objective'}
            </div>
            <div style={{ fontFamily: T.fontMono, fontSize: '0.68rem', color: T.text3, letterSpacing: '0.06em' }}>
              {(snapshot?.current_stage || 'planning').toUpperCase()}
            </div>
            {error && <div style={{ marginTop: 12 }}><FieldError>{error}</FieldError></div>}
            <div style={{ marginTop: 22 }}>
              <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {mode === 'ai' && step === 'review' && planDraft && (
          <div style={{ display: 'grid', gap: 16, marginTop: 16 }}>
            <div style={{ display: 'grid', gap: 12 }}>
              <div>
                <label style={labelStyle}>Title</label>
                <input
                  value={planDraft.title}
                  onChange={(e) => setPlanDraft({ ...planDraft, title: e.target.value })}
                  style={fieldStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Description</label>
                <textarea
                  value={planDraft.description || ''}
                  onChange={(e) => setPlanDraft({ ...planDraft, description: e.target.value })}
                  rows={2}
                  style={{ ...fieldStyle, resize: 'vertical' }}
                />
              </div>
            </div>

            {(planDraft.assumptions?.length || planDraft.warnings?.length) ? (
              <div style={{ display: 'grid', gap: 8 }}>
                {(planDraft.assumptions || []).map((item) => (
                  <Note key={`a-${item}`} tone="neutral">{item}</Note>
                ))}
                {(planDraft.warnings || []).map((item) => (
                  <Note key={`w-${item}`} tone="warn">{item}</Note>
                ))}
              </div>
            ) : null}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ ...labelStyle, marginBottom: 0 }}>
                Widgets ({planDraft.widgets.length}/8)
              </div>
              <button
                type="button"
                disabled={planDraft.widgets.length >= 8}
                onClick={() => setPlanDraft({
                  ...planDraft,
                  widgets: [...planDraft.widgets, createEmptyWidgetPlan(planDraft.widgets.length)],
                })}
                style={{
                  padding: '6px 10px',
                  borderRadius: T.radius.sm,
                  border: `1px solid ${T.border}`,
                  background: T.s2,
                  color: T.text,
                  fontFamily: T.fontMono,
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  cursor: planDraft.widgets.length >= 8 ? 'not-allowed' : 'pointer',
                  opacity: planDraft.widgets.length >= 8 ? 0.5 : 1,
                }}
              >
                + ADD WIDGET
              </button>
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
              {planDraft.widgets.map((widget, index) => (
                <div
                  key={widget.client_key}
                  style={{
                    border: `1px solid ${T.border}`,
                    borderRadius: T.radius.md,
                    padding: 14,
                    background: T.s2,
                    display: 'grid',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontFamily: T.fontMono, fontSize: '0.62rem', color: T.text3, fontWeight: 800 }}>
                      WIDGET {index + 1}
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <TinyButton onClick={() => moveWidget(index, -1)} disabled={index === 0}>↑</TinyButton>
                      <TinyButton onClick={() => moveWidget(index, 1)} disabled={index === planDraft.widgets.length - 1}>↓</TinyButton>
                      <TinyButton
                        onClick={() => setPlanDraft({
                          ...planDraft,
                          widgets: planDraft.widgets.filter((_, i) => i !== index),
                        })}
                        disabled={planDraft.widgets.length <= 1}
                        danger
                      >
                        Remove
                      </TinyButton>
                    </div>
                  </div>
                  <input
                    value={widget.title}
                    onChange={(e) => updateWidget(index, { title: e.target.value })}
                    placeholder="Title"
                    style={fieldStyle}
                  />
                  <textarea
                    value={widget.question}
                    onChange={(e) => updateWidget(index, { question: e.target.value })}
                    placeholder="Analytical question"
                    rows={2}
                    style={{ ...fieldStyle, resize: 'vertical' }}
                  />
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                    <select
                      value={widget.visualization}
                      onChange={(e) => updateWidget(index, { visualization: e.target.value as WidgetPlan['visualization'] })}
                      style={fieldStyle}
                    >
                      {VISUALIZATIONS.map((v) => <option key={v} value={v}>{v}</option>)}
                    </select>
                    <select
                      value={widget.size}
                      onChange={(e) => updateWidget(index, { size: e.target.value as WidgetPlan['size'] })}
                      style={fieldStyle}
                    >
                      {SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <input
                      value={widget.time_range || ''}
                      onChange={(e) => updateWidget(index, { time_range: e.target.value || null })}
                      placeholder="Time range"
                      style={fieldStyle}
                    />
                  </div>
                </div>
              ))}
            </div>

            {error && <FieldError>{error}</FieldError>}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'flex-end' }}>
              <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
              <SecondaryButton onClick={handleRegeneratePlan}>Regenerate plan</SecondaryButton>
              <SecondaryButton onClick={handleSavePlan} disabled={savingPlan}>
                {savingPlan ? 'Saving…' : 'Save edits'}
              </SecondaryButton>
              <PrimaryButton onClick={handleApprove} disabled={approving || planDraft.widgets.length < 1}>
                {approving ? 'Approving…' : 'Approve & generate'}
              </PrimaryButton>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function FieldError({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 6, color: T.red, fontFamily: T.fontBody, fontSize: '0.78rem' }}>
      {children}
    </div>
  );
}

function Note({ children, tone }: { children: React.ReactNode; tone: 'neutral' | 'warn' }) {
  return (
    <div style={{
      padding: '8px 10px',
      borderRadius: T.radius.sm,
      border: `1px solid ${tone === 'warn' ? 'rgba(245,158,11,0.35)' : T.border}`,
      background: tone === 'warn' ? T.yellowDim : T.s2,
      color: T.text2,
      fontSize: '0.78rem',
      fontFamily: T.fontBody,
    }}>
      {children}
    </div>
  );
}

function PrimaryButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '10px 16px',
        borderRadius: T.radius.sm,
        border: 'none',
        background: T.text,
        color: T.bg,
        fontFamily: T.fontMono,
        fontSize: '0.72rem',
        fontWeight: 800,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}
    >
      {children}
    </button>
  );
}

function SecondaryButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '10px 14px',
        borderRadius: T.radius.sm,
        border: `1px solid ${T.border}`,
        background: 'transparent',
        color: T.text2,
        fontFamily: T.fontBody,
        fontSize: '0.82rem',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}
    >
      {children}
    </button>
  );
}

function TinyButton({
  children,
  onClick,
  disabled,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '4px 8px',
        borderRadius: 6,
        border: `1px solid ${danger ? 'rgba(239,68,68,0.35)' : T.border}`,
        background: danger ? T.redDim : T.s1,
        color: danger ? T.red : T.text2,
        fontSize: '0.68rem',
        fontFamily: T.fontMono,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
      }}
    >
      {children}
    </button>
  );
}

async function listConnectionsSafe(): Promise<DatabaseConnection[]> {
  try {
    return await api.listConnections();
  } catch {
    return [];
  }
}
