import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  User, Zap, CreditCard, 
  LogOut, AlertTriangle,
  Monitor, Smartphone, ChevronRight
} from 'lucide-react';
import { MainShell } from '../components/common/MainShell';
import { T } from '../components/dashboard/tokens';
import { useSettingsStore } from '../store/settingsStore';
import { useAuth } from '../context/AuthContext';

type Section = 'profile' | 'billing';

const NAV: { id: Section; label: string; icon: any; badge?: string }[] = [
  { id: 'profile',       label: 'PROFILE',       icon: User },
  { id: 'billing',       label: 'BILLING',       icon: CreditCard, badge: 'PRO' },
];

export function SettingsPage() {
  const [section, setSection] = useState<Section>('profile');
  const { settings, isLoading, fetchSettings } = useSettingsStore();

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  if (isLoading && !settings) {
    return (
      <MainShell title="USER_SETTINGS" subtitle="PREFERENCES AND SECURITY CONFIGURATION">
        <div style={{ padding: 40, color: T.text3, fontFamily: T.fontMono, fontSize: '0.72rem' }}>AWAITING_TELEMETRY...</div>
      </MainShell>
    );
  }

  return (
    <MainShell
      title="SETTINGS"
      subtitle="SYSTEM CONFIGURATION & ACCESS"
      badge={{
        text: 'PRO_LICENSE',
        color: T.accent,
        icon: <Zap size={10} fill={T.accent} />
      }}
    >
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', background: T.bg, position: 'relative' }}>
        {/* Faint Grid Background */}
        <div style={{ 
          position: 'absolute', inset: 0, 
          backgroundImage: `radial-gradient(${T.border} 1px, transparent 1px)`, 
          backgroundSize: '40px 40px', opacity: 0.1, pointerEvents: 'none' 
        }} />

        {/* Sidebar */}
        <aside style={{
          width: 240, flexShrink: 0, background: T.s1,
          borderRight: `1px solid ${T.border}`,
          padding: '40px 0', display: 'flex', flexDirection: 'column',
          zIndex: 10,
          backdropFilter: 'blur(8px)'
        }}>
          <div style={{ fontSize: '0.62rem', fontWeight: 950, letterSpacing: 3, color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, padding: '0 32px 24px', opacity: 0.6 }}>
            SYSTEM_MANIFEST
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column' }}>
            {NAV.map(item => {
              const active = section === item.id;
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setSection(item.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '14px 32px', border: 'none', cursor: 'pointer',
                    background: active ? T.s2 : 'transparent',
                    color: active ? T.accent : T.text2,
                    fontSize: '0.72rem', fontFamily: T.fontMono, fontWeight: 800,
                    textAlign: 'left', width: '100%', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative', 
                    borderLeft: `4px solid ${active ? T.accent : 'transparent'}`,
                    letterSpacing: '1px'
                  }}
                  className="nav-button"
                >
                  <Icon size={16} strokeWidth={active ? 2.5 : 2} />
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {item.badge && (
                    <span style={{ fontSize: '0.55rem', fontFamily: T.fontMono, padding: '2px 8px', background: T.accent, color: '#000', fontWeight: 950 }}>{item.badge}</span>
                  )}
                  {active && <ChevronRight size={14} style={{ opacity: 0.5 }} />}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Content Area */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '64px 80px', position: 'relative', zIndex: 1 }} className="settings-scroll">
          <div style={{ maxWidth: 900, animation: 'fadeInScale 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) forwards' }}>
            {section === 'profile'       && <ProfileSection />}
            {section === 'billing'       && <BillingSection />}
          </div>
        </main>
      </div>

      <style>{`
        @keyframes fadeInScale {
          from { opacity: 0; transform: translateY(10px) scale(0.99); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .settings-scroll::-webkit-scrollbar { width: 4px; }
        .settings-scroll::-webkit-scrollbar-thumb { background: ${T.s4}; }
        .settings-scroll::-webkit-scrollbar-track { background: ${T.bg}; }
        .settings-row:hover { background: ${T.s2}44; }
        .settings-input:focus { border-color: ${T.accent} !important; box-shadow: 0 0 0 4px ${T.accent}11; }
        .nav-button:hover:not(:disabled) { padding-left: 36px !important; background: ${T.s2} !important; color: ${T.text} !important; }
      `}</style>
    </MainShell>
  );
}

