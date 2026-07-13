import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Clock, Plus, Sparkles, X } from 'lucide-react';
import { T } from '../dashboard/tokens';
import type { SchemaResponse } from '../../types/api';
import type {
  SemanticDefinition,
  SemanticDefinitionVersion,
  SemanticImpactItem,
  SemanticKind,
  SemanticSuggestionCandidate,
  SemanticSuggestionRun,
  SemanticSummary,
} from '../../types/semantics';
import {
  cancelSemanticSuggestions,
  createSemanticDefinition,
  createSemanticVersion,
  deprecateSemanticVersion,
  getSemanticImpact,
  getSemanticSuggestions,
  getSemanticSummary,
  listSemanticDefinitions,
  startSemanticSuggestions,
  updateSemanticDraft,
  validateSemanticVersion,
  verifySemanticVersion,
} from '../../services/semantics';
import { ApiRequestError } from '../../services/http';

const KINDS: SemanticKind[] = [
  'table', 'column', 'entity', 'dimension', 'metric',
  'relationship', 'filter', 'date_policy', 'synonym',
];

const box: React.CSSProperties = { background: T.s1, border: `1px solid ${T.border}` };
const button: React.CSSProperties = {
  border: `1px solid ${T.border}`, background: T.s2, color: T.text2, padding: '8px 12px',
  fontFamily: T.fontMono, fontSize: '0.64rem', fontWeight: 800, cursor: 'pointer',
  textTransform: 'uppercase', letterSpacing: '0.06em',
};
const input: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', border: `1px solid ${T.border}`, background: T.s2,
  color: T.text, padding: '10px 12px', fontFamily: T.fontMono, fontSize: '0.72rem', outline: 'none',
};

export function SemanticsWorkspace({ connectionId, schema }: { connectionId: string; schema: SchemaResponse | null }) {
  const [summary, setSummary] = useState<SemanticSummary | null>(null);
  const [definitions, setDefinitions] = useState<SemanticDefinition[]>([]);
  const [kind, setKind] = useState<SemanticKind | ''>('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ definition?: SemanticDefinition; candidate?: SemanticSuggestionCandidate } | null>(null);
  const [selected, setSelected] = useState<SemanticDefinition | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, list] = await Promise.all([
        getSemanticSummary(connectionId),
        listSemanticDefinitions(connectionId, { kind, search }),
      ]);
      setSummary(nextSummary);
      setDefinitions(list.items);
      setSelected((current) => current ? list.items.find((item) => item.id === current.id) || null : null);
    } catch (err) {
      setError((err as Error).message || 'Semantic catalog could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [connectionId, kind, search]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap' }}>
        <div>
          <div style={{ color: T.accent, fontFamily: T.fontMono, fontSize: '0.62rem', fontWeight: 900, letterSpacing: '0.12em' }}>SEMANTIC CATALOG</div>
          <h2 style={{ margin: '8px 0 6px', color: T.text, fontFamily: T.fontHead }}>Teach QueryMind your business language</h2>
          <p style={{ margin: 0, maxWidth: 720, color: T.text3, fontSize: '0.78rem', lineHeight: 1.6 }}>
            Definitions are metadata only. They never alter your database and cannot weaken physical schema or safety protections.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" style={button} onClick={() => setSuggesting(true)}><Sparkles size={13} /> Suggest definitions</button>
          <button type="button" style={{ ...button, background: T.accent, color: T.bg }} onClick={() => setEditor({})}><Plus size={13} /> New definition</button>
        </div>
      </div>

      {summary && <SummaryCards summary={summary} />}
      {summary?.stale ? (
        <div role="status" style={{ ...box, padding: 14, marginBottom: 16, borderColor: T.yellow, color: T.yellow, fontFamily: T.fontMono, fontSize: '0.68rem' }}>
          <AlertTriangle size={14} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          {summary.stale} verified definition{summary.stale === 1 ? '' : 's'} became stale after schema drift and will not be used for new work.
        </div>
      ) : null}

      <div style={{ ...box, padding: 12, display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <select aria-label="Definition kind" value={kind} onChange={(event) => setKind(event.target.value as SemanticKind | '')} style={{ ...input, width: 190 }}>
          <option value="">ALL KINDS</option>
          {KINDS.map((item) => <option key={item} value={item}>{item.replace('_', ' ').toUpperCase()}</option>)}
        </select>
        <input aria-label="Search definitions" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="SEARCH NAME OR DESCRIPTION" style={{ ...input, flex: 1, minWidth: 220 }} />
        <button type="button" style={button} onClick={() => void load()}>Refresh</button>
      </div>

      {loading && <State text="Loading semantic catalog…" />}
      {error && <State text={error} tone="error" />}
      {!loading && !error && definitions.length === 0 && (
        <State text="No definitions yet. Create one manually or ask QueryMind for draft suggestions." />
      )}
      {!loading && definitions.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(300px, .8fr)', gap: 16, alignItems: 'start' }}>
          <div style={{ ...box }}>
            {definitions.map((definition) => (
              <DefinitionRow
                key={definition.id}
                definition={definition}
                active={selected?.id === definition.id}
                onSelect={() => setSelected(definition)}
                onEdit={() => setEditor({ definition })}
              />
            ))}
          </div>
          <DefinitionInspector connectionId={connectionId} definition={selected} onChanged={load} />
        </div>
      )}

      {editor && (
        <DefinitionEditor
          connectionId={connectionId}
          schema={schema}
          definitions={definitions}
          definition={editor.definition}
          candidate={editor.candidate}
          onClose={() => setEditor(null)}
          onSaved={async () => { setEditor(null); await load(); }}
        />
      )}
      {suggesting && (
        <SuggestionWizard
          connectionId={connectionId}
          onClose={() => setSuggesting(false)}
          onAccept={(candidate) => { setSuggesting(false); setEditor({ candidate }); }}
        />
      )}
    </div>
  );
}

