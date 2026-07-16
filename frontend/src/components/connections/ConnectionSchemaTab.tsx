import { useState } from 'react';

import type { SchemaResponse } from '../../types/api';
import type { ConnectionListItem, LoadState } from '../../types/connections';
import { T } from '../dashboard/tokens';
import { ErdDiagram } from './ErdDiagram';
import { SemanticsWorkspace } from './SemanticsWorkspace';
import { SectionCard, StateBlock } from './ConnectionDetailShared';
import { secondaryButtonStyle } from './connectionDetailUtils';

type SchemaSection = 'physical' | 'definitions';
type PhysicalView = 'tables' | 'relationships';

export function ConnectionSchemaTab({ connection, schema, state, error, onRefresh }: { connection: ConnectionListItem; schema: SchemaResponse | null; state: LoadState; error?: string | null; onRefresh?: () => Promise<void> | void }) {
  const [section, setSection] = useState<SchemaSection>('physical');
  const [view, setView] = useState<PhysicalView>('tables');
  const tables = schema?.tables ?? [];

  return <div>
    <div role="tablist" aria-label="Schema views" style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
      <SubTab id="physical" active={section === 'physical'} label="PHYSICAL SCHEMA" onSelect={() => setSection('physical')} />
      <SubTab id="definitions" active={section === 'definitions'} label="BUSINESS DEFINITIONS" onSelect={() => setSection('definitions')} />
    </div>

    {section === 'definitions' ? <div id="schema-definitions-panel" role="tabpanel" aria-labelledby="schema-definitions-tab"><SemanticsWorkspace connectionId={connection.id} schema={schema} /></div> : <div id="schema-physical-panel" role="tabpanel" aria-labelledby="schema-physical-tab" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <strong style={{ color: T.accent, font: `800 .66rem ${T.fontMono}`, letterSpacing: 1 }}>{tables.length} TABLES</strong>
        <button type="button" onClick={() => setView('tables')} style={{ ...secondaryButtonStyle, borderColor: view === 'tables' ? T.accent : T.border, color: view === 'tables' ? T.accent : T.text2 }}>TABLES</button>
        <button type="button" onClick={() => setView('relationships')} style={{ ...secondaryButtonStyle, borderColor: view === 'relationships' ? T.accent : T.border, color: view === 'relationships' ? T.accent : T.text2 }}>RELATIONSHIPS</button>
        {onRefresh && <button type="button" onClick={onRefresh} style={{ ...primaryButtonStyle, marginLeft: 'auto' }}>REFRESH SCHEMA</button>}
      </div>

      {state === 'loading' && <StateBlock title="SCHEMA REFRESH IN PROGRESS" body="Reading table and relationship metadata from the source." />}
      {state === 'error' && <StateBlock title="SCHEMA SYNC FAILED" body={error || 'Schema metadata could not be loaded.'} tone="error" actionLabel="RETRY SYNC" onAction={onRefresh} />}
      {state === 'empty' && <StateBlock title="NO TABLES DISCOVERED" body="The schema refresh completed, but no accessible tables were returned." actionLabel="REFRESH AGAIN" onAction={onRefresh} />}

      {!['loading', 'error', 'empty'].includes(state) && view === 'tables' && <SectionCard title="DATABASE TABLES" badge={`${tables.length} TABLES`}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.72rem' }}>
            <thead><tr style={{ background: T.s3 }}>{['Table', 'Rows', 'Columns'].map(label => <th key={label} style={{ padding: '12px 18px', textAlign: 'left', color: T.text3, borderBottom: `1px solid ${T.border}`, font: `700 .6rem ${T.fontMono}`, textTransform: 'uppercase' }}>{label}</th>)}</tr></thead>
            <tbody>{tables.map(table => <tr key={table.name} style={{ borderBottom: `1px solid ${T.border}` }}><td style={cellStyle(true)}>{table.name}</td><td style={cellStyle()}>{table.row_count?.toLocaleString() ?? 'N/A'}</td><td style={cellStyle()}>{table.columns.length}</td></tr>)}</tbody>
          </table>
        </div>
      </SectionCard>}

      {!['loading', 'error', 'empty'].includes(state) && view === 'relationships' && <div style={{ minHeight: 450, height: 'calc(100vh - 350px)', border: `1px solid ${T.border}` }}><ErdDiagram tables={tables} /></div>}
    </div>}
  </div>;
}

function SubTab({ id, active, label, onSelect }: { id: SchemaSection; active: boolean; label: string; onSelect: () => void }) {
  return <button id={`schema-${id}-tab`} type="button" role="tab" aria-selected={active} aria-controls={`schema-${id}-panel`} onClick={onSelect} style={{ ...secondaryButtonStyle, color: active ? T.accent : T.text3, borderColor: active ? T.accent : T.border }}>{label}</button>;
}

function cellStyle(emphasized = false) {
  return { padding: '12px 18px', color: emphasized ? T.text : T.text2, fontFamily: T.fontMono, fontWeight: emphasized ? 700 : 500 } as const;
}

const primaryButtonStyle = { padding: '8px 14px', background: T.accent, border: `1px solid ${T.accent}`, color: '#000', cursor: 'pointer', font: `900 .62rem ${T.fontMono}` } as const;
