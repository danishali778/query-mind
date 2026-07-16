import { useState } from 'react';

import { discoverConnectionScope, previewConnectionScope, rotateConnectionCredentials, updateConnectionAutomation, updateConnectionScope } from '../../services/api';
import type { ConnectionScopePreview } from '../../types/api';
import type { ConnectionListItem } from '../../types/connections';
import { T } from '../dashboard/tokens';
import { Accordion, InfoRow, SectionCard } from './ConnectionDetailShared';
import { controlStyle, formatTimestamp, primaryButtonStyle, secondaryButtonStyle } from './connectionDetailUtils';

export function ConnectionSettingsTab({ connection, onConnectionUpdated, onDelete }: { connection: ConnectionListItem; onConnectionUpdated?: () => Promise<void> | void; onDelete?: (id: string) => void }) {
  const [transportOpen, setTransportOpen] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [automationOpen, setAutomationOpen] = useState(false);
  const [username, setUsername] = useState(connection.username || '');
  const [password, setPassword] = useState('');
  const [sslMode, setSslMode] = useState(connection.ssl_mode || 'disable');
  const [rootCa, setRootCa] = useState('');
  const [clientCert, setClientCert] = useState('');
  const [clientKey, setClientKey] = useState('');
  const [clearCertificates, setClearCertificates] = useState(false);
  const [sshUsername, setSshUsername] = useState('');
  const [sshPassword, setSshPassword] = useState('');
  const [sshPrivateKey, setSshPrivateKey] = useState('');
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [credentialMessage, setCredentialMessage] = useState<string | null>(null);

  const [scopeMode, setScopeMode] = useState<'all' | 'allowlist'>(connection.scope_mode);
  const [schemas, setSchemas] = useState<string[]>(connection.included_schemas);
  const [tables, setTables] = useState<string[]>(connection.included_tables);
  const [inventory, setInventory] = useState<Array<{ name: string; tables: string[] }>>([]);
  const [inventoryState, setInventoryState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [scopePreview, setScopePreview] = useState<ConnectionScopePreview | null>(null);
  const [scopeAcknowledged, setScopeAcknowledged] = useState(false);
  const [scopeMessage, setScopeMessage] = useState<string | null>(null);

  const [healthEnabled, setHealthEnabled] = useState(connection.health_check_enabled);
  const [healthInterval, setHealthInterval] = useState(connection.health_check_interval_minutes);
  const [refreshEnabled, setRefreshEnabled] = useState(connection.schema_refresh_enabled);
  const [refreshInterval, setRefreshInterval] = useState(connection.schema_refresh_interval_hours);
  const [automationMessage, setAutomationMessage] = useState<string | null>(null);

  const credentialDirty = Boolean(username !== (connection.username || '') || password || rootCa || clientCert || clientKey || clearCertificates || sshUsername || sshPassword || sshPrivateKey || sslMode !== (connection.ssl_mode || 'disable'));

  const saveCredentials = async () => {
    if (!credentialDirty) return;
    setSavingCredentials(true); setCredentialMessage(null);
    try {
      await rotateConnectionCredentials(connection.id, {
        expected_credential_revision: connection.credential_revision,
        ssl_mode: sslMode,
        ...(username !== (connection.username || '') ? { username } : {}),
        ...(password ? { password } : {}),
        ...(clearCertificates ? { ssl_root_certificate: null, ssl_client_certificate: null, ssl_client_private_key: null } : {
          ...(rootCa ? { ssl_root_certificate: rootCa } : {}),
          ...(clientCert ? { ssl_client_certificate: clientCert } : {}),
          ...(clientKey ? { ssl_client_private_key: clientKey } : {}),
        }),
        ...(connection.use_ssh ? {
          ...(sshUsername ? { ssh_username: sshUsername } : {}),
          ...(sshPassword ? { ssh_password: sshPassword } : {}),
          ...(sshPrivateKey ? { ssh_private_key: sshPrivateKey } : {}),
        } : {}),
      });
      setPassword(''); setRootCa(''); setClientCert(''); setClientKey(''); setClearCertificates(false);
      setSshUsername(''); setSshPassword(''); setSshPrivateKey('');
      await onConnectionUpdated?.();
      setCredentialMessage('Credentials updated and tested successfully.');
    } catch (error) {
      setCredentialMessage(error instanceof Error ? error.message : 'Credential update failed.');
    } finally { setSavingCredentials(false); }
  };

  const loadScopeInventory = async () => {
    setInventoryState('loading'); setScopeMessage(null);
    try {
      const result = await discoverConnectionScope(connection.id);
      setInventory(result.inventory);
      setInventoryState('ready');
    } catch (error) {
      setInventoryState('error');
      setScopeMessage(error instanceof Error ? error.message : 'Scope discovery failed.');
    }
  };

  const openScope = () => {
    const next = !scopeOpen;
    setScopeOpen(next);
    if (next && inventoryState === 'idle') void loadScopeInventory();
  };

  const toggle = (values: string[], value: string, update: (next: string[]) => void) => {
    update(values.includes(value) ? values.filter(item => item !== value) : [...values, value]);
    setScopePreview(null);
  };

  const previewScope = async () => {
    setScopeMessage(null);
    try {
      setScopePreview(await previewConnectionScope(connection.id, { mode: scopeMode, included_schemas: schemas, included_tables: tables }));
      setScopeAcknowledged(false);
    } catch (error) { setScopeMessage(error instanceof Error ? error.message : 'Scope preview failed.'); }
  };

  const applyScope = async () => {
    if (!scopePreview?.valid) return;
    try {
      await updateConnectionScope(connection.id, { mode: scopeMode, included_schemas: schemas, included_tables: tables, expected_scope_revision: connection.scope_revision, acknowledged_impact_codes: scopeAcknowledged ? scopePreview.impacts.map(item => item.code) : [] });
      setScopePreview(null); setScopeMessage('Data access scope updated.');
      await onConnectionUpdated?.();
    } catch (error) { setScopeMessage(error instanceof Error ? error.message : 'Scope update failed.'); }
  };

  const saveAutomation = async () => {
    setAutomationMessage(null);
    try {
      await updateConnectionAutomation(connection.id, { health_check_enabled: healthEnabled, health_check_interval_minutes: healthInterval, schema_refresh_enabled: refreshEnabled, schema_refresh_interval_hours: refreshInterval });
      await onConnectionUpdated?.();
      setAutomationMessage('Automation settings saved.');
    } catch (error) { setAutomationMessage(error instanceof Error ? error.message : 'Automation update failed.'); }
  };

  return <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
    <SectionCard title="CONNECTION SETTINGS" badge={`REVISION ${connection.credential_revision}`}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '0 24px', padding: '10px 18px' }}>
        <InfoRow label="TARGET" value={`${connection.host || 'localhost'}:${connection.port || 'N/A'}/${connection.database || 'N/A'}`} />
        <InfoRow label="USERNAME" value={connection.username || 'N/A'} />
        <InfoRow label="TLS" value={(connection.ssl_mode || 'disable').toUpperCase()} />
        <InfoRow label="ROOT CA" value={connection.has_ssl_root_certificate ? 'Stored' : 'Not configured'} />
        <InfoRow label="CLIENT CERTIFICATE" value={connection.has_ssl_client_certificate ? 'Stored' : 'Not configured'} />
        <InfoRow label="SSH" value={connection.use_ssh ? `Enabled via ${connection.ssh_host || 'configured host'}` : 'Disabled'} />
      </div>
      <div style={{ padding: '4px 18px 18px' }}>
        <CredentialField label="DATABASE USERNAME" value={username} onChange={setUsername} placeholder="PostgreSQL role" />
        <CredentialField label="NEW DATABASE PASSWORD" value={password} onChange={setPassword} secret placeholder="Leave blank to keep the current password" />
        <button type="button" onClick={saveCredentials} disabled={!credentialDirty || savingCredentials} style={{ ...primaryButtonStyle, opacity: !credentialDirty || savingCredentials ? .5 : 1 }}>{savingCredentials ? 'SAVING…' : 'SAVE CREDENTIAL CHANGES'}</button>
        {credentialMessage && <div aria-live="polite" style={messageStyle}>{credentialMessage}</div>}
      </div>
    </SectionCard>

    <div style={{ color: T.text3, font: `800 .62rem ${T.fontMono}`, letterSpacing: 1 }}>ADVANCED SETTINGS</div>
    <Accordion id="transport-security" title="TRANSPORT SECURITY" description="TLS certificates and existing SSH tunnel credentials" open={transportOpen} onToggle={() => setTransportOpen(value => !value)}>
      <div style={gridStyle}>
        <label style={labelStyle}>TLS MODE<select value={sslMode} onChange={event => setSslMode(event.target.value)} style={controlStyle}><option value="disable">DISABLE</option><option value="require">REQUIRE</option><option value="verify-ca">VERIFY CA</option><option value="verify-full">VERIFY FULL</option></select></label>
        <CredentialField label="ROOT CA CERTIFICATE" value={rootCa} onChange={setRootCa} multiline placeholder={connection.has_ssl_root_certificate ? 'Stored — paste to replace' : 'Optional'} />
        <CredentialField label="CLIENT CERTIFICATE" value={clientCert} onChange={setClientCert} multiline placeholder={connection.has_ssl_client_certificate ? 'Stored — paste to replace' : 'Optional'} />
        <CredentialField label="CLIENT PRIVATE KEY" value={clientKey} onChange={setClientKey} multiline placeholder={connection.has_ssl_client_private_key ? 'Stored — paste to replace' : 'Optional'} />
        {connection.use_ssh && <><CredentialField label="SSH USERNAME" value={sshUsername} onChange={setSshUsername} placeholder="Leave blank to keep current" /><CredentialField label="NEW SSH PASSWORD" value={sshPassword} onChange={setSshPassword} secret placeholder="Leave blank to keep current" /><CredentialField label="NEW SSH PRIVATE KEY" value={sshPrivateKey} onChange={setSshPrivateKey} multiline placeholder="Leave blank to keep current" /></>}
      </div>
      <label style={{ ...labelStyle, flexDirection: 'row', marginTop: 12 }}><input type="checkbox" checked={clearCertificates} onChange={event => setClearCertificates(event.target.checked)} /> CLEAR STORED TLS CERTIFICATES</label>
    </Accordion>

    <Accordion id="data-access-scope" title="DATA ACCESS SCOPE" description="Limit QueryMind to selected schemas and tables" open={scopeOpen} onToggle={openScope}>
      {inventoryState === 'loading' && <p style={hintStyle}>Discovering accessible schemas…</p>}
      {inventoryState === 'error' && <button type="button" onClick={() => { void loadScopeInventory(); }} style={secondaryButtonStyle}>RETRY DISCOVERY</button>}
      <label style={labelStyle}>SCOPE MODE<select value={scopeMode} onChange={event => { setScopeMode(event.target.value as 'all' | 'allowlist'); setScopePreview(null); }} style={controlStyle}><option value="all">ALL ACCESSIBLE USER TABLES</option><option value="allowlist">SELECT SCHEMAS / TABLES</option></select></label>
      {scopeMode === 'allowlist' && inventoryState === 'ready' && <div style={{ maxHeight: 300, overflowY: 'auto', padding: 12, background: T.s2, border: `1px solid ${T.border}` }}>{inventory.map(schema => <div key={schema.name}><label style={treeLabelStyle}><input type="checkbox" checked={schemas.includes(schema.name)} onChange={() => toggle(schemas, schema.name, setSchemas)} /> <strong>{schema.name}</strong></label>{schema.tables.map(table => { const qualified = `${schema.name}.${table}`; return <label key={qualified} style={{ ...treeLabelStyle, paddingLeft: 26 }}><input type="checkbox" checked={tables.includes(qualified)} disabled={schemas.includes(schema.name)} onChange={() => toggle(tables, qualified, setTables)} /> {table}</label>; })}</div>)}</div>}
      <p style={hintStyle}>Use a dedicated SELECT-only PostgreSQL role. Database grants remain the final authorization boundary.</p>
      <button type="button" onClick={previewScope} style={secondaryButtonStyle}>PREVIEW IMPACT</button>
      {scopePreview && <div style={{ marginTop: 14, padding: 12, background: T.s2, border: `1px solid ${scopePreview.valid ? T.green : T.red}`, color: T.text2, fontFamily: T.fontMono }}><div>{scopePreview.valid ? 'Scope is valid.' : scopePreview.errors.map(item => item.message).join(' ')}</div>{scopePreview.impacts.map(item => <div key={`${item.consumer_type}-${item.consumer_id}`} style={{ color: T.yellow, marginTop: 6 }}>{item.consumer_type}: {item.label}</div>)}{scopePreview.impacts.length > 0 && <label style={{ display: 'block', marginTop: 12 }}><input type="checkbox" checked={scopeAcknowledged} onChange={event => setScopeAcknowledged(event.target.checked)} /> I acknowledge these impacts</label>}<button type="button" onClick={applyScope} disabled={!scopePreview.valid || (scopePreview.impacts.length > 0 && !scopeAcknowledged)} style={{ ...primaryButtonStyle, marginTop: 12 }}>APPLY SCOPE</button></div>}
      {scopeMessage && <div aria-live="polite" style={messageStyle}>{scopeMessage}</div>}
    </Accordion>

    <Accordion id="connection-automation" title="AUTOMATION" description="Optional health checks and schema refresh schedules" open={automationOpen} onToggle={() => setAutomationOpen(value => !value)}>
      <div style={gridStyle}>
        <label style={labelStyle}><span><input type="checkbox" checked={healthEnabled} onChange={event => setHealthEnabled(event.target.checked)} /> HEALTH CHECKS</span><select value={healthInterval} onChange={event => setHealthInterval(Number(event.target.value) as 15 | 60 | 360 | 1440)} style={controlStyle}><option value={15}>15 MINUTES</option><option value={60}>HOURLY</option><option value={360}>6 HOURS</option><option value={1440}>DAILY</option></select></label>
        <label style={labelStyle}><span><input type="checkbox" checked={refreshEnabled} onChange={event => setRefreshEnabled(event.target.checked)} /> SCHEMA REFRESH</span><select value={refreshInterval} onChange={event => setRefreshInterval(Number(event.target.value) as 6 | 12 | 24 | 168)} style={controlStyle}><option value={6}>6 HOURS</option><option value={12}>12 HOURS</option><option value={24}>DAILY</option><option value={168}>WEEKLY</option></select></label>
      </div>
      <p style={hintStyle}>Next health check: {formatTimestamp(connection.next_health_check_at)} · Next schema refresh: {formatTimestamp(connection.next_schema_refresh_at)}</p>
      <button type="button" onClick={saveAutomation} style={primaryButtonStyle}>SAVE AUTOMATION</button>
      {automationMessage && <div aria-live="polite" style={messageStyle}>{automationMessage}</div>}
    </Accordion>

    <section style={{ padding: 18, background: T.redDim, border: `1px solid ${T.red}` }}>
      <h3 style={{ margin: 0, color: T.red, font: `900 .7rem ${T.fontMono}` }}>DANGER ZONE</h3>
      <p style={{ color: T.text3, font: `600 .65rem/1.6 ${T.fontMono}` }}>Disconnecting removes this source, its cached schema, and associated connection configuration from QueryMind.</p>
      <button type="button" onClick={() => onDelete?.(connection.id)} style={{ ...secondaryButtonStyle, color: T.red, borderColor: T.red }}>DISCONNECT DATABASE</button>
    </section>
  </div>;
}

function CredentialField({ label, value, onChange, secret, multiline, placeholder }: { label: string; value: string; onChange: (value: string) => void; secret?: boolean; multiline?: boolean; placeholder?: string }) {
  return <label style={labelStyle}>{label}{multiline ? <textarea rows={4} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} style={controlStyle} /> : <input type={secret ? 'password' : 'text'} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} style={controlStyle} />}</label>;
}

const labelStyle = { display: 'flex', flexDirection: 'column', gap: 7, color: T.text3, font: `700 .62rem ${T.fontMono}` } as const;
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 16, paddingTop: 16 } as const;
const hintStyle = { color: T.text3, font: `600 .63rem/1.6 ${T.fontMono}` } as const;
const treeLabelStyle = { display: 'block', padding: 5, color: T.text2, font: `600 .65rem ${T.fontMono}` } as const;
const messageStyle = { marginTop: 12, color: T.accent, font: `700 .64rem ${T.fontMono}` } as const;
