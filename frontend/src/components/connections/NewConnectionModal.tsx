import { useState } from 'react';
import { T } from '../dashboard/tokens';
import { connectDatabase, testConnection } from '../../services/api';
import { Database, X, ChevronRight, ChevronLeft, Check, Lock, Globe, Server, FileText } from 'lucide-react';

export function NewConnectionModal({ isOpen, onClose, onSaved }: { isOpen: boolean, onClose: () => void, onSaved?: () => void }) {
  const [step, setStep] = useState(1);
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null);
  const [formData, setFormData] = useState({ name: '', host: 'localhost', port: '', database: '', username: '', password: '', ssl_mode: 'disable', readonly: true });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; tables?: number | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // SSH state
  const [sshEnabled, setSshEnabled] = useState(false);
  const [sshAuth, setSshAuth] = useState<'password' | 'key'>('password');
  const [sshData, setSshData] = useState({ ssh_host: '', ssh_port: '22', ssh_username: '', ssh_password: '', ssh_private_key: '' });

  const connectorMap: Record<string, string> = { pg: 'postgresql', my: 'mysql', sqlite: 'sqlite', sql: 'mssql', snow: 'snowflake', bq: 'bigquery', rs: 'redshift', dbx: 'databricks', xls: 'excel', gs: 'gsheets', csv: 'csv', duck: 'duckdb' };

  const buildPayload = () => ({
    db_type: connectorMap[selectedConnector || ''] || selectedConnector || '',
    host: formData.host || 'localhost',
    port: parseInt(formData.port) || 5432,
    database: formData.database,
    username: formData.username,
    password: formData.password,
    name: formData.name || undefined,
    ssl_mode: formData.ssl_mode,
    readonly: formData.readonly,
    use_ssh: sshEnabled,
    ...(sshEnabled ? {
      ssh_host: sshData.ssh_host,
      ssh_port: parseInt(sshData.ssh_port) || 22,
      ssh_username: sshData.ssh_username,
      ssh_password: sshAuth === 'password' ? sshData.ssh_password : undefined,
      ssh_private_key: sshAuth === 'key' ? sshData.ssh_private_key : undefined,
    } : {}),
  });

  const handleTest = async () => {
    setTesting(true); setTestResult(null);
    try {
      const res = await testConnection(buildPayload() as any);
      setTestResult({ success: res.success, message: res.message, tables: res.tables_found });
    } catch (e: any) {
      setTestResult({ success: false, message: e.message || 'Test failed' });
    } finally { setTesting(false); }
  };

  const handleSave = async () => {
    setSaving(true); setError(null);
    try {
      await connectDatabase(buildPayload() as any);
      onSaved?.();
      setStep(1); setSelectedConnector(null);
      setFormData({ name: '', host: 'localhost', port: '', database: '', username: '', password: '', ssl_mode: 'disable', readonly: true });
      setSshEnabled(false); setSshData({ ssh_host: '', ssh_port: '22', ssh_username: '', ssh_password: '', ssh_private_key: '' });
      setTestResult(null);
    } catch (e: any) {
      setError(e.message || 'Failed to connect');
    } finally { setSaving(false); }
  };

  if (!isOpen) return null;

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(6,10,18,0.95)', zIndex: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: T.fontBody }}>
      <div style={{ width: 720, maxHeight: '90vh', background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 0 0 1px rgba(255,255,255,0.05)' }}>
        
        {/* Header Masthead */}
        <div style={{ padding: '24px 32px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, background: T.s2 }}>
          <div>
            <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.2rem', color: T.text, fontStyle: 'italic', letterSpacing: '-0.5px' }}>SOURCE REGISTRATION</div>
            <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, textTransform: 'uppercase', marginTop: 2, letterSpacing: '1px' }}>System Node: {selectedConnector ? selectedConnector.toUpperCase() : 'PENDING'}</div>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: 0, background: 'transparent', border: `1px solid ${T.border}`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.text3, transition: 'all 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = T.text; e.currentTarget.style.color = T.text; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.text3; }}
          ><X size={16} /></button>
        </div>

        {/* Navigation Ledger */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '0 32px', background: T.s1, borderBottom: `1px solid ${T.border}` }}>
          <WizardStep num={1} label="ENGINE" active={step === 1} done={step > 1} />
          <WizardLine done={step > 1} />
          <WizardStep num={2} label="CREDENTIALS" active={step === 2} done={step > 2} />
          <WizardLine done={step > 2} />
          <WizardStep num={3} label="DISPATCH" active={step === 3} done={step > 3} />
        </div>

        {/* Body Content */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '32px' }} className="modal-body">
          
          {step === 1 && (
            <div>
              <Section label="SQL ENGINES">
                <Grid>
                  <Card icon={<Database size={20} />} name="POSTGRESQL" type="DB" selected={selectedConnector === 'pg'} onClick={() => setSelectedConnector('pg')} />
                  <Card icon={<Database size={20} />} name="MYSQL" type="DB" selected={selectedConnector === 'my'} onClick={() => setSelectedConnector('my')} />
                  <Card icon={<Server size={20} />} name="SQL SERVER" type="DB" selected={selectedConnector === 'sql'} onClick={() => setSelectedConnector('sql')} />
                  <Card icon={<Globe size={20} />} name="SQLITE" type="DB" selected={selectedConnector === 'sqlite'} onClick={() => setSelectedConnector('sqlite')} />
                </Grid>
              </Section>
              <Section label="WAREHOUSES">
                <Grid>
                  <Card icon={<Server size={20} />} name="SNOWFLAKE" type="WHS" selected={selectedConnector === 'snow'} onClick={() => setSelectedConnector('snow')} />
                  <Card icon={<Globe size={20} />} name="BIGQUERY" type="WHS" selected={selectedConnector === 'bq'} onClick={() => setSelectedConnector('bq')} />
                  <Card icon={<Database size={20} />} name="REDSHIFT" type="WHS" selected={selectedConnector === 'rs'} onClick={() => setSelectedConnector('rs')} />
                  <Card icon={<Database size={20} />} name="DATABRICKS" type="WHS" selected={selectedConnector === 'dbx'} onClick={() => setSelectedConnector('dbx')} />
                </Grid>
              </Section>
              <Section label="FLAT SOURCES">
                <Grid>
                  <Card icon={<FileText size={20} />} name="EXCEL" type="SS" selected={selectedConnector === 'xls'} onClick={() => setSelectedConnector('xls')} />
                  <Card icon={<FileText size={20} />} name="G-SHEETS" type="SS" selected={selectedConnector === 'gs'} onClick={() => setSelectedConnector('gs')} />
                  <Card icon={<FileText size={20} />} name="CSV UPLOAD" type="FILE" selected={selectedConnector === 'csv'} onClick={() => setSelectedConnector('csv')} />
                  <Card icon={<Database size={20} />} name="DUCKDB" type="EMB" selected={selectedConnector === 'duck'} onClick={() => setSelectedConnector('duck')} />
                </Grid>
              </Section>
            </div>
          )}

          {step === 2 && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 32 }}>
                <ModalInput label="CONNECTION NAME" placeholder="PROD-DATACENTER-A" value={formData.name} onChange={v => setFormData(prev => ({...prev, name: v}))} />
                <ModalInput label="HOST ADDRESS" placeholder="LOCALHOST" value={formData.host} onChange={v => setFormData(prev => ({...prev, host: v}))} />
                <ModalInput label="PORT" placeholder="5432" value={formData.port} onChange={v => setFormData(prev => ({...prev, port: v}))} />
                <ModalInput label="DATABASE NAME" placeholder="QUERYMIND_PRIMARY" value={formData.database} onChange={v => setFormData(prev => ({...prev, database: v}))} />
                <ModalInput label="USERNAME" placeholder="ADMIN" value={formData.username} onChange={v => setFormData(prev => ({...prev, username: v}))} />
                <ModalInput label="PASSWORD" placeholder="••••••••" value={formData.password} onChange={v => setFormData(prev => ({...prev, password: v}))} password />
              </div>

              <div style={{ height: 1, background: T.border, margin: '24px 0' }} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>SSL MODE</label>
                  <select value={formData.ssl_mode} onChange={e => setFormData(prev => ({...prev, ssl_mode: e.target.value}))} style={{ background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0, padding: '12px 16px', color: T.text, fontFamily: T.fontMono, fontSize: '0.72rem', outline: 'none', cursor: 'pointer', appearance: 'none' }}>
                    <option value="disable">DISABLE</option>
                    <option value="require">REQUIRE</option>
                    <option value="verify-full">VERIFY-FULL</option>
                  </select>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>ACCESS LEVEL</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, height: 44 }}>
                    <button type="button" onClick={() => setFormData(prev => ({...prev, readonly: !prev.readonly}))} style={{ width: 44, height: 22, borderRadius: 0, border: `1px solid ${T.border}`, cursor: 'pointer', background: formData.readonly ? T.accent : T.s4, position: 'relative', transition: 'all 0.2s', flexShrink: 0 }}>
                      <div style={{ position: 'absolute', top: 2, left: formData.readonly ? 24 : 2, width: 16, height: 16, borderRadius: 0, background: '#000', transition: 'left 0.2s' }} />
                    </button>
                    <span style={{ fontSize: '0.72rem', color: formData.readonly ? T.text : T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{formData.readonly ? 'READ-ONLY' : 'READ / WRITE'}</span>
                  </div>
                </div>
              </div>

              {/* SSH Toggle Section */}
              <div style={{ height: 1, background: T.border, margin: '24px 0' }} />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: sshEnabled ? 20 : 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                   <Lock size={14} color={sshEnabled ? T.accent : T.text3} />
                   <div style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: '1.2px', color: sshEnabled ? T.text : T.text3, fontFamily: T.fontMono, textTransform: 'uppercase' }}>SSH BRIDGE</div>
                </div>
                <button type="button" onClick={() => setSshEnabled(p => !p)} style={{ width: 44, height: 22, borderRadius: 0, border: `1px solid ${T.border}`, cursor: 'pointer', background: sshEnabled ? T.accent : T.s4, position: 'relative', transition: 'all 0.2s', flexShrink: 0 }}>
                  <div style={{ position: 'absolute', top: 2, left: sshEnabled ? 24 : 2, width: 16, height: 16, borderRadius: 0, background: '#000', transition: 'left 0.2s' }} />
                </button>
              </div>
              
              {sshEnabled && (
                <div style={{ background: T.s2, padding: '20px', border: `1px solid ${T.border}` }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 16 }}>
                    <ModalInput label="BASTION HOST" placeholder="BASTION.EXAMPLE.COM" value={sshData.ssh_host} onChange={v => setSshData(p => ({...p, ssh_host: v}))} />
                    <ModalInput label="PORT" placeholder="22" value={sshData.ssh_port} onChange={v => setSshData(p => ({...p, ssh_port: v}))} />
                  </div>
                  <ModalInput label="SSH USERNAME" placeholder="UBUNTU" value={sshData.ssh_username} onChange={v => setSshData(p => ({...p, ssh_username: v}))} />
                  <div style={{ display: 'flex', gap: 0, margin: '20px 0 16px' }}>
                    {(['password', 'key'] as const).map(opt => (
                      <button key={opt} type="button" onClick={() => setSshAuth(opt)} style={{ flex: 1, padding: '8px', border: `1px solid ${T.border}`, background: sshAuth === opt ? T.accent : 'transparent', color: sshAuth === opt ? '#000' : T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 900, cursor: 'pointer', transition: 'all 0.15s', textTransform: 'uppercase' }}>
                        {opt === 'password' ? 'PASSWORD' : 'RSA KEY'}
                      </button>
                    ))}
                  </div>
                  {sshAuth === 'password'
                    ? <ModalInput label="SSH PASSCODE" placeholder="••••••••" value={sshData.ssh_password} onChange={v => setSshData(p => ({...p, ssh_password: v}))} password />
                    : <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase' }}>PRIVATE KEY (.PEM)</label>
                        <textarea value={sshData.ssh_private_key} onChange={e => setSshData(p => ({...p, ssh_private_key: e.target.value}))} placeholder="-----BEGIN RSA PRIVATE KEY-----" rows={4} style={{ background: T.s1, border: `1px solid ${T.border}`, borderRadius: 0, padding: '12px 16px', color: T.text, fontFamily: T.fontMono, fontSize: '0.68rem', outline: 'none', width: '100%', resize: 'none', boxSizing: 'border-box' }} />
                      </div>
                  }
                </div>
              )}

              {error && <div style={{ marginTop: 20, padding: '12px 16px', background: T.redDim, color: T.red, fontSize: '0.68rem', border: `1px solid ${T.red}`, fontFamily: T.fontMono, fontWeight: 700 }}>{error.toUpperCase()}</div>}
            </div>
          )}

          {step === 3 && (
            <div>
              {/* Summary LEDGER */}
              <div style={{ background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0, padding: '24px', marginBottom: 24 }}>
                <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, marginBottom: 12, textTransform: 'uppercase', letterSpacing: '1px' }}>MANIFEST SUMMARY</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                   <SummaryRow label="SOURCE" val={formData.name || formData.database} />
                   <SummaryRow label="ENGINE" val={connectorMap[selectedConnector || ''] || selectedConnector || 'N/A'} />
                   <SummaryRow label="ENDPOINT" val={`${formData.host}:${formData.port || 5432}`} />
                   {sshEnabled && <SummaryRow label="SSH BRIDGE" val={sshData.ssh_host} color={T.accent} />}
                </div>
              </div>

              {/* Health Check Dispatch */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 32 }}>
                <button onClick={handleTest} disabled={testing} style={{ width: '100%', padding: '14px', borderRadius: 0, border: `1px solid ${T.accent}`, background: 'transparent', color: T.accent, fontFamily: T.fontMono, fontSize: '0.72rem', fontWeight: 900, cursor: testing ? 'not-allowed' : 'pointer', transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {testing ? 'RUNNING DIAGNOSTICS...' : 'DISPATCH HEALTH CHECK'}
                </button>

                {testResult && (
                  <div style={{ padding: '14px 20px', background: testResult.success ? T.greenDim : T.redDim, border: `1px solid ${testResult.success ? T.green : T.red}`, color: testResult.success ? T.green : T.red, fontSize: '0.7rem', fontFamily: T.fontMono, fontWeight: 800 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                       {testResult.success ? <Check size={14} /> : <X size={14} />}
                       {testResult.message.toUpperCase()}
                    </div>
                    {testResult.success && testResult.tables != null && <div style={{ marginTop: 4, marginLeft: 24, opacity: 0.8 }}>IDENTIFIED {testResult.tables} DATA ENTITIES</div>}
                  </div>
                )}
              </div>

              {/* Final Commitment */}
              <button onClick={handleSave} disabled={saving} style={{ width: '100%', padding: '16px', borderRadius: 0, border: 'none', background: saving ? T.s4 : T.accent, color: '#000', fontFamily: T.fontMono, fontSize: '0.75rem', fontWeight: 900, cursor: saving ? 'not-allowed' : 'pointer', transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '2px' }}>
                {saving ? 'COMMITTING...' : 'REGISTER SOURCE'}
              </button>
              {error && <div style={{ marginTop: 12, padding: '12px 16px', background: T.redDim, color: T.red, fontSize: '0.68rem', border: `1px solid ${T.red}`, fontFamily: T.fontMono, fontWeight: 700 }}>{error.toUpperCase()}</div>}
            </div>
          )}

        </div>

        {/* Footer Ledger */}
        <div style={{ padding: '20px 32px', borderTop: `1px solid ${T.border}`, display: 'flex', gap: 12, justifyContent: 'flex-end', flexShrink: 0, background: T.s2 }}>
          <button onClick={onClose} style={{ padding: '10px 24px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s', textTransform: 'uppercase' }}>CANCEL</button>
          
          {step > 1 && (
             <button onClick={() => setStep(step - 1)} style={{ padding: '10px 24px', borderRadius: 0, border: `1px solid ${T.border}`, background: 'transparent', color: T.text2, fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 8, textTransform: 'uppercase' }}><ChevronLeft size={14} /> BACK</button>
          )}

          <button onClick={() => { if (step < 3) { setStep(step + 1); setTestResult(null); } }} disabled={!selectedConnector || step === 3} style={{ padding: '10px 24px', borderRadius: 0, border: 'none', background: step < 3 && selectedConnector ? T.accent : T.s4, color: step < 3 && selectedConnector ? '#000' : T.text3, fontFamily: T.fontMono, fontSize: '0.68rem', fontWeight: 900, cursor: step < 3 && selectedConnector ? 'pointer' : 'not-allowed', display: step === 3 ? 'none' : 'flex', alignItems: 'center', gap: 8, textTransform: 'uppercase' }}>
            NEXT <ChevronRight size={14} />
          </button>
        </div>

      </div>
      <style>{`
        .modal-body::-webkit-scrollbar { width: 4px; }
        .modal-body::-webkit-scrollbar-thumb { background: ${T.s4}; }
      `}</style>
    </div>
  );
}

