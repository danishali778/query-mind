import { useMemo, useState, type CSSProperties } from 'react';
import { X } from 'lucide-react';

import { connectDatabase, testConnection } from '../../services/api';
import type { ConnectDatabaseRequest, TestConnectionResponse } from '../../types/api';
import { T } from '../dashboard/tokens';

type InputMode = 'fields' | 'uri';
type ScopeMode = 'all' | 'allowlist';

const emptyFields = { name: '', uri: '', host: 'localhost', port: '5432', database: '', username: '', password: '', sslMode: 'require', rootCa: '', clientCert: '', clientKey: '' };
const emptySsh = { enabled: false, host: '', port: '22', username: '', password: '', privateKey: '' };

export function NewConnectionWizard({ isOpen, onClose, onSaved }: { isOpen: boolean; onClose: () => void; onSaved?: () => void }) {
  const [mode, setMode] = useState<InputMode>('fields');
  const [fields, setFields] = useState(emptyFields);
  const [ssh, setSsh] = useState(emptySsh);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [scopeMode, setScopeMode] = useState<ScopeMode>('all');
  const [schemas, setSchemas] = useState<string[]>([]);
  const [tables, setTables] = useState<string[]>([]);
  const [diagnostic, setDiagnostic] = useState<TestConnectionResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scopeIsValid = scopeMode === 'all' || schemas.length > 0 || tables.length > 0;

  const invalidate = () => { setDiagnostic(null); setScopeOpen(false); setScopeMode('all'); setSchemas([]); setTables([]); setError(null); };
  const updateField = (key: keyof typeof emptyFields, value: string) => { invalidate(); setFields(current => ({ ...current, [key]: value })); };
  const updateSsh = (key: keyof typeof emptySsh, value: string | boolean) => { invalidate(); setSsh(current => ({ ...current, [key]: value })); };

  const payload = useMemo<ConnectDatabaseRequest>(() => {
    const common = {
      name: fields.name || undefined,
      db_type: 'postgresql' as const,
      ssl_mode: fields.sslMode,
      ssl_root_certificate: fields.rootCa || undefined,
      ssl_client_certificate: fields.clientCert || undefined,
      ssl_client_private_key: fields.clientKey || undefined,
      use_ssh: ssh.enabled,
      ...(ssh.enabled ? { ssh_host: ssh.host, ssh_port: Number(ssh.port) || 22, ssh_username: ssh.username, ssh_password: ssh.password || undefined, ssh_private_key: ssh.privateKey || undefined } : {}),
    };
    return mode === 'uri'
      ? { ...common, input_mode: 'uri', connection_uri: fields.uri }
      : { ...common, input_mode: 'fields', host: fields.host, port: Number(fields.port) || 5432, database: fields.database, username: fields.username, password: fields.password };
  }, [fields, mode, ssh]);

  const reset = () => {
    setMode('fields'); setFields(emptyFields); setSsh(emptySsh); setAdvancedOpen(false);
    setScopeOpen(false); setScopeMode('all'); setSchemas([]); setTables([]);
    setDiagnostic(null); setTesting(false); setSaving(false); setError(null);
  };

  const close = () => { reset(); onClose(); };

  const runTest = async () => {
    setTesting(true); setError(null); setDiagnostic(null);
    try {
      const result = await testConnection(payload);
      setDiagnostic(result);
      if (!result.success) setError(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Connection diagnostics failed.');
    } finally { setTesting(false); }
  };

  const save = async () => {
    if (!diagnostic?.success || !scopeIsValid) return;
    setSaving(true); setError(null);
    try {
      await connectDatabase({ ...payload, scope_mode: scopeMode, included_schemas: scopeMode === 'allowlist' ? schemas : [], included_tables: scopeMode === 'allowlist' ? tables : [] });
      reset(); onSaved?.();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Connection could not be saved.'); }
    finally { setSaving(false); }
  };

  if (!isOpen) return null;

  return <div role="dialog" aria-modal="true" aria-labelledby="connection-wizard-title" style={styles.overlay}>
    <div style={styles.modal}>
      <header style={styles.header}>
        <div><h2 id="connection-wizard-title" style={styles.title}>CONNECT POSTGRESQL</h2><p style={{ ...styles.hint, margin: '5px 0 0' }}>Enter connection details, test access, then save.</p></div>
        <button type="button" aria-label="Close" onClick={close} style={styles.iconButton}><X size={16} /></button>
      </header>

      <main style={styles.body}>
        <section aria-labelledby="connection-details-title">
          <h3 id="connection-details-title" style={styles.sectionTitle}>CONNECTION DETAILS</h3>
          <div style={styles.modeRow}>{(['fields', 'uri'] as const).map(value => <button key={value} type="button" onClick={() => { invalidate(); setMode(value); }} style={mode === value ? styles.activeButton : styles.secondaryButton}>{value === 'fields' ? 'INDIVIDUAL FIELDS' : 'CONNECTION URI'}</button>)}</div>
          <Input label="CONNECTION NAME" value={fields.name} onChange={value => updateField('name', value)} />
          {mode === 'uri' ? <Input label="POSTGRESQL URI" value={fields.uri} onChange={value => updateField('uri', value)} secret placeholder="postgresql://user:password@host:5432/database" /> : <div style={styles.grid}>
            <Input label="HOST" value={fields.host} onChange={value => updateField('host', value)} />
            <Input label="PORT" value={fields.port} onChange={value => updateField('port', value)} />
            <Input label="DATABASE" value={fields.database} onChange={value => updateField('database', value)} />
            <Input label="USERNAME" value={fields.username} onChange={value => updateField('username', value)} />
            <Input label="PASSWORD" value={fields.password} onChange={value => updateField('password', value)} secret />
          </div>}
          <p style={styles.hint}>Use a dedicated PostgreSQL user with CONNECT, USAGE, and SELECT only. QueryMind never tests access by writing data.</p>
        </section>

        <section style={{ marginTop: 18, border: `1px solid ${T.border}` }}>
          <button type="button" aria-expanded={advancedOpen} aria-controls="advanced-connection-options" onClick={() => setAdvancedOpen(value => !value)} style={styles.disclosureButton}><span><strong>ADVANCED CONNECTION OPTIONS</strong><small>TLS certificates and SSH tunnel</small></span><span aria-hidden="true">{advancedOpen ? '−' : '+'}</span></button>
          {advancedOpen && <div id="advanced-connection-options" style={styles.disclosureBody}>
            <label style={styles.label}>TLS MODE<select value={fields.sslMode} onChange={event => updateField('sslMode', event.target.value)} style={styles.input}><option value="disable">DISABLE (LOCAL ONLY)</option><option value="require">REQUIRE</option><option value="verify-ca">VERIFY CA</option><option value="verify-full">VERIFY FULL</option></select></label>
            {fields.sslMode === 'disable' && <p style={{ ...styles.hint, color: T.yellow }}>TLS is disabled. Use this only for trusted local development.</p>}
            {['verify-ca', 'verify-full'].includes(fields.sslMode) && <Pem label="ROOT CA CERTIFICATE" value={fields.rootCa} onChange={value => updateField('rootCa', value)} />}
            <div style={styles.grid}><Pem label="CLIENT CERTIFICATE (OPTIONAL)" value={fields.clientCert} onChange={value => updateField('clientCert', value)} /><Pem label="CLIENT PRIVATE KEY (OPTIONAL)" value={fields.clientKey} onChange={value => updateField('clientKey', value)} /></div>
            <label style={styles.check}><input type="checkbox" checked={ssh.enabled} onChange={event => updateSsh('enabled', event.target.checked)} /> USE SSH TUNNEL</label>
            {ssh.enabled && <div style={styles.grid}><Input label="SSH HOST" value={ssh.host} onChange={value => updateSsh('host', value)} /><Input label="SSH PORT" value={ssh.port} onChange={value => updateSsh('port', value)} /><Input label="SSH USERNAME" value={ssh.username} onChange={value => updateSsh('username', value)} /><Input label="SSH PASSWORD" value={ssh.password} onChange={value => updateSsh('password', value)} secret /><Pem label="SSH PRIVATE KEY" value={ssh.privateKey} onChange={value => updateSsh('privateKey', value)} /></div>}
          </div>}
        </section>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 22, flexWrap: 'wrap' }}>
          <button type="button" onClick={runTest} disabled={testing} style={primaryButton(!testing)}>{testing ? 'TESTING CONNECTION…' : 'TEST CONNECTION'}</button>
          {!diagnostic && <span style={styles.hint}>A successful live test is required before saving.</span>}
        </div>

        {diagnostic && <DiagnosticResult diagnostic={diagnostic} />}

        {diagnostic?.success && <section style={{ marginTop: 18, border: `1px solid ${T.border}` }}>
          <button type="button" aria-expanded={scopeOpen} aria-controls="connection-scope-options" onClick={() => setScopeOpen(value => !value)} style={styles.disclosureButton}><span><strong>LIMIT DATA ACCESS (OPTIONAL)</strong><small>Default: all accessible user tables</small></span><span aria-hidden="true">{scopeOpen ? '−' : '+'}</span></button>
          {scopeOpen && <div id="connection-scope-options" style={styles.disclosureBody}>
            <label style={styles.label}>SCOPE<select value={scopeMode} onChange={event => setScopeMode(event.target.value as ScopeMode)} style={styles.input}><option value="all">ALL ACCESSIBLE USER TABLES</option><option value="allowlist">SELECT SCHEMAS / TABLES</option></select></label>
            {scopeMode === 'allowlist' && <ScopeTree inventory={diagnostic.inventory ?? []} schemas={schemas} tables={tables} setSchemas={setSchemas} setTables={setTables} />}
            {scopeMode === 'allowlist' && !scopeIsValid && <p style={{ ...styles.hint, color: T.yellow }}>Select at least one schema or table before saving.</p>}
            {diagnostic.inventory_truncated && <p style={{ ...styles.hint, color: T.yellow }}>Inventory is truncated. You can refine scope later from Settings.</p>}
          </div>}
        </section>}

        {diagnostic?.success && <section aria-label="Safe connection summary" style={styles.summary}>
          <SummaryRow label="NAME" value={fields.name || fields.database || 'PostgreSQL'} />
          <SummaryRow label="TARGET" value={mode === 'uri' ? 'PostgreSQL URI (hidden)' : `${fields.host}:${fields.port}/${fields.database}`} />
          <SummaryRow label="TLS" value={fields.sslMode} />
          <SummaryRow label="SSH" value={ssh.enabled ? 'Configured' : 'Disabled'} />
          <SummaryRow label="TABLES" value={String(diagnostic.tables_found ?? 0)} />
          <SummaryRow label="LATENCY" value={diagnostic.latency_ms == null ? 'N/A' : `${Math.round(diagnostic.latency_ms)} ms`} />
        </section>}

        <div aria-live="polite">{error && <div style={styles.error}>{error}</div>}</div>
      </main>

      <footer style={styles.footer}>
        <button type="button" onClick={close} style={styles.secondaryButton}>CANCEL</button>
        <button type="button" onClick={save} disabled={!diagnostic?.success || !scopeIsValid || saving} style={primaryButton(Boolean(diagnostic?.success) && scopeIsValid && !saving)}>{saving ? 'SAVING…' : 'SAVE CONNECTION'}</button>
      </footer>
    </div>
  </div>;
}