// ── Shared Layout Components ──────────────────────────────

function PageTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{ 
      marginBottom: 64, 
      position: 'relative',
      paddingTop: 40,
      borderBottom: `2px solid ${T.text}`,
      paddingBottom: 32
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ fontSize: '0.58rem', fontFamily: T.fontMono, color: T.text3, fontWeight: 950, letterSpacing: '2px' }}>
          SYS_MOD_778 // {title.replace('_', ' ')}
        </div>
        <div style={{ flex: 1, height: 1, background: T.border, opacity: 0.3 }} />
        <div style={{ display: 'flex', gap: 4 }}>
          {[1, 2, 3].map(i => <div key={i} style={{ width: 3, height: 3, background: T.accent, opacity: 1 - i * 0.2 }} />)}
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <h1 style={{ 
          fontFamily: T.fontHead, fontWeight: 950, fontSize: '3.6rem', 
          color: T.text, margin: 0, textTransform: 'uppercase', 
          letterSpacing: '-3px', lineHeight: 0.85, marginBottom: 12
        }}>{title}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ height: 2, width: 60, background: T.accent }} />
          <p style={{ 
            fontSize: '0.85rem', color: T.text2, margin: 0, 
            fontFamily: T.fontMono, fontWeight: 800, 
            textTransform: 'uppercase', letterSpacing: '4px' 
          }}>{sub}</p>
        </div>
      </div>
      
      {/* Dynamic scanline effect */}
      <div style={{ 
        position: 'absolute', bottom: -1, left: 0, width: '40%', height: 2, 
        background: `linear-gradient(90deg, ${T.accent}, transparent)`,
        animation: 'scanlineMove 3s infinite linear' 
      }} />
      <style>{`
        @keyframes scanlineMove {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(250%); }
        }
      `}</style>
    </div>
  );
}

function Card({ children, style, title }: { children: React.ReactNode; style?: React.CSSProperties; title?: string }) {
  return (
    <div style={{
      background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0,
      padding: '0', marginBottom: 48, position: 'relative',
      boxShadow: `20px 20px 60px ${T.bg}44`,
      ...style,
    }}>
      {title && (
        <div style={{ 
          padding: '16px 32px', borderBottom: `1px solid ${T.border}`, 
          background: `linear-gradient(90deg, ${T.s2}, transparent)`, 
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 8, height: 8, border: `1.5px solid ${T.accent}`, transform: 'rotate(45deg)' }} />
            <span style={{ fontSize: '0.65rem', fontWeight: 950, fontFamily: T.fontMono, color: T.text, letterSpacing: '3px', textTransform: 'uppercase' }}>{title}</span>
          </div>
          <div style={{ fontSize: '0.5rem', fontFamily: T.fontMono, color: T.text3, opacity: 0.5 }}>LGR_PROTO_V.4.6</div>
        </div>
      )}
      <div style={{ padding: '32px 40px' }}>
        {children}
      </div>
    </div>
  );
}