// ------------------------
// Helpers
// ------------------------

function WizardStep({ num, label, active, done }: { num: number, label: string, active: boolean, done: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 0', position: 'relative' }}>
      <div style={{ width: 22, height: 22, borderRadius: 0, border: `1px solid ${active || done ? T.accent : T.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem', fontFamily: T.fontMono, color: active || done ? '#000' : T.text3, background: active || done ? T.accent : 'transparent', fontWeight: 900, flexShrink: 0, transition: 'all 0.2s' }}>
        {done ? <Check size={12} strokeWidth={4} /> : num}
      </div>
      <span style={{ fontSize: '0.62rem', color: active || done ? T.text : T.text3, fontFamily: T.fontMono, fontWeight: 800, letterSpacing: '1px' }}>{label}</span>
      {active && <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: T.accent }} />}
    </div>
  );
}

function WizardLine({ done: _done }: { done: boolean }) {
  return <div style={{ flex: 1, height: 1, background: T.border, margin: '0 20px', opacity: 0.3 }} />
}

function Section({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <span style={{ fontSize: '0.62rem', fontWeight: 800, letterSpacing: '1.5px', textTransform: 'uppercase', color: T.accent, fontFamily: T.fontMono, marginBottom: 16, display: 'block' }}>{label}</span>
      {children}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>{children}</div>
}

function Card({ icon, name, type, selected, onClick }: { icon: React.ReactNode, name: string, type: string, selected?: boolean, onClick: () => void }) {
  return (
    <div onClick={onClick} style={{
      background: selected ? T.s2 : T.s1, border: `1px solid ${selected ? T.accent : T.border}`, borderRadius: 0,
      padding: '20px 12px', textAlign: 'center', cursor: 'pointer', transition: 'all 0.15s', position: 'relative'
    }}
    onMouseEnter={e => { if(!selected) { e.currentTarget.style.borderColor = T.text3; e.currentTarget.style.background = T.s2; } }}
    onMouseLeave={e => { if(!selected) { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.background = T.s1; } }}
    >
      <div style={{ color: selected ? T.accent : T.text3, marginBottom: 12, display: 'flex', justifyContent: 'center' }}>{icon}</div>
      <div style={{ fontSize: '0.68rem', fontWeight: 800, color: selected ? T.text : T.text2, fontFamily: T.fontMono, letterSpacing: '0.5px' }}>{name}</div>
      <div style={{ fontSize: '0.55rem', color: T.text3, fontFamily: T.fontMono, marginTop: 4, letterSpacing: '1px' }}>{type}</div>
    </div>
  );
}

function ModalInput({ label, placeholder, value, onChange, password }: { label: string, placeholder: string, value: string, onChange: (v: string) => void, password?: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label style={{ fontSize: '0.62rem', color: T.text3, fontWeight: 700, fontFamily: T.fontMono, textTransform: 'uppercase', letterSpacing: '1px' }}>{label}</label>
      <input
        type={password ? 'password' : 'text'}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          background: T.s2, border: `1px solid ${T.border}`, borderRadius: 0,
          padding: '12px 16px', color: T.text, fontFamily: T.fontMono, fontSize: '0.72rem',
          outline: 'none', width: '100%', transition: 'all 0.15s', letterSpacing: '0.5px'
        }}
        onFocus={e => e.target.style.borderColor = T.accent}
        onBlur={e => e.target.style.borderColor = T.border}
      />
    </div>
  );
}

function SummaryRow({ label, val, color }: { label: string, val: string, color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.border}`, padding: '8px 0' }}>
       <span style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, fontWeight: 700 }}>{label}</span>
       <span style={{ fontSize: '0.68rem', color: color || T.text2, fontFamily: T.fontMono, fontWeight: 900 }}>{val.toUpperCase()}</span>
    </div>
  );
}