function DiagnosticResult({ diagnostic }: { diagnostic: TestConnectionResponse }) {
  return <section aria-live="polite" style={{ ...styles.diagnostic, borderColor: diagnostic.success ? T.green : T.red }}>
    <strong style={{ color: diagnostic.success ? T.green : T.red }}>{diagnostic.message}</strong>
    <div style={styles.grid}>{(diagnostic.checks ?? []).map(check => <div key={check.code} style={styles.checkRow}>{check.status === 'passed' ? 'OK' : 'ERR'} · {check.label}</div>)}</div>
    <p style={styles.hint}>Latency: {diagnostic.latency_ms == null ? 'N/A' : `${Math.round(diagnostic.latency_ms)} ms`} · Tables: {diagnostic.tables_found ?? 0} · PostgreSQL {diagnostic.server_version ?? 'unknown'}</p>
    {(diagnostic.warnings ?? []).map(item => <p key={item.code} style={{ ...styles.hint, color: T.yellow }}>{item.message}</p>)}
    {(diagnostic.suggestions ?? []).map(item => <p key={item} style={styles.hint}>→ {item}</p>)}
  </section>;
}

function ScopeTree({ inventory, schemas, tables, setSchemas, setTables }: { inventory: Array<{ name: string; tables: string[] }>; schemas: string[]; tables: string[]; setSchemas: (value: string[]) => void; setTables: (value: string[]) => void }) {
  const toggle = (values: string[], value: string, update: (next: string[]) => void) => update(values.includes(value) ? values.filter(item => item !== value) : [...values, value]);
  return <div style={styles.tree}>{inventory.map(schema => <div key={schema.name}><label style={styles.treeItem}><input type="checkbox" checked={schemas.includes(schema.name)} onChange={() => toggle(schemas, schema.name, setSchemas)} /> <strong>{schema.name}</strong> ({schema.tables.length})</label>{schema.tables.map(table => { const qualified = `${schema.name}.${table}`; return <label key={qualified} style={{ ...styles.treeItem, paddingLeft: 26 }}><input type="checkbox" checked={tables.includes(qualified)} disabled={schemas.includes(schema.name)} onChange={() => toggle(tables, qualified, setTables)} /> {table}</label>; })}</div>)}</div>;
}

