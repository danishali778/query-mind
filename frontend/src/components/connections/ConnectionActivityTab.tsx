import type { QueryRecord } from '../../types/api';
import type { LoadState } from '../../types/connections';
import { T } from '../dashboard/tokens';
import { ActivityRow, SectionCard, StateBlock } from './ConnectionDetailShared';

export function ConnectionActivityTab({ queryHistory, state, error }: { queryHistory: QueryRecord[]; state: LoadState; error?: string | null }) {
  return <SectionCard title="QUERY ACTIVITY" badge={`${queryHistory.length} QUERIES`}>
    {state === 'loading' && <StateBlock title="LOADING QUERY ACTIVITY" body="Retrieving recent runs for this source." />}
    {state === 'error' && <StateBlock title="QUERY ACTIVITY FAILED" body={error || 'Recent query activity could not be loaded.'} tone="error" />}
    {!['loading', 'error'].includes(state) && queryHistory.map((query, index) => <ActivityRow key={`${query.timestamp}-${index}`} success={query.success} query={query.sql || 'Query text unavailable'} duration={query.success ? `${((query.execution_time_ms || 0) / 1000).toFixed(2)}s` : 'Error'} timestamp={query.timestamp} />)}
    {!['loading', 'error'].includes(state) && queryHistory.length === 0 && <div style={{ padding: 28, textAlign: 'center', color: T.text3, font: `600 .68rem/1.6 ${T.fontMono}` }}>No queries have been executed yet. Ask a question in Chat and it will appear here.</div>}
  </SectionCard>;
}
