import { useMemo, useState, type CSSProperties } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';

import { connectDatabase, testConnection } from '../../services/api';
import type { ConnectDatabaseRequest, TestConnectionResponse } from '../../types/api';
import { T } from '../dashboard/tokens';

type InputMode = 'fields' | 'uri';
type ScopeMode = 'all' | 'allowlist';
const emptyFields = { name: '', uri: '', host: 'localhost', port: '5432', database: '', username: '', password: '', sslMode: 'require', rootCa: '', clientCert: '', clientKey: '' };
const emptySsh = { enabled: false, host: '', port: '22', username: '', password: '', privateKey: '' };

export function NewConnectionWizard({ isOpen, onClose, onSaved }: { isOpen: boolean; onClose: () => void; onSaved?: () => void }) {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<InputMode>('fields');
  const [fields, setFields] = useState(emptyFields);
  const [ssh, setSsh] = useState(emptySsh);
  const [diagnostic, setDiagnostic] = useState<TestConnectionResponse | null>(null);
  const [scopeMode, setScopeMode] = useState<ScopeMode>('all');
  const [schemas, setSchemas] = useState<string[]>([]);
  const [tables, setTables] = useState<string[]>([]);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => { setDiagnostic(null); setError(null); };
  const field = (key: keyof typeof emptyFields, value: string) => { invalidate(); setFields(current => ({ ...current, [key]: value })); };
  const sshField = (key: keyof typeof emptySsh, value: string | boolean) => { invalidate(); setSsh(current => ({ ...current, [key]: value })); };
  const payload = useMemo<ConnectDatabaseRequest>(() => {
    const common = {
      name: fields.name || undefined, db_type: 'postgresql' as const, ssl_mode: fields.sslMode,
      ssl_root_certificate: fields.rootCa || undefined, ssl_client_certificate: fields.clientCert || undefined,
      ssl_client_private_key: fields.clientKey || undefined, use_ssh: ssh.enabled,
      ...(ssh.enabled ? { ssh_host: ssh.host, ssh_port: Number(ssh.port) || 22, ssh_username: ssh.username, ssh_password: ssh.password || undefined, ssh_private_key: ssh.privateKey || undefined } : {}),
    };
    return mode === 'uri'
      ? { ...common, input_mode: 'uri', connection_uri: fields.uri }
      : { ...common, input_mode: 'fields', host: fields.host, port: Number(fields.port) || 5432, database: fields.database, username: fields.username, password: fields.password };
  }, [fields, mode, ssh]);

  const reset = () => { setStep(1); setMode('fields'); setFields(emptyFields); setSsh(emptySsh); setDiagnostic(null); setScopeMode('all'); setSchemas([]); setTables([]); setError(null); };
  const close = () => { reset(); onClose(); };
  const test = async () => {
    setTesting(true); setError(null);
    try { const result = await testConnection(payload); setDiagnostic(result); if (!result.success) setError(result.message); }
    catch (reason) { setDiagnostic(null); setError(reason instanceof Error ? reason.message : 'Connection diagnostics failed.'); }
    finally { setTesting(false); }
  };
  const save = async () => {
    if (!diagnostic?.success) return;
    setSaving(true); setError(null);
    try {
      await connectDatabase({ ...payload, scope_mode: scopeMode, included_schemas: scopeMode === 'allowlist' ? schemas : [], included_tables: scopeMode === 'allowlist' ? tables : [] });
      reset(); onSaved?.();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Connection could not be saved.'); }
    finally { setSaving(false); }
  };
  if (!isOpen) return null;

  return <div role="dialog" aria-modal="true" aria-labelledby="connection-wizard-title" style={S.overlay}>
    <div style={S.modal}>
      <header style={S.header}><div><h2 id="connection-wizard-title" style={S.title}>REGISTER POSTGRESQL SOURCE</h2><span style={S.hint}>A live test is required before saving.</span></div><button aria-label="Close" onClick={close} style={S.icon}><X size={16} /></button></header>
      <nav aria-label="Setup progress" style={S.steps}>{['CONNECTION', 'SECURITY', 'DIAGNOSTICS', 'REVIEW'].map((label, index) => <span key={label} aria-current={step === index + 1 ? 'step' : undefined} style={{ color: step >= index + 1 ? T.accent : T.text3 }}>{step > index + 1 ? 'OK' : `0${index + 1}`} {label}</span>)}</nav>
      <main style={S.body}>
        {step === 1 && <section><Title>CONNECTION INPUT</Title><div style={S.row}>{(['fields', 'uri'] as const).map(value => <button key={value} onClick={() => { invalidate(); setMode(value); }} style={mode === value ? S.active : S.secondary}>{value === 'fields' ? 'INDIVIDUAL FIELDS' : 'CONNECTION URI'}</button>)}</div><Input label="CONNECTION NAME" value={fields.name} change={value => field('name', value)} />{mode === 'uri' ? <Input label="POSTGRESQL URI" value={fields.uri} change={value => field('uri', value)} secret placeholder="postgresql://user:password@host:5432/database" /> : <div style={S.grid}><Input label="HOST" value={fields.host} change={value => field('host', value)} /><Input label="PORT" value={fields.port} change={value => field('port', value)} /><Input label="DATABASE" value={fields.database} change={value => field('database', value)} /><Input label="USERNAME" value={fields.username} change={value => field('username', value)} /><Input label="PASSWORD" value={fields.password} change={value => field('password', value)} secret /></div>}<p style={S.hint}>Use a dedicated role with CONNECT, USAGE, and SELECT only. QueryMind never tests access by writing data.</p></section>}
        {step === 2 && <section><Title>TLS & SSH</Title><label style={S.label}>TLS MODE<select value={fields.sslMode} onChange={event => field('sslMode', event.target.value)} style={S.input}><option value="disable">DISABLE (LOCAL ONLY)</option><option value="require">REQUIRE</option><option value="verify-ca">VERIFY CA</option><option value="verify-full">VERIFY FULL</option></select></label>{fields.sslMode === 'disable' && <p style={{ ...S.hint, color: T.yellow }}>TLS is disabled. Use this only for trusted local networks.</p>}{['verify-ca', 'verify-full'].includes(fields.sslMode) && <Pem label="ROOT CA CERTIFICATE" value={fields.rootCa} change={value => field('rootCa', value)} />}<div style={S.grid}><Pem label="CLIENT CERTIFICATE (OPTIONAL)" value={fields.clientCert} change={value => field('clientCert', value)} /><Pem label="CLIENT PRIVATE KEY (OPTIONAL)" value={fields.clientKey} change={value => field('clientKey', value)} /></div><label style={S.check}><input type="checkbox" checked={ssh.enabled} onChange={event => sshField('enabled', event.target.checked)} /> USE SSH TUNNEL</label>{ssh.enabled && <div style={S.grid}><Input label="SSH HOST" value={ssh.host} change={value => sshField('host', value)} /><Input label="SSH PORT" value={ssh.port} change={value => sshField('port', value)} /><Input label="SSH USERNAME" value={ssh.username} change={value => sshField('username', value)} /><Input label="SSH PASSWORD" value={ssh.password} change={value => sshField('password', value)} secret /><Pem label="SSH PRIVATE KEY" value={ssh.privateKey} change={value => sshField('privateKey', value)} /></div>}</section>}
        {step === 3 && <Diagnostics diagnostic={diagnostic} testing={testing} test={test} scopeMode={scopeMode} setScopeMode={setScopeMode} schemas={schemas} setSchemas={setSchemas} tables={tables} setTables={setTables} />}
        {step === 4 && <section><Title>REVIEW — SECRETS HIDDEN</Title><div style={S.panel}><Review label="NAME" value={fields.name || fields.database || 'PostgreSQL'} /><Review label="TARGET" value={mode === 'uri' ? 'PostgreSQL URI (hidden)' : `${fields.host}:${fields.port}/${fields.database}`} /><Review label="TLS" value={fields.sslMode} /><Review label="MUTUAL TLS" value={fields.clientCert && fields.clientKey ? 'Configured' : 'Not configured'} /><Review label="SSH" value={ssh.enabled ? `Via ${ssh.host}` : 'Disabled'} /><Review label="SCOPE" value={scopeMode === 'all' ? 'All accessible user tables' : `${schemas.length} schemas + ${tables.length} tables`} /><Review label="TEST" value={diagnostic?.success ? `Passed · ${Math.round(diagnostic.latency_ms ?? 0)} ms` : 'Not passed'} /></div></section>}
        <div aria-live="polite">{error && <div style={S.error}>{error}</div>}</div>
      </main>
      <footer style={S.footer}><button onClick={close} style={S.secondary}>CANCEL</button>{step > 1 && <button onClick={() => setStep(value => value - 1)} style={S.secondary}><ChevronLeft size={14} /> BACK</button>}{step < 4 && <button onClick={() => setStep(value => value + 1)} disabled={step === 3 && !diagnostic?.success} style={button(step !== 3 || Boolean(diagnostic?.success))}>NEXT <ChevronRight size={14} /></button>}{step === 4 && <button onClick={save} disabled={saving || !diagnostic?.success} style={button(Boolean(diagnostic?.success) && !saving)}>{saving ? 'SAVING…' : 'SAVE CONNECTION'}</button>}</footer>
    </div>
  </div>;
}

function Diagnostics({ diagnostic, testing, test, scopeMode, setScopeMode, schemas, setSchemas, tables, setTables }: { diagnostic: TestConnectionResponse | null; testing: boolean; test: () => void; scopeMode: ScopeMode; setScopeMode: (value: ScopeMode) => void; schemas: string[]; setSchemas: (value: string[]) => void; tables: string[]; setTables: (value: string[]) => void }) {
  const toggle = (values: string[], value: string, update: (next: string[]) => void) => update(values.includes(value) ? values.filter(item => item !== value) : [...values, value]);
  return <section><Title>LIVE DIAGNOSTICS</Title><button onClick={test} disabled={testing} style={button(!testing)}>{testing ? 'TESTING…' : 'RUN CONNECTION TEST'}</button>{diagnostic && <div aria-live="polite" style={{ ...S.panel, borderColor: diagnostic.success ? T.green : T.red }}><strong style={{ color: diagnostic.success ? T.green : T.red }}>{diagnostic.message}</strong><div style={S.grid}>{diagnostic.checks.map(check => <div key={check.code} style={S.checkRow}>{check.status === 'passed' ? 'OK' : 'ERR'} · {check.label}</div>)}</div><p style={S.hint}>Latency: {diagnostic.latency_ms == null ? 'N/A' : `${Math.round(diagnostic.latency_ms)} ms`} · Tables: {diagnostic.tables_found ?? 0} · PostgreSQL {diagnostic.server_version ?? 'unknown'}</p>{diagnostic.warnings.map(item => <p key={item.code} style={{ ...S.hint, color: T.yellow }}>{item.message}</p>)}{diagnostic.suggestions.map(item => <p key={item} style={S.hint}>→ {item}</p>)}</div>}{diagnostic?.success && <div style={{ marginTop: 24 }}><Title>DATA ACCESS SCOPE</Title><label style={S.label}>SCOPE<select value={scopeMode} onChange={event => setScopeMode(event.target.value as ScopeMode)} style={S.input}><option value="all">ALL ACCESSIBLE USER TABLES</option><option value="allowlist">SELECT SCHEMAS / TABLES</option></select></label>{scopeMode === 'allowlist' && <div style={S.tree}>{(diagnostic.inventory ?? []).map(schema => <div key={schema.name}><label style={S.treeItem}><input type="checkbox" checked={schemas.includes(schema.name)} onChange={() => toggle(schemas, schema.name, setSchemas)} /> <strong>{schema.name}</strong> ({schema.tables.length})</label>{schema.tables.map(table => { const qualified = `${schema.name}.${table}`; return <label key={qualified} style={S.treeItem}><input type="checkbox" checked={tables.includes(qualified)} disabled={schemas.includes(schema.name)} onChange={() => toggle(tables, qualified, setTables)} /> {table}</label>; })}</div>)}</div>}{diagnostic.inventory_truncated && <p style={{ ...S.hint, color: T.yellow }}>Inventory is truncated. You can refine scope after saving.</p>}</div>}</section>;
}

function Title({ children }: { children: string }) { return <h3 style={S.sectionTitle}>{children}</h3>; }
function Input({ label, value, change, secret, placeholder }: { label: string; value: string; change: (value: string) => void; secret?: boolean; placeholder?: string }) {
  const [visible, setVisible] = useState(false);
  return <label style={S.label}>{label}<div style={{ display: 'flex' }}><input type={secret && !visible ? 'password' : 'text'} value={value} onChange={event => change(event.target.value)} placeholder={placeholder} style={S.input} />{secret && <button type="button" aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`} onClick={() => setVisible(current => !current)} style={S.secondary}>{visible ? 'HIDE' : 'SHOW'}</button>}</div></label>;
}
function Pem({ label, value, change }: { label: string; value: string; change: (value: string) => void }) {
  return <label style={S.label}>{label}<input type="file" accept=".pem,.crt,.key,text/plain" aria-label={`Upload ${label.toLowerCase()}`} onChange={event => { const file = event.target.files?.[0]; if (file) void file.text().then(change); }} style={{ color: T.text3 }} /><textarea value={value} onChange={event => change(event.target.value)} rows={4} placeholder="-----BEGIN…-----" style={{ ...S.input, resize: 'vertical' }} /></label>;
}
function Review({ label, value }: { label: string; value: string }) { return <div style={S.review}><span style={S.hint}>{label}</span><strong>{value}</strong></div>; }
const button = (enabled: boolean): CSSProperties => ({ ...S.primary, background: enabled ? T.accent : T.s4, color: enabled ? '#000' : T.text3, cursor: enabled ? 'pointer' : 'not-allowed' });
const S: Record<string, CSSProperties> = {
  overlay: { position: 'fixed', inset: 0, zIndex: 800, background: 'rgba(6,10,18,.94)', display: 'grid', placeItems: 'center', padding: 16 }, modal: { width: 'min(860px,100%)', maxHeight: '94vh', display: 'flex', flexDirection: 'column', background: T.s1, border: `1px solid ${T.border}`, color: T.text }, header: { padding: '20px 24px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.border}` }, title: { margin: 0, font: `900 1.1rem ${T.fontHead}` }, icon: { width: 34, height: 34, background: 'transparent', color: T.text2, border: `1px solid ${T.border}`, cursor: 'pointer' }, steps: { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '14px 24px', overflowX: 'auto', borderBottom: `1px solid ${T.border}`, font: `700 .62rem ${T.fontMono}` }, body: { padding: 24, overflowY: 'auto', flex: 1 }, footer: { padding: '16px 24px', display: 'flex', justifyContent: 'flex-end', gap: 10, borderTop: `1px solid ${T.border}` }, sectionTitle: { color: T.accent, font: `800 .68rem ${T.fontMono}`, letterSpacing: 1.5, margin: '0 0 18px' }, grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 16 }, row: { display: 'flex', gap: 8, marginBottom: 20 }, label: { display: 'flex', flexDirection: 'column', gap: 7, marginBottom: 16, color: T.text3, font: `700 .62rem ${T.fontMono}` }, check: { display: 'flex', gap: 8, margin: '16px 0', color: T.text2, font: `700 .64rem ${T.fontMono}` }, input: { boxSizing: 'border-box', width: '100%', padding: '11px 12px', background: T.s2, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.fontMono }, secondary: { padding: '10px 16px', display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: `1px solid ${T.border}`, color: T.text2, cursor: 'pointer', font: `800 .64rem ${T.fontMono}` }, active: { padding: '10px 16px', border: `1px solid ${T.accent}`, color: T.accent, background: T.s2, cursor: 'pointer', font: `800 .64rem ${T.fontMono}` }, primary: { padding: '10px 18px', display: 'inline-flex', alignItems: 'center', gap: 6, border: 0, font: `900 .64rem ${T.fontMono}` }, hint: { color: T.text3, font: `400 .66rem/1.6 ${T.fontMono}` }, error: { marginTop: 18, padding: 12, border: `1px solid ${T.red}`, background: T.redDim, color: T.red, fontFamily: T.fontMono }, panel: { marginTop: 18, padding: 18, border: `1px solid ${T.border}`, background: T.s2, fontFamily: T.fontMono }, checkRow: { padding: 9, border: `1px solid ${T.border}`, color: T.text2, fontSize: '.68rem' }, tree: { maxHeight: 250, overflowY: 'auto', padding: 14, border: `1px solid ${T.border}`, background: T.s2 }, treeItem: { display: 'block', padding: '5px 8px', color: T.text2, font: `600 .68rem ${T.fontMono}` }, review: { display: 'flex', justifyContent: 'space-between', gap: 24, padding: '11px 0', borderBottom: `1px solid ${T.border}`, fontSize: '.7rem' },
};