function Input({ label, value, onChange, secret, placeholder }: { label: string; value: string; onChange: (value: string) => void; secret?: boolean; placeholder?: string }) {
  const [visible, setVisible] = useState(false);
  return <label style={styles.label}>{label}<div style={{ display: 'flex' }}><input type={secret && !visible ? 'password' : 'text'} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} style={styles.input} />{secret && <button type="button" aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`} onClick={() => setVisible(value => !value)} style={styles.secondaryButton}>{visible ? 'HIDE' : 'SHOW'}</button>}</div></label>;
}

function Pem({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label style={styles.label}>{label}<input type="file" accept=".pem,.crt,.key,text/plain" aria-label={`Upload ${label.toLowerCase()}`} onChange={event => { const file = event.target.files?.[0]; if (file) void file.text().then(onChange); }} style={{ color: T.text3 }} /><textarea value={value} onChange={event => onChange(event.target.value)} rows={4} placeholder="-----BEGIN…-----" style={{ ...styles.input, resize: 'vertical' }} /></label>;
}

function SummaryRow({ label, value }: { label: string; value: string }) { return <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, padding: '9px 0', borderBottom: `1px solid ${T.border}` }}><span style={styles.hint}>{label}</span><strong>{value}</strong></div>; }

const primaryButton = (enabled: boolean): CSSProperties => ({ padding: '10px 17px', border: 0, background: enabled ? T.accent : T.s4, color: enabled ? '#000' : T.text3, cursor: enabled ? 'pointer' : 'not-allowed', font: `900 .64rem ${T.fontMono}` });

const styles: Record<string, CSSProperties> = {
  overlay: { position: 'fixed', inset: 0, zIndex: 800, display: 'grid', placeItems: 'center', padding: 16, background: 'rgba(6,10,18,.94)' },
  modal: { width: 'min(820px,100%)', maxHeight: '94vh', display: 'flex', flexDirection: 'column', background: T.s1, border: `1px solid ${T.border}`, color: T.text },
  header: { display: 'flex', justifyContent: 'space-between', gap: 20, padding: '20px 24px', borderBottom: `1px solid ${T.border}` },
  title: { margin: 0, font: `900 1.1rem ${T.fontHead}` },
  iconButton: { width: 34, height: 34, background: 'transparent', color: T.text2, border: `1px solid ${T.border}`, cursor: 'pointer' },
  body: { flex: 1, overflowY: 'auto', padding: 24 },
  footer: { display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '15px 24px', borderTop: `1px solid ${T.border}` },
  sectionTitle: { margin: '0 0 16px', color: T.accent, font: `900 .68rem ${T.fontMono}`, letterSpacing: 1.3 },
  modeRow: { display: 'flex', gap: 8, marginBottom: 18 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 14 },
  label: { display: 'flex', flexDirection: 'column', gap: 7, marginBottom: 14, color: T.text3, font: `700 .62rem ${T.fontMono}` },
  input: { boxSizing: 'border-box', width: '100%', padding: '10px 12px', background: T.s2, border: `1px solid ${T.border}`, color: T.text, fontFamily: T.fontMono },
  check: { display: 'flex', gap: 8, margin: '14px 0', color: T.text2, font: `700 .64rem ${T.fontMono}` },
  hint: { color: T.text3, font: `500 .64rem/1.6 ${T.fontMono}` },
  secondaryButton: { padding: '9px 14px', display: 'inline-flex', alignItems: 'center', background: 'transparent', border: `1px solid ${T.border}`, color: T.text2, cursor: 'pointer', font: `800 .62rem ${T.fontMono}` },
  activeButton: { padding: '9px 14px', background: T.s2, border: `1px solid ${T.accent}`, color: T.accent, cursor: 'pointer', font: `800 .62rem ${T.fontMono}` },
  disclosureButton: { width: '100%', display: 'flex', justifyContent: 'space-between', gap: 16, padding: '15px 17px', textAlign: 'left', background: 'transparent', border: 0, color: T.text, cursor: 'pointer', font: `800 .64rem ${T.fontMono}` },
  disclosureBody: { padding: '16px 17px', borderTop: `1px solid ${T.border}` },
  diagnostic: { marginTop: 18, padding: 17, background: T.s2, border: `1px solid ${T.border}`, fontFamily: T.fontMono },
  checkRow: { padding: 8, marginTop: 10, color: T.text2, border: `1px solid ${T.border}`, fontSize: '.65rem' },
  summary: { marginTop: 18, padding: '6px 17px', background: T.s2, border: `1px solid ${T.border}`, font: `700 .68rem ${T.fontMono}` },
  tree: { maxHeight: 250, overflowY: 'auto', padding: 12, background: T.s2, border: `1px solid ${T.border}` },
  treeItem: { display: 'block', padding: 5, color: T.text2, font: `600 .66rem ${T.fontMono}` },
  error: { marginTop: 16, padding: 12, background: T.redDim, border: `1px solid ${T.red}`, color: T.red, fontFamily: T.fontMono },
};