function Row({ label, sub, children, noBorder }: { label: string; sub?: string; children: React.ReactNode; noBorder?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 0', borderBottom: noBorder ? 'none' : `1px solid ${T.border}` }} className="settings-row">
      <div style={{ flex: 1, paddingRight: 32 }}>
        <div style={{ fontSize: '0.75rem', color: T.text, fontFamily: T.fontMono, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
        {sub && <div style={{ fontSize: '0.65rem', color: T.text3, fontFamily: T.fontMono, marginTop: 4, fontWeight: 500, letterSpacing: '0.2px' }}>{sub}</div>}
      </div>
      <div style={{ flexShrink: 0 }}>{children}</div>
    </div>
  );
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <div onClick={onToggle} style={{
      width: 44, height: 22, borderRadius: 0,
      background: on ? T.accent : T.s4,
      cursor: 'pointer', position: 'relative', flexShrink: 0, transition: 'all 0.2s',
      border: `1px solid ${T.border}`,
    }}>
      <div style={{ position: 'absolute', width: 16, height: 16, borderRadius: 0, background: '#000', top: 2, left: on ? 24 : 2, transition: 'all 0.2s' }} />
    </div>
  );
}

function TextInput({ value, onChange, placeholder, type = 'text', width = 280, readOnly }: { value: string; onChange?: (v: string) => void; placeholder?: string; type?: string; width?: number | string; readOnly?: boolean }) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange?.(e.target.value)}
      placeholder={placeholder}
      readOnly={readOnly}
      className="settings-input"
      style={{
        width, padding: '10px 16px', borderRadius: 0,
        background: readOnly ? T.s2 : T.s1, border: `1px solid ${T.border}`,
        color: readOnly ? T.text3 : T.text, fontSize: '0.72rem', fontFamily: T.fontMono,
        outline: 'none', transition: 'all 0.15s', fontWeight: 600,
        cursor: readOnly ? 'not-allowed' : 'text'
      }}
    />
  );
}

function SaveBtn({ label = 'COMMIT CHANGES', onClick, loading }: { label?: string; onClick?: () => void; loading?: boolean }) {
  return (
    <button onClick={onClick} disabled={loading} style={{
      marginTop: 24, padding: '12px 32px', borderRadius: 0, border: 'none',
      background: T.accent, color: '#000', fontSize: '0.7rem', fontFamily: T.fontMono,
      cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 900, transition: 'all 0.15s',
      textTransform: 'uppercase', letterSpacing: '1.5px',
    }}
      onMouseEnter={e => { if(!loading) e.currentTarget.style.filter = 'brightness(1.1)'; }}
      onMouseLeave={e => { if(!loading) e.currentTarget.style.filter = 'none'; }}
    >
      {loading ? 'EXECUTING...' : label}
    </button>
  );
}

// ── Profile ───────────────────────────────────────────────

