import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Eye, EyeOff, KeyRound, RefreshCw, Trash2 } from 'lucide-react';

import { T } from '../dashboard/tokens';
import {
  deleteLlmCredential,
  getLlmConfiguration,
  getLlmUsage,
  revalidateLlmCredential,
  saveLlmCredential,
  updateLlmPreferences,
} from '../../services/llmSettings';
import type { LlmConfiguration, LlmProvider, LlmUsageEvent } from '../../types/llmSettings';

const PROVIDER_LABELS: Record<LlmProvider, string> = {
  gemini: 'GOOGLE GEMINI',
  groq: 'GROQ',
  openai: 'OPENAI',
};

const buttonStyle = {
  border: `1px solid ${T.border}`,
  background: T.s2,
  color: T.text,
  padding: '9px 12px',
  fontFamily: T.fontMono,
  fontSize: '0.62rem',
  fontWeight: 900,
  cursor: 'pointer',
} as const;

export function LlmProviderSettings() {
  const [configuration, setConfiguration] = useState<LlmConfiguration | null>(null);
  const [usage, setUsage] = useState<LlmUsageEvent[]>([]);
  const [usageUnavailable, setUsageUnavailable] = useState(false);
  const [keys, setKeys] = useState<Partial<Record<LlmProvider, string>>>({});
  const [models, setModels] = useState<Partial<Record<LlmProvider, string>>>({});
  const [visible, setVisible] = useState<Partial<Record<LlmProvider, boolean>>>({});
  const [busy, setBusy] = useState<LlmProvider | 'preferences' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const next = await getLlmConfiguration();
      setConfiguration(next);
      try {
        const usagePage = await getLlmUsage(20);
        setUsage(usagePage.items);
        setUsageUnavailable(false);
      } catch {
        setUsageUnavailable(true);
      }
      setModels(current => {
        const updated = { ...current };
        for (const provider of next.providers) {
          updated[provider.provider] =
            next.preferred_provider === provider.provider && next.preferred_model
              ? next.preferred_model
              : updated[provider.provider] || provider.allowed_models[0];
        }
        return updated;
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load AI provider settings.');
    }
  }, []);

  useEffect(() => {
    void load();
    return () => {
      setKeys({});
    };
  }, [load]);

  const configuredProviders = useMemo(
    () => configuration?.providers.filter(provider => provider.configured) || [],
    [configuration],
  );

  async function save(provider: LlmProvider) {
    const apiKey = keys[provider]?.trim();
    const model = models[provider];
    const current = configuration?.providers.find(item => item.provider === provider);
    if (!apiKey || !model) {
      setError('Enter an API key and select an allowed model.');
      return;
    }
    setBusy(provider);
    setError(null);
    setNotice(null);
    try {
      await saveLlmCredential(provider, {
        api_key: apiKey,
        model,
        ...(current?.credential_revision ? { expected_credential_revision: current.credential_revision } : {}),
      });
      setKeys(previous => ({ ...previous, [provider]: '' }));
      setVisible(previous => ({ ...previous, [provider]: false }));
      setNotice(`${PROVIDER_LABELS[provider]} credential validated and saved.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Credential validation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function revalidate(provider: LlmProvider) {
    setBusy(provider);
    setError(null);
    try {
      await revalidateLlmCredential(provider);
      setNotice(`${PROVIDER_LABELS[provider]} credential is valid.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Credential validation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function remove(provider: LlmProvider, revision: number) {
    if (!window.confirm(`Remove the saved ${PROVIDER_LABELS[provider]} credential?`)) return;
    const replacement = configuration?.preferred_provider === provider
      ? configuredProviders.find(item => item.provider !== provider)?.provider
      : undefined;
    setBusy(provider);
    setError(null);
    try {
      await deleteLlmCredential(provider, {
        expected_credential_revision: revision,
        ...(replacement ? { replacement_provider: replacement } : {}),
      });
      setNotice(`${PROVIDER_LABELS[provider]} credential removed.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to remove this credential.');
    } finally {
      setBusy(null);
    }
  }

  async function updatePreference(provider: LlmProvider | null, model: string | null, background: boolean) {
    if (!configuration) return;
    setBusy('preferences');
    setError(null);
    try {
      await updateLlmPreferences({
        expected_preference_revision: configuration.preference_revision,
        preferred_provider: provider,
        preferred_model: model,
        allow_background_ai: background,
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to update AI preferences.');
    } finally {
      setBusy(null);
    }
  }

  if (!configuration) {
    return <div role="status" style={{ color: T.text3, fontFamily: T.fontMono }}>LOADING_AI_PROVIDER_SETTINGS...</div>;
  }

  const fallback = configuration.deployment_fallback;

  return (
    <div>
      <div style={{ marginBottom: 40, borderBottom: `2px solid ${T.text}`, paddingBottom: 24 }}>
        <h1 style={{ margin: 0, color: T.text, fontFamily: T.fontHead, fontSize: 'clamp(2rem, 5vw, 3.6rem)' }}>AI_PROVIDER_KEYS</h1>
        <p style={{ color: T.text2, fontFamily: T.fontMono, fontSize: '0.72rem', letterSpacing: 1.5 }}>
          YOUR KEYS ARE VALIDATED SERVER-SIDE, ENCRYPTED AT REST, AND NEVER SHOWN AGAIN.
        </p>
      </div>

      {(error || notice) && (
        <div role={error ? 'alert' : 'status'} aria-live="polite" style={{ marginBottom: 20, padding: 14, border: `1px solid ${error ? T.red : T.green}`, color: error ? T.red : T.green, background: error ? T.redDim : T.greenDim, fontFamily: T.fontMono, fontSize: '0.68rem' }}>
          {error ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />} {' '}{error || notice}
        </div>
      )}

      <section style={{ border: `1px solid ${T.border}`, background: T.s1, padding: 24, marginBottom: 24 }}>
        <div style={{ color: T.text, fontFamily: T.fontMono, fontWeight: 900, marginBottom: 8 }}>QUERYMIND_DEPLOYMENT_FALLBACK</div>
        <div style={{ color: T.text2, fontFamily: T.fontMono, fontSize: '0.68rem', lineHeight: 1.7 }}>
          {fallback.privileged
            ? 'This account has privileged deployment-key access.'
            : `${fallback.calls_remaining} of ${fallback.calls_limit} lifetime provider calls remain.`}
          {' '}One agent action can make multiple provider calls. Personal-key calls do not consume this allowance.
        </div>
        {fallback.calls_remaining <= 3 && !fallback.privileged && (
          <div style={{ color: T.yellow, marginTop: 10, fontFamily: T.fontMono, fontSize: '0.68rem' }}>ADD A PERSONAL KEY BEFORE THE TRIAL RUNS OUT.</div>
        )}
      </section>

      <div style={{ display: 'grid', gap: 20 }}>
        {configuration.providers.map(provider => {
          const selectedModel = models[provider.provider] || provider.allowed_models[0];
          const isPreferred = configuration.preferred_provider === provider.provider;
          return (
            <section key={provider.provider} style={{ border: `1px solid ${isPreferred ? T.accent : T.border}`, background: T.s1, padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: T.text, fontFamily: T.fontMono, fontWeight: 950 }}>
                  <KeyRound size={16} color={T.accent} /> {PROVIDER_LABELS[provider.provider]}
                </div>
                <span style={{ color: provider.status === 'invalid' ? T.red : provider.configured ? T.green : T.text3, fontFamily: T.fontMono, fontSize: '0.6rem' }}>
                  {provider.configured ? `${provider.status?.toUpperCase()} - ****${provider.key_hint}` : 'NOT_CONFIGURED'}
                </span>
              </div>

              <label style={{ display: 'block', color: T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', marginBottom: 6 }} htmlFor={`model-${provider.provider}`}>MODEL</label>
              <select id={`model-${provider.provider}`} value={selectedModel} onChange={event => setModels(previous => ({ ...previous, [provider.provider]: event.target.value }))} style={{ width: '100%', padding: 11, marginBottom: 14, background: T.s2, color: T.text, border: `1px solid ${T.border}`, fontFamily: T.fontMono }}>
                {provider.allowed_models.map(model => <option value={model} key={model}>{model}</option>)}
              </select>

              <label style={{ display: 'block', color: T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', marginBottom: 6 }} htmlFor={`key-${provider.provider}`}>
                {provider.configured ? 'ROTATE_API_KEY' : 'API_KEY'}
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input id={`key-${provider.provider}`} autoComplete="off" type={visible[provider.provider] ? 'text' : 'password'} value={keys[provider.provider] || ''} onChange={event => setKeys(previous => ({ ...previous, [provider.provider]: event.target.value }))} style={{ minWidth: 0, flex: 1, padding: 11, background: T.s2, color: T.text, border: `1px solid ${T.border}`, fontFamily: T.fontMono }} />
                <button type="button" aria-label={`${visible[provider.provider] ? 'Hide' : 'Show'} ${PROVIDER_LABELS[provider.provider]} API key`} onClick={() => setVisible(previous => ({ ...previous, [provider.provider]: !previous[provider.provider] }))} style={buttonStyle}>
                  {visible[provider.provider] ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
                <button type="button" disabled={busy !== null} onClick={() => void save(provider.provider)} style={{ ...buttonStyle, background: T.accent, color: '#000' }}>
                  {busy === provider.provider ? 'VALIDATING...' : 'VALIDATE & SAVE'}
                </button>
                {provider.configured && provider.credential_revision && (
                  <>
                    <button type="button" disabled={busy !== null} onClick={() => void revalidate(provider.provider)} style={buttonStyle}><RefreshCw size={13} /> REVALIDATE</button>
                    {!isPreferred && <button type="button" disabled={busy !== null} onClick={() => void updatePreference(provider.provider, selectedModel, configuration.allow_background_ai)} style={buttonStyle}>MAKE PREFERRED</button>}
                    {isPreferred && selectedModel !== configuration.preferred_model && <button type="button" disabled={busy !== null} onClick={() => void updatePreference(provider.provider, selectedModel, configuration.allow_background_ai)} style={buttonStyle}>USE MODEL</button>}
                    <button type="button" aria-label={`Remove ${PROVIDER_LABELS[provider.provider]} credential`} disabled={busy !== null} onClick={() => void remove(provider.provider, provider.credential_revision!)} style={{ ...buttonStyle, color: T.red }}><Trash2 size={13} /> REMOVE</button>
                  </>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <section style={{ border: `1px solid ${T.border}`, background: T.s1, padding: 24, marginTop: 24 }}>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer' }}>
          <input type="checkbox" checked={configuration.allow_background_ai} disabled={busy !== null || !configuration.preferred_provider} onChange={event => void updatePreference(configuration.preferred_provider, configuration.preferred_model, event.target.checked)} />
          <span>
            <strong style={{ display: 'block', color: T.text, fontFamily: T.fontMono, fontSize: '0.7rem' }}>ALLOW_BACKGROUND_AI_PERSONALIZATION</strong>
            <span style={{ display: 'block', color: T.text3, fontFamily: T.fontMono, fontSize: '0.64rem', marginTop: 5, lineHeight: 1.6 }}>Allows cached suggestions and templates to use your personal provider key and may create provider charges.</span>
          </span>
        </label>
      </section>

      <section style={{ border: `1px solid ${T.border}`, background: T.s1, padding: 24, marginTop: 24 }}>
        <div style={{ color: T.text, fontFamily: T.fontMono, fontWeight: 900, marginBottom: 6 }}>RECENT_AI_INVOCATIONS</div>
        <p style={{ color: T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', lineHeight: 1.6, marginTop: 0 }}>
          Sanitized provider activity only. Prompts, responses, SQL, and API keys are never stored here.
        </p>
        {usageUnavailable ? (
          <div role="status" style={{ color: T.yellow, fontFamily: T.fontMono, fontSize: '0.64rem' }}>USAGE_HISTORY_TEMPORARILY_UNAVAILABLE</div>
        ) : usage.length === 0 ? (
          <div style={{ color: T.text3, fontFamily: T.fontMono, fontSize: '0.64rem' }}>NO_AI_INVOCATIONS_RECORDED</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 680, fontFamily: T.fontMono, fontSize: '0.62rem' }}>
              <thead>
                <tr style={{ color: T.text3, textAlign: 'left', borderBottom: `1px solid ${T.border}` }}>
                  <th style={{ padding: '9px 8px' }}>TIME</th>
                  <th style={{ padding: '9px 8px' }}>PROVIDER</th>
                  <th style={{ padding: '9px 8px' }}>SOURCE</th>
                  <th style={{ padding: '9px 8px' }}>FEATURE</th>
                  <th style={{ padding: '9px 8px' }}>STATUS</th>
                  <th style={{ padding: '9px 8px' }}>TOKENS</th>
                  <th style={{ padding: '9px 8px' }}>LATENCY</th>
                </tr>
              </thead>
              <tbody>
                {usage.map(event => (
                  <tr key={event.id} style={{ borderBottom: `1px solid ${T.border}`, color: T.text2 }}>
                    <td style={{ padding: '10px 8px', whiteSpace: 'nowrap' }}>{event.created_at ? new Date(event.created_at).toLocaleString() : '-'}</td>
                    <td style={{ padding: '10px 8px' }}>{event.provider.toUpperCase()}</td>
                    <td style={{ padding: '10px 8px' }}>{event.credential_source === 'user' ? 'YOUR KEY' : 'QUERYMIND TRIAL'}</td>
                    <td style={{ padding: '10px 8px' }}>{event.feature}</td>
                    <td style={{ padding: '10px 8px', color: event.status === 'failed' ? T.red : event.status === 'completed' ? T.green : T.yellow }}>{event.status.toUpperCase()}</td>
                    <td style={{ padding: '10px 8px' }}>{event.input_tokens == null && event.output_tokens == null ? '-' : `${event.input_tokens || 0} / ${event.output_tokens || 0}`}</td>
                    <td style={{ padding: '10px 8px' }}>{event.latency_ms == null ? '-' : `${Math.round(event.latency_ms)} ms`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