function SummaryCards({ summary }: { summary: SemanticSummary }) {
  const cards = [
    ['TOTAL', summary.total, T.text], ['VERIFIED', summary.verified, T.green], ['DRAFTS', summary.draft, T.accent],
    ['INVALID', summary.invalid, T.red], ['STALE', summary.stale, T.yellow],
  ] as const;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(100px, 1fr))', gap: 10, marginBottom: 16 }}>
      {cards.map(([label, value, color]) => (
        <div key={label} style={{ ...box, padding: 14 }}>
          <div style={{ color, fontFamily: T.fontHead, fontSize: '1.4rem', fontWeight: 900 }}>{value}</div>
          <div style={{ color: T.text3, fontFamily: T.fontMono, fontSize: '0.58rem', letterSpacing: '.1em' }}>{label}</div>
        </div>
      ))}
    </div>
  );
}

function DefinitionRow({ definition, active, onSelect, onEdit }: { definition: SemanticDefinition; active: boolean; onSelect: () => void; onEdit: () => void }) {
  const current = definition.versions.find((item) => item.status === 'draft') || definition.versions.find((item) => item.status === 'verified') || definition.versions[0];
  return (
    <div onClick={onSelect} style={{ padding: '14px 16px', borderBottom: `1px solid ${T.border}`, background: active ? T.s2 : 'transparent', cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'center' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <strong style={{ color: T.text, fontSize: '0.82rem' }}>{current?.display_name || definition.key}</strong>
          <Badge text={definition.kind} color={T.purple} />
          <Badge text={current?.status || 'unknown'} color={current?.status === 'verified' ? T.green : T.accent} />
          {current?.validation_status === 'stale' && <Badge text="stale" color={T.yellow} />}
          {current?.validation_status === 'invalid' && <Badge text="invalid" color={T.red} />}
        </div>
        <div style={{ color: T.text3, fontSize: '0.68rem', marginTop: 5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{current?.description || 'No description'}</div>
      </div>
      <button type="button" style={button} onClick={(event) => { event.stopPropagation(); onEdit(); }}>Edit</button>
    </div>
  );
}

function DefinitionInspector({ connectionId, definition, onChanged }: { connectionId: string; definition: SemanticDefinition | null; onChanged: () => Promise<void> }) {
  const [impact, setImpact] = useState<SemanticImpactItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setImpact(null); }, [definition?.id]);
  if (!definition) return <div style={{ ...box, padding: 20, color: T.text3, fontSize: '0.72rem' }}>Select a definition to inspect version history and consumers.</div>;
  const loadImpact = async () => { setBusy(true); try { setImpact(await getSemanticImpact(connectionId, definition.id)); } finally { setBusy(false); } };
  const activeVerified = definition.versions.find((item) => item.status === 'verified');
  return (
    <aside style={{ ...box, padding: 16 }}>
      <div style={{ color: T.text, fontWeight: 900, marginBottom: 4 }}>{definition.key}</div>
      <div style={{ color: T.text3, fontFamily: T.fontMono, fontSize: '0.62rem', marginBottom: 16 }}>VERSION HISTORY</div>
      {definition.versions.map((version) => (
        <div key={version.id} style={{ borderTop: `1px solid ${T.border}`, padding: '12px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ color: T.text, fontFamily: T.fontMono, fontSize: '0.68rem' }}>V{version.version} · {version.status.toUpperCase()}</span>
            <span style={{ color: version.validation_status === 'valid' ? T.green : version.validation_status === 'stale' ? T.yellow : T.text3, fontFamily: T.fontMono, fontSize: '0.58rem' }}>{version.validation_status.toUpperCase()}</span>
          </div>
          {version.change_note && <div style={{ color: T.text3, fontSize: '0.66rem', marginTop: 6 }}>{version.change_note}</div>}
        </div>
      ))}
      <button type="button" style={{ ...button, width: '100%', marginTop: 8 }} onClick={() => void loadImpact()} disabled={busy}>{busy ? 'Loading…' : 'Show impact'}</button>
      {impact && <div style={{ marginTop: 12, color: T.text3, fontSize: '0.66rem' }}>{impact.length === 0 ? 'No historical consumers.' : impact.map((item) => <div key={`${item.consumer_type}-${item.consumer_id}-${item.definition_version_id}`} style={{ padding: '7px 0', borderBottom: `1px solid ${T.border}` }}>{item.consumer_type.replace('_', ' ')} · v{item.version} · {item.usage_role}</div>)}</div>}
      {activeVerified && <button type="button" style={{ ...button, width: '100%', marginTop: 10, color: T.red }} onClick={async () => { if (window.confirm('Deprecate this verified version? New runs will stop using it.')) { await deprecateSemanticVersion(connectionId, definition.id, activeVerified.version); await onChanged(); } }}>Deprecate active version</button>}
    </aside>
  );
}

function DefinitionEditor({ connectionId, schema, definitions, definition, candidate, onClose, onSaved }: {
  connectionId: string; schema: SchemaResponse | null; definitions: SemanticDefinition[];
  definition?: SemanticDefinition; candidate?: SemanticSuggestionCandidate; onClose: () => void; onSaved: () => Promise<void>;
}) {
  const initialVersion = definition?.versions.find((item) => item.status === 'draft') || definition?.versions.find((item) => item.status === 'verified') || definition?.versions[0];
  const [kind, setKind] = useState<SemanticKind>(candidate?.kind || definition?.kind || 'table');
  const [key, setKey] = useState(candidate?.key || definition?.key || '');
  const [name, setName] = useState(candidate?.display_name || initialVersion?.display_name || '');
  const [description, setDescription] = useState(candidate?.description || initialVersion?.description || '');
  const [payload, setPayload] = useState<Record<string, unknown>>(candidate?.payload || initialVersion?.payload || { kind: candidate?.kind || definition?.kind || 'table' });
  const [saved, setSaved] = useState<SemanticDefinition | null>(definition || null);
  const [changeNote, setChangeNote] = useState('');
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const draft = saved?.versions.find((item) => item.status === 'draft');
  const report = draft?.validation_report;
  const canVerify = draft?.validation_status === 'valid' && Boolean(draft.schema_hash) && (report?.warnings || []).every((warning) => acknowledged.includes(warning.code));

  const save = async () => {
    setBusy(true); setError(null);
    try {
      let result: SemanticDefinition;
      if (!saved) {
        result = await createSemanticDefinition(connectionId, { kind, key: key || undefined, display_name: name, description, payload: { ...payload, kind }, change_note: changeNote || undefined });
      } else if (draft) {
        result = await updateSemanticDraft(connectionId, saved.id, { expected_draft_revision: draft.draft_revision, display_name: name, description, payload: { ...payload, kind } });
      } else {
        result = await createSemanticVersion(connectionId, saved.id, { display_name: name, description, payload: { ...payload, kind }, change_note: changeNote || undefined });
      }
      setSaved(result);
    } catch (err) {
      const apiError = err as ApiRequestError;
      setError(apiError.code === 'semantic_definition_revision_conflict' ? 'This draft changed elsewhere. Close and reopen it before editing again.' : apiError.message);
    } finally { setBusy(false); }
  };
  const validate = async () => {
    if (!saved || !draft) return;
    setBusy(true); setError(null);
    try { setSaved(await validateSemanticVersion(connectionId, saved.id, draft.version)); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  };
  const verify = async () => {
    if (!saved || !draft || !draft.schema_hash) return;
    setBusy(true); setError(null);
    try {
      await verifySemanticVersion(connectionId, saved.id, draft.version, { expected_schema_hash: draft.schema_hash, acknowledged_warning_codes: acknowledged, change_note: changeNote || undefined });
      await onSaved();
    } catch (err) { setError((err as Error).message); setBusy(false); }
  };

  return (
    <Modal title={saved ? `Edit ${saved.key}` : 'New semantic definition'} onClose={onClose}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Field label="Kind"><select disabled={Boolean(definition)} value={kind} onChange={(event) => { const next = event.target.value as SemanticKind; setKind(next); setPayload({ kind: next }); }} style={input}>{KINDS.map((item) => <option key={item} value={item}>{item}</option>)}</select></Field>
        <Field label="Stable key"><input disabled={Boolean(definition)} value={key} onChange={(event) => setKey(event.target.value)} style={input} placeholder="revenue" /></Field>
      </div>
      <Field label="Display name"><input value={name} onChange={(event) => setName(event.target.value)} style={input} /></Field>
      <Field label="Business description"><textarea value={description} onChange={(event) => setDescription(event.target.value)} style={{ ...input, minHeight: 76, resize: 'vertical' }} /></Field>
      <KindFields kind={kind} payload={payload} setPayload={setPayload} schema={schema} definitions={definitions} />
      <Field label="Change note"><input value={changeNote} onChange={(event) => setChangeNote(event.target.value)} style={input} placeholder="Why this definition changed" /></Field>

      {report && <ValidationPanel version={draft!} acknowledged={acknowledged} setAcknowledged={setAcknowledged} />}
      {error && <div role="alert" style={{ color: T.red, background: T.redDim, padding: 10, fontSize: '0.7rem', marginTop: 10 }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 18 }}>
        <button type="button" style={button} onClick={onClose}>Close</button>
        <button type="button" style={button} disabled={busy || !name} onClick={() => void save()}>{busy ? 'Working…' : saved ? (draft ? 'Save draft' : 'Create next draft') : 'Create draft'}</button>
        {draft && <button type="button" style={button} disabled={busy} onClick={() => void validate()}>Validate & preview</button>}
        {draft && <button type="button" style={{ ...button, background: canVerify ? T.green : T.s2, color: canVerify ? T.bg : T.text3 }} disabled={!canVerify || busy} onClick={() => void verify()}>Verify version</button>}
      </div>
    </Modal>
  );
}

function ValidationPanel({ version, acknowledged, setAcknowledged }: { version: SemanticDefinitionVersion; acknowledged: string[]; setAcknowledged: (items: string[]) => void }) {
  const report = version.validation_report;
  return (
    <div aria-live="polite" style={{ ...box, padding: 14, marginTop: 14 }}>
      <div style={{ color: T.text, fontWeight: 900, fontSize: '0.72rem' }}>VALIDATION · {version.validation_status.toUpperCase()}</div>
      <div style={{ color: T.text3, fontFamily: T.fontMono, fontSize: '0.6rem', marginTop: 4 }}>SCHEMA {version.schema_hash || 'NOT VALIDATED'}</div>
      {(report.errors || []).map((finding) => <Finding key={finding.code} finding={finding} color={T.red} />)}
      {(report.warnings || []).map((finding) => (
        <label key={finding.code} style={{ display: 'flex', gap: 8, color: T.yellow, fontSize: '0.68rem', marginTop: 9 }}>
          <input type="checkbox" checked={acknowledged.includes(finding.code)} onChange={(event) => setAcknowledged(event.target.checked ? [...acknowledged, finding.code] : acknowledged.filter((code) => code !== finding.code))} />
          <span><strong>{finding.code}</strong>: {finding.message}</span>
        </label>
      ))}
      {report.preview && Object.keys(report.preview).length > 0 && <div style={{ marginTop: 10, color: T.text2, fontFamily: T.fontMono, fontSize: '0.65rem' }}>Preview: {Object.entries(report.preview).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</div>}
    </div>
  );
}

function KindFields({ kind, payload, setPayload, schema, definitions }: { kind: SemanticKind; payload: Record<string, unknown>; setPayload: (payload: Record<string, unknown>) => void; schema: SchemaResponse | null; definitions: SemanticDefinition[] }) {
  const set = (key: string, value: unknown) => setPayload({ ...payload, [key]: value });
  const tables = schema?.tables || [];
  const tableName = String(payload.table_name || payload.primary_table || payload.left_table || '');
  const columns = tables.find((table) => table.name === tableName)?.columns || [];
  const tableSelect = (key: string, label = 'Table') => <Field label={label}><select style={input} value={String(payload[key] || '')} onChange={(event) => set(key, event.target.value)}><option value="">Select table</option>{tables.map((table) => <option key={table.name} value={table.name}>{table.name}</option>)}</select></Field>;
  const columnSelect = (key: string, label = 'Column', sourceTable = tableName) => {
    const sourceColumns = tables.find((table) => table.name === sourceTable)?.columns || [];
    return <Field label={label}><select style={input} value={String(payload[key] || '')} onChange={(event) => set(key, event.target.value)}><option value="">Select column</option>{sourceColumns.map((column) => <option key={column.name} value={column.name}>{column.name} · {column.type}</option>)}</select></Field>;
  };
  const synonyms = <Field label="Synonyms (comma separated)"><input style={input} value={Array.isArray(payload.synonyms) ? payload.synonyms.join(', ') : ''} onChange={(event) => set('synonyms', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></Field>;
  if (kind === 'table') return <>{tableSelect('table_name')}<Field label="Agent visibility"><select style={input} value={String(payload.visibility || 'included')} onChange={(event) => set('visibility', event.target.value)}><option value="included">Included</option><option value="hidden">Hidden from AI</option></select></Field>{synonyms}</>;
  if (kind === 'column') return <>{tableSelect('table_name')}{columnSelect('column_name')}<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}><Field label="Semantic type"><select style={input} value={String(payload.semantic_type || 'unknown')} onChange={(event) => set('semantic_type', event.target.value)}>{['unknown','identifier','numeric','quantity','money','date','datetime','category','boolean','json','email','phone','name','address','free_text'].map((item) => <option key={item}>{item}</option>)}</select></Field><Field label="Classification"><select style={input} value={String(payload.classification || 'public')} onChange={(event) => set('classification', event.target.value)}>{['public','internal','sensitive','restricted'].map((item) => <option key={item}>{item}</option>)}</select></Field></div><div style={{ color: T.text3, fontSize: '0.65rem', margin: '-4px 0 10px' }}>Automatic sensitivity may be tightened, never weakened.</div>{synonyms}</>;
  if (kind === 'entity') return <>{tableSelect('primary_table', 'Primary table')}{columnSelect('primary_key', 'Primary key', String(payload.primary_table || ''))}{columnSelect('display_column', 'Display column', String(payload.primary_table || ''))}{synonyms}</>;
  if (kind === 'dimension') return <>{tableSelect('table_name')}{columnSelect('column_name')}<Field label="Display label"><input style={input} value={String(payload.label || '')} onChange={(event) => set('label', event.target.value)} /></Field><Field label="Format"><input style={input} value={String(payload.format || '')} onChange={(event) => set('format', event.target.value || null)} /></Field>{synonyms}</>;
  if (kind === 'relationship') return <><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>{tableSelect('left_table', 'Left table')}{columnSelect('left_column', 'Left column', String(payload.left_table || ''))}{tableSelect('right_table', 'Right table')}{columnSelect('right_column', 'Right column', String(payload.right_table || ''))}</div><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}><Field label="Cardinality"><select style={input} value={String(payload.cardinality || 'many_to_one')} onChange={(event) => set('cardinality', event.target.value)}>{['one_to_one','one_to_many','many_to_one','many_to_many'].map((item) => <option key={item}>{item}</option>)}</select></Field><Field label="Preferred join"><select style={input} value={String(payload.join_type || 'left')} onChange={(event) => set('join_type', event.target.value)}><option value="left">left</option><option value="inner">inner</option></select></Field></div><label style={{ color: T.text2, fontSize: '0.68rem' }}><input type="checkbox" checked={payload.canonical !== false} onChange={(event) => set('canonical', event.target.checked)} /> Canonical relationship</label></>;
  if (kind === 'metric') return <><Field label="Aggregate formula"><textarea style={{ ...input, minHeight: 90 }} value={String(payload.expression || '')} onChange={(event) => set('expression', event.target.value)} placeholder="SUM(orders.total_amount)" /></Field><div style={{ color: T.text3, fontSize: '0.64rem', margin: '-5px 0 10px' }}>Use fully-qualified columns and approved aggregate functions. Parsed references are checked by the backend.</div><Field label="Required tables (comma separated)"><input style={input} value={Array.isArray(payload.tables) ? payload.tables.join(', ') : ''} onChange={(event) => set('tables', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></Field><Field label="Verified relationship IDs (comma separated)"><input style={input} value={Array.isArray(payload.relationship_ids) ? payload.relationship_ids.join(', ') : ''} onChange={(event) => set('relationship_ids', event.target.value.split(',').map((item) => item.trim()).filter(Boolean))} /></Field><Field label="Display format"><select style={input} value={String(payload.display_format || 'number')} onChange={(event) => set('display_format', event.target.value)}>{['number','currency','percent','duration'].map((item) => <option key={item}>{item}</option>)}</select></Field>{synonyms}</>;
  if (kind === 'filter') return <>{tableSelect('table_name')}<Field label="Conjunction"><select style={input} value={String(payload.conjunction || 'and')} onChange={(event) => set('conjunction', event.target.value)}><option value="and">AND</option><option value="or">OR</option></select></Field><FilterConditions payload={payload} setPayload={setPayload} columns={columns.map((column) => column.name)} /></>;
  if (kind === 'date_policy') return <>{tableSelect('table_name')}{columnSelect('column_name', 'Date column')}<Field label="Business meaning"><input style={input} value={String(payload.meaning || '')} onChange={(event) => set('meaning', event.target.value)} /></Field><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}><Field label="Timezone"><input style={input} value={String(payload.timezone || 'UTC')} onChange={(event) => set('timezone', event.target.value)} /></Field><Field label="Default grain"><select style={input} value={String(payload.default_grain || 'month')} onChange={(event) => set('default_grain', event.target.value)}>{['day','week','month','quarter','year'].map((item) => <option key={item}>{item}</option>)}</select></Field></div></>;
  return <><Field label="Phrase"><input style={input} value={String(payload.phrase || '')} onChange={(event) => set('phrase', event.target.value)} /></Field><Field label="Verified target"><select style={input} value={String(payload.target_definition_id || '')} onChange={(event) => set('target_definition_id', event.target.value)}><option value="">Select definition</option>{definitions.filter((definition) => definition.versions.some((version) => version.status === 'verified')).map((definition) => <option key={definition.id} value={definition.id}>{definition.key} · {definition.kind}</option>)}</select></Field></>;
}

function FilterConditions({ payload, setPayload, columns }: { payload: Record<string, unknown>; setPayload: (payload: Record<string, unknown>) => void; columns: string[] }) {
  const conditions = Array.isArray(payload.conditions) ? payload.conditions as Array<Record<string, unknown>> : [{ column: '', operator: 'eq', value: '' }];
  const update = (index: number, key: string, value: unknown) => setPayload({ ...payload, conditions: conditions.map((condition, i) => i === index ? { ...condition, [key]: value } : condition) });
  return <Field label="Conditions">{conditions.map((condition, index) => <div key={index} style={{ display: 'grid', gridTemplateColumns: '1fr 130px 1fr auto', gap: 6, marginBottom: 7 }}><select style={input} value={String(condition.column || '')} onChange={(event) => update(index, 'column', event.target.value)}><option value="">Column</option>{columns.map((column) => <option key={column}>{column}</option>)}</select><select style={input} value={String(condition.operator || 'eq')} onChange={(event) => update(index, 'operator', event.target.value)}>{['eq','neq','in','not_in','gt','gte','lt','lte','between','is_null','is_not_null','contains','starts_with','ends_with'].map((item) => <option key={item}>{item}</option>)}</select><input style={input} value={String(condition.value ?? '')} disabled={['is_null','is_not_null'].includes(String(condition.operator))} onChange={(event) => update(index, 'value', ['in','not_in','between'].includes(String(condition.operator)) ? event.target.value.split(',').map((item) => item.trim()) : event.target.value)} /><button type="button" style={button} onClick={() => setPayload({ ...payload, conditions: conditions.filter((_, i) => i !== index) })}><X size={12} /></button></div>)}<button type="button" style={button} onClick={() => setPayload({ ...payload, conditions: [...conditions, { column: '', operator: 'eq', value: '' }] })}>Add condition</button></Field>;
}

function SuggestionWizard({ connectionId, onClose, onAccept }: { connectionId: string; onClose: () => void; onAccept: (candidate: SemanticSuggestionCandidate) => void }) {
  const [selectedKinds, setSelectedKinds] = useState<SemanticKind[]>(['metric', 'dimension', 'relationship']);
  const [context, setContext] = useState('');
  const [run, setRun] = useState<SemanticSuggestionRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = run && ['queued', 'running'].includes(run.status);
  useEffect(() => {
    if (!active || !run) return;
    const timer = window.setInterval(async () => {
      try { setRun(await getSemanticSuggestions(connectionId, run.id)); }
      catch (err) { setError((err as Error).message); }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [active, connectionId, run]);
  const start = async () => { setError(null); try { setRun(await startSemanticSuggestions(connectionId, { client_request_id: crypto.randomUUID(), requested_kinds: selectedKinds, business_context: context || undefined })); } catch (err) { setError((err as Error).message); } };
  return <Modal title="Suggest semantic definitions" onClose={onClose}>
    {!run && <><Field label="Definition kinds"><div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>{KINDS.map((kind) => <label key={kind} style={{ ...box, padding: '7px 9px', color: selectedKinds.includes(kind) ? T.accent : T.text3, fontFamily: T.fontMono, fontSize: '0.62rem' }}><input type="checkbox" checked={selectedKinds.includes(kind)} onChange={(event) => setSelectedKinds(event.target.checked ? [...selectedKinds, kind] : selectedKinds.filter((item) => item !== kind))} /> {kind}</label>)}</div></Field><Field label="Optional business context"><textarea style={{ ...input, minHeight: 90 }} value={context} onChange={(event) => setContext(event.target.value)} placeholder="How your company defines revenue, customers, lifecycle stages…" /></Field><button type="button" style={{ ...button, background: T.accent, color: T.bg }} disabled={!selectedKinds.length} onClick={() => void start()}>Start suggestion job</button></>}
    {active && <State text={`${run.status === 'queued' ? 'Queued' : 'Generating'} suggestions… You can close this dialog; the durable job will continue.`} />}
    {run?.status === 'failed' && <State tone="error" text={run.failure_message || 'Suggestion generation failed.'} />}
    {run?.status === 'cancelled' && <State text="Suggestion job cancelled." />}
    {run?.status === 'completed' && <div aria-live="polite">{run.candidates.length === 0 ? <State text="No useful candidates were found." /> : run.candidates.map((candidate, index) => <div key={`${candidate.kind}-${candidate.key}-${index}`} style={{ ...box, padding: 14, marginBottom: 10 }}><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><strong style={{ color: T.text }}>{candidate.display_name}</strong><Badge text={candidate.kind} color={T.purple} /><Badge text={candidate.structural_validation.valid ? 'structurally valid' : 'needs editing'} color={candidate.structural_validation.valid ? T.green : T.yellow} /></div><p style={{ color: T.text3, fontSize: '0.7rem', lineHeight: 1.5 }}>{candidate.rationale}</p>{candidate.structural_validation.errors.map((finding) => <Finding key={finding.code} finding={finding} color={T.red} />)}<button type="button" style={button} onClick={() => onAccept(candidate)}>Accept as draft</button></div>)}</div>}
    {error && <div role="alert" style={{ color: T.red, marginTop: 10 }}>{error}</div>}
    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>{active && <button type="button" style={{ ...button, color: T.red }} onClick={async () => run && setRun(await cancelSemanticSuggestions(connectionId, run.id))}>Cancel job</button>}<button type="button" style={button} onClick={onClose}>Close</button></div>
  </Modal>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return <div role="dialog" aria-modal="true" aria-label={title} style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.58)', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 20 }}><div style={{ width: 'min(880px, 96vw)', maxHeight: '90vh', overflowY: 'auto', background: T.bg, border: `1px solid ${T.border}`, boxShadow: '0 24px 80px rgba(0,0,0,.35)' }}><div style={{ position: 'sticky', top: 0, zIndex: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', background: T.s1, borderBottom: `1px solid ${T.border}` }}><strong style={{ color: T.text, fontFamily: T.fontHead }}>{title}</strong><button type="button" aria-label="Close" style={button} onClick={onClose}><X size={14} /></button></div><div style={{ padding: 18 }}>{children}</div></div></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label style={{ display: 'block', marginBottom: 11 }}><span style={{ display: 'block', color: T.text3, fontFamily: T.fontMono, fontSize: '0.6rem', fontWeight: 800, letterSpacing: '.08em', textTransform: 'uppercase', marginBottom: 6 }}>{label}</span>{children}</label>; }
function Badge({ text, color }: { text: string; color: string }) { return <span style={{ border: `1px solid ${color}55`, color, padding: '2px 6px', fontFamily: T.fontMono, fontSize: '0.54rem', textTransform: 'uppercase' }}>{text.replace('_', ' ')}</span>; }
function Finding({ finding, color }: { finding: { code: string; message: string }; color: string }) { return <div style={{ color, fontSize: '0.67rem', marginTop: 8 }}><strong>{finding.code}</strong>: {finding.message}</div>; }
function State({ text, tone }: { text: string; tone?: 'error' }) { return <div role={tone === 'error' ? 'alert' : 'status'} style={{ ...box, padding: 24, textAlign: 'center', color: tone === 'error' ? T.red : T.text3, fontFamily: T.fontMono, fontSize: '0.7rem' }}>{tone === 'error' ? <AlertTriangle size={15} /> : <Clock size={15} />} <span>{text}</span></div>; }