function ProfileSection() {
  const { settings, updateSetting } = useSettingsStore();
  const { user, signOut } = useAuth();
  const defaultNameFromEmail = user?.email ? user.email.split('@')[0] : '';
  const [name, setName] = useState(settings?.full_name || defaultNameFromEmail);
  const [role, setRole] = useState(settings?.job_title || '');
  const [timezone, setTimezone] = useState(settings?.timezone || 'UTC');

  const handleSave = () => {
    updateSetting({ full_name: name, job_title: role, timezone });
  };

  const handleSignOut = async () => {
    await signOut();
    window.location.href = '/auth';
  };

  return (
    <>
      <PageTitle title="USER_PROFILE" sub="IDENTITY AND REGION CONFIGURATION" />

      <Card title="ACCOUNT IDENTITY">
        <div style={{ display: 'flex', alignItems: 'center', gap: 32, paddingBottom: 32, borderBottom: `1px solid ${T.border}`, marginBottom: 8 }}>
          <div style={{
            width: 80, height: 80, borderRadius: 0,
            background: T.s2, border: `1px solid ${T.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.8rem', fontWeight: 900, color: T.text, fontFamily: T.fontMono, flexShrink: 0,
          }}>
            {name ? name.substring(0, 2).toUpperCase() : (user?.email?.substring(0, 2).toUpperCase() || 'U')}
          </div>
          <div>
            <div style={{ fontSize: '0.65rem', color: T.text3, marginBottom: 12, fontFamily: T.fontMono, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>AVATAR_SYSTEM_ACTIVE</div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button style={{ padding: '8px 16px', borderRadius: 0, border: `1px solid ${T.border}`, background: T.accent, color: '#000', fontSize: '0.62rem', fontFamily: T.fontMono, cursor: 'pointer', fontWeight: 900, textTransform: 'uppercase' }}>UPLOAD_NEW</button>
              <button style={{ padding: '8px 16px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text3, fontSize: '0.62rem', fontFamily: T.fontMono, cursor: 'pointer', fontWeight: 700, textTransform: 'uppercase' }}>PURGE</button>
            </div>
          </div>
        </div>

        <Row label="LEGAL_NAME" sub="Display name for workspace and reports">
          <TextInput value={name} onChange={setName} placeholder="IDENTIFIER" />
        </Row>
        <Row label="EMAIL_CHANNEL" sub="Managed securely via Supabase Auth">
          <TextInput value={user?.email || 'AWAITING_AUTH'} readOnly width={280} />
        </Row>
        <Row label="FUNCTIONAL_ROLE" sub="Used for AI personalization">
          <TextInput value={role} onChange={setRole} placeholder="e.g. SYSTEM_ARCHITECT" />
        </Row>
        <Row label="TEMPORAL_ZONE" sub="Standard offset for query scheduling" noBorder>
          <select 
            value={timezone}
            onChange={e => setTimezone(e.target.value)}
            style={{ width: 280, padding: '10px 16px', borderRadius: 0, background: T.s1, border: `1px solid ${T.border}`, color: T.text, fontSize: '0.72rem', fontFamily: T.fontMono, outline: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            <option value="Asia/Karachi">KARACHI (UTC+5)</option>
            <option value="UTC">UTC (GMT+0)</option>
            <option value="America/New_York">NEW_YORK (UTC−5)</option>
            <option value="Europe/London">LONDON (UTC+0)</option>
            <option value="Asia/Kolkata">KOLKATA (UTC+5:30)</option>
          </select>
        </Row>
      </Card>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 40 }}>
        <SaveBtn onClick={handleSave} />
        <button 
          onClick={handleSignOut}
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '12px 24px', borderRadius: 0, border: `1px solid ${T.red}`,
            background: 'transparent', color: T.red, fontSize: '0.68rem', fontFamily: T.fontMono, cursor: 'pointer', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px'
          }}
        >
          <LogOut size={14} />
          TERMINATE_SESSION
        </button>
      </div>
    </>
  );
}
// ── Security (Mocked) ──────────────────────────────────────

export function SecuritySection() {
  const [twoFa, setTwoFa] = useState(false);
  const [sessions] = useState([
    { device: 'CHROME_ON_WINDOWS', location: 'KARACHI, PK', last: 'ACTIVE_NOW', current: true, icon: Monitor },
    { device: 'SAFARI_ON_IOS', location: 'DUBAI, AE', last: '2_HOURS_AGO', current: false, icon: Smartphone },
  ]);

  return (
    <>
      <PageTitle title="SECURITY_PROTOCOL" sub="ACCESS CONTROL AND SESSION MONITORING" />

      <Card title="MULTI-FACTOR AUTHENTICATION">
        <Row label="AUTHENTICATOR_APP" sub="Use Google Authenticator or hardware tokens" noBorder>
          <Toggle on={twoFa} onToggle={() => setTwoFa(!twoFa)} />
        </Row>
      </Card>

      <Card title="ACTIVE_SESSION_LOG">
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sessions.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '20px 0', borderBottom: i < sessions.length - 1 ? `1px solid ${T.border}` : 'none' }}>
              <div style={{ width: 44, height: 44, borderRadius: 0, background: T.s2, border: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: T.text2 }}>
                <s.icon size={18} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.72rem', color: T.text, fontFamily: T.fontMono, fontWeight: 900, display: 'flex', alignItems: 'center', gap: 8, letterSpacing: '0.5px' }}>
                  {s.device}
                  {s.current && <span style={{ fontSize: '0.55rem', fontFamily: T.fontMono, padding: '2px 6px', background: T.greenDim, color: T.green, border: `1px solid ${T.green}44`, fontWeight: 900 }}>CURRENT</span>}
                </div>
                <div style={{ fontSize: '0.65rem', color: T.text3, fontFamily: T.fontMono, marginTop: 4, fontWeight: 500, letterSpacing: '0.2px' }}>{s.location} · {s.last}</div>
              </div>
              <button style={{ padding: '6px 12px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text3, fontSize: '0.6rem', fontFamily: T.fontMono, fontWeight: 800, cursor: 'pointer', textTransform: 'uppercase' }}>REVOKE</button>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ── AI Engine & Queries ───────────────────────────────────

export function AISection() {
  const { settings, updateSetting } = useSettingsStore();
  const [prompt, setPrompt] = useState(settings?.system_prompt || '');
  const [saving, setSaving] = useState(false);

  if (!settings) return null;

  const handleSavePrompt = async () => {
    setSaving(true);
    await updateSetting({ system_prompt: prompt });
    setSaving(false);
  };

  return (
    <>
      <PageTitle title="AI_ENGINE_CONFIG" sub="NEURAL MODEL AND QUERY DISPATCH PARAMETERS" />

      <Card title="MODEL_SPECIFICATIONS">
        <Row label="PRIMARY_LLM" sub="Generative model for SQL synthesis">
          <select
            value={settings.ai_model}
            onChange={e => updateSetting({ ai_model: e.target.value })}
            style={{ width: 280, padding: '10px 16px', borderRadius: 0, background: T.s1, border: `1px solid ${T.border}`, color: T.text, fontSize: '0.72rem', fontFamily: T.fontMono, outline: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            <option value="claude-sonnet-4-6">CLAUDE_SONNET_4.6</option>
            <option value="claude-opus-4-6">CLAUDE_OPUS_4.6</option>
            <option value="claude-haiku-4-5">CLAUDE_HAIKU_4.5</option>
            <option value="gpt-4o">GPT_4O_LATEST</option>
          </select>
        </Row>
        <Row label="STREAM_RESPONSES" sub="Real-time token dispatch for lower latency" noBorder>
          <Toggle on={settings.stream_responses} onToggle={() => updateSetting({ stream_responses: !settings.stream_responses })} />
        </Row>
      </Card>

      <Card title="EXECUTION_LIMITS">
        <Row label="DEFAULT_ROW_LIMIT" sub="Maximum entities returned per query cycle">
          <select
            value={settings.default_row_limit.toString()}
            onChange={e => updateSetting({ default_row_limit: parseInt(e.target.value, 10) })}
            style={{ width: 140, padding: '10px 16px', borderRadius: 0, background: T.s1, border: `1px solid ${T.border}`, color: T.text, fontSize: '0.72rem', fontFamily: T.fontMono, outline: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            {['100', '250', '500', '1000', '5000'].map(v => (
              <option key={v} value={v}>{v} ROWS</option>
            ))}
          </select>
        </Row>
        <Row label="AUTO_ARCHIVE" sub="Persist all AI-generated queries to Library" noBorder>
          <Toggle on={settings.auto_save_queries} onToggle={() => updateSetting({ auto_save_queries: !settings.auto_save_queries })} />
        </Row>
      </Card>

      <Card title="SYSTEM_INSTRUCTIONS">
        <div style={{ fontSize: '0.65rem', color: T.text3, marginBottom: 16, fontFamily: T.fontMono, lineHeight: 1.6, fontWeight: 500 }}>
          CONTEXTUAL OVERRIDE: THESE INSTRUCTIONS ARE INJECTED INTO EVERY AI DISPATCH. USE THIS TO DEFINE BUSINESS LOGIC, FISCAL CALENDARS, OR DATA PRIVACY RULES.
        </div>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="e.g. FISCAL_YEAR_START: APRIL_1. IGNORE_SOFT_DELETES: TRUE."
          style={{
            width: '100%', minHeight: 140, background: T.s2, border: `1px solid ${T.border}`,
            borderRadius: 0, padding: '16px', fontFamily: T.fontMono, fontSize: '0.72rem',
            lineHeight: 1.8, color: T.text, outline: 'none', resize: 'vertical', boxSizing: 'border-box',
            fontWeight: 500,
          }}
          className="settings-input"
        />
        <SaveBtn onClick={handleSavePrompt} loading={saving} />
      </Card>
    </>
  );
}

// ── Notifications (Alerts) ────────────────────────────────

export function NotificationsSection() {
  const { settings, updateSetting } = useSettingsStore();
  const [webhook, setWebhook] = useState(settings?.slack_webhook || '');
  const [channel, setChannel] = useState(settings?.slack_channel || '');

  if (!settings) return null;

  return (
    <>
      <PageTitle title="ALERT_DISPATCH" sub="COMMUNICATION CHANNELS AND TRIGGER EVENTS" />

      <Card title="EMAIL_NOTIFICATION_SYSTEM">
        <Row label="SCHEDULED_REPORTS" sub="Receive detailed result sets via email">
          <Toggle on={settings.email_scheduled} onToggle={() => updateSetting({ email_scheduled: !settings.email_scheduled })} />
        </Row>
        <Row label="EXECUTION_FAILURE_LOGS" sub="Notify on pipeline or query errors">
          <Toggle on={settings.email_failed} onToggle={() => updateSetting({ email_failed: !settings.email_failed })} />
        </Row>
        <Row label="THRESHOLD_ALERTS" sub="Notify when data conditions are met">
          <Toggle on={settings.email_alerts} onToggle={() => updateSetting({ email_alerts: !settings.email_alerts })} />
        </Row>
        <Row label="PAYLOAD_FORMAT" noBorder>
          <select 
            value={settings.delivery_format}
            onChange={e => updateSetting({ delivery_format: e.target.value })}
            style={{ width: 220, padding: '10px 16px', borderRadius: 0, background: T.s1, border: `1px solid ${T.border}`, color: T.text, fontSize: '0.72rem', fontFamily: T.fontMono, outline: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            <option value="CSV + Chart PNG">CSV + CHART_PNG</option>
            <option value="CSV only">CSV_ONLY</option>
            <option value="Summary only">TEXT_SUMMARY</option>
          </select>
        </Row>
      </Card>

      <Card title="SLACK_BRIDGE_INTEGRATION">
        <Row label="ENABLE_SLACK_WEBHOOKS">
          <Toggle on={settings.slack_enabled} onToggle={() => updateSetting({ slack_enabled: !settings.slack_enabled })} />
        </Row>
        {settings.slack_enabled && (
          <>
            <Row label="WEBHOOK_URL" sub="Standard Slack incoming webhook URL">
              <TextInput value={webhook} onChange={setWebhook} placeholder="HTTPS://HOOKS.SLACK.COM/..." width={320} />
            </Row>
            <Row label="TARGET_CHANNEL" sub="Broadcast destination">
              <TextInput value={channel} onChange={setChannel} placeholder="#DATA_ALERTS" width={220} />
            </Row>
          </>
        )}
        <SaveBtn onClick={() => updateSetting({ slack_webhook: webhook, slack_channel: channel })} />
      </Card>
    </>
  );
}

// ── API Access ────────────────────────────────────────────

export function ApiKeysSection() {
  const [keys] = useState([
    { name: 'PRODUCTION_DASHBOARD', prefix: 'QM_LIVE_4XK9', created: 'JAN_12_2026', last: '2_HOURS_AGO', scopes: ['READ', 'EXECUTE'] },
  ]);

  return (
    <>
      <PageTitle title="API_ACCESS_MANIFEST" sub="PROGRAMMATIC INTERFACE CONTROL" />

      <Card title="ACTIVE_ACCESS_TOKENS">
        {keys.map((k, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '24px 0', borderBottom: i < keys.length - 1 ? `1px solid ${T.border}` : 'none' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: T.text, fontWeight: 900, marginBottom: 8, fontFamily: T.fontMono, letterSpacing: '1px' }}>{k.name}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <code style={{ fontFamily: T.fontMono, fontSize: '0.72rem', color: T.accent, background: T.accentDim, padding: '4px 10px', fontWeight: 800 }}>{k.prefix}••••••••••••</code>
                <span style={{ fontSize: '0.6rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 600 }}>LAST_ACTIVE: {k.last}</span>
              </div>
            </div>
            <button style={{ padding: '8px 16px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.red, fontSize: '0.65rem', fontFamily: T.fontMono, fontWeight: 900, cursor: 'pointer', textTransform: 'uppercase' }}>REVOKE</button>
          </div>
        ))}
        {keys.length === 0 && <div style={{ padding: 40, textAlign: 'center', color: T.text3, fontFamily: T.fontMono, fontSize: '0.7rem' }}>NO ACTIVE KEYS FOUND</div>}
      </Card>
      
      <Card title="SECURITY_ADVISORY" style={{ background: T.yellowDim, borderColor: `${T.yellow}33` }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <AlertTriangle size={18} color={T.yellow} style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: '0.68rem', color: T.yellow, lineHeight: 1.8, fontFamily: T.fontMono, fontWeight: 700, letterSpacing: '0.5px' }}>
            API_GATEWAY_RESTRICTION: KEY MANAGEMENT REQUIRES ENTERPRISE_GATEWAY (KONG) AUTHORIZATION. CURRENT INTERFACE IS READ-ONLY FOR COMPLIANCE.
          </div>
        </div>
      </Card>
    </>
  );
}

// ── Billing & Entitlements ────────────────────────────────

import { getBillingInfo } from '../services/api';
import type { UserSubscription } from '../services/api';

function BillingSection() {
  const navigate = useNavigate();
  const [sub, setSub] = useState<UserSubscription | null>(null);

  useEffect(() => {
    getBillingInfo().then(setSub).catch(console.error);
  }, []);

  if (!sub) return <div style={{ color: T.text3, fontSize: '0.7rem', fontFamily: T.fontMono, padding: 40 }}>AWAITING_BILLING_TELEMETRY...</div>;

  const isPro = sub.plan_type === 'pro';

  return (
    <>
      <PageTitle title="ENTITLEMENTS" sub="SUBSCRIPTION STATUS AND RESOURCE CONSUMPTION" />

      <Card title="CURRENT_LICENSE_STATE" style={{ background: isPro ? `${T.accent}08` : T.s1, borderColor: isPro ? `${T.accent}44` : T.border }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <span style={{ fontFamily: T.fontMono, fontWeight: 900, fontSize: '1.2rem', color: isPro ? T.accent : T.text, textTransform: 'uppercase', letterSpacing: '1px' }}>
                {isPro ? 'PRO_ANNUAL' : 'FREE_TIER'}
              </span>
              {isPro && <div style={{ padding: '4px 10px', background: T.accent, color: '#000', fontSize: '0.55rem', fontWeight: 900, fontFamily: T.fontMono }}>ACTIVE_SUBSCRIPTION</div>}
            </div>
            <div style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 600 }}>{isPro ? 'BILLED_VIA_ENTERPRISE_INVOICING' : 'BASIC_LEVEL_RESOURCE_ACCESS'}</div>
          </div>
          {!isPro && (
            <button 
              onClick={() => navigate('/upgrade')}
              style={{ padding: '12px 32px', borderRadius: 0, border: 'none', background: T.accent, color: '#000', fontWeight: 900, fontSize: '0.7rem', fontFamily: T.fontMono, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px' }}
            >
              UPGRADE_SYSTEM
            </button>
          )}
        </div>
      </Card>

      <Card title="RESOURCE_CONSUMPTION">
        <UsageBar label="QUERY_CYCLES" value={sub.queries_used} max={sub.queries_limit} color={T.accent} />
        <UsageBar label="NEURAL_TOKENS" value={sub.ai_used} max={sub.ai_limit} color={T.purple} />
      </Card>
      
      <div style={{ fontSize: '0.6rem', color: T.text3, marginTop: 40, fontFamily: T.fontMono, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.7 }}>
        * BILLING_PIPELINE: MANAGED_VIA_STRIPE_CONNECT. CONTACT ADMIN FOR EXPORT_INVOICES.
      </div>
    </>
  );
}

function UsageBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: '0.68rem', color: T.text, fontFamily: T.fontMono, fontWeight: 800 }}>{label}</span>
        <span style={{ fontSize: '0.62rem', fontFamily: T.fontMono, color: T.text3, fontWeight: 700 }}>{value.toLocaleString()} / {max.toLocaleString()} [{pct}%]</span>
      </div>
      <div style={{ height: 4, borderRadius: 0, background: T.s3, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)' }} />
      </div>
    </div>
  );
}
