/* eslint-disable react-hooks/exhaustive-deps */
import { useState, useEffect } from 'react';
import { X, Play, Trash2, Clock, Database, FileText, Activity, Terminal } from 'lucide-react';
import { T } from '../dashboard/tokens';
import { runSavedQuery, getQueryRunHistory, setQuerySchedule, removeQuerySchedule, updateSavedQuery, listLibraryFolders } from '../../services/api';
import { highlightSqlInline, extractTablesFromSql } from '../../utils/sqlHighlight';
import type { LibraryQuery, LibraryRunResult } from '../../types/library';
import type { FolderSummary, QueryRunHistoryRecord, ScheduleConfig } from '../../types/api';

const DAYS_OF_WEEK = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] as const;
const COMMON_TIMEZONES = [
  'UTC','America/New_York','America/Chicago','America/Denver','America/Los_Angeles',
  'Europe/London','Europe/Berlin','Asia/Karachi','Asia/Kolkata','Asia/Tokyo','Australia/Sydney',
];

function defaultSchedule(): ScheduleConfig {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return { enabled: true, frequency: 'weekly', day_of_week: 'monday', day_of_month: null, hour: 9, minute: 0, timezone: COMMON_TIMEZONES.includes(tz) ? tz : 'UTC', next_run_at: null };
}

export function QueryDetailPanel({ query, onClose, onDelete, onRefresh, initialTab }: { query: LibraryQuery | null, onClose: () => void, onDelete?: (id: string) => void, onRefresh?: () => void, initialTab?: string }) {
  const [activeTab, setActiveTab] = useState<'info'|'sql'|'history'|'schedule'>('info');
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<LibraryRunResult | null>(null);
  const [runHistory, setRunHistory] = useState<QueryRunHistoryRecord[]>([]);
  const [schedDraft, setSchedDraft] = useState<ScheduleConfig>(defaultSchedule());
  const [schedSaving, setSchedSaving] = useState(false);
  const [folders, setFolders] = useState<FolderSummary[]>([]);
  const [folderDraft, setFolderDraft] = useState('');
  const [newFolderMode, setNewFolderMode] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [folderSaving, setFolderSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (!query) return;
    getQueryRunHistory(query.id).then(setRunHistory).catch(() => setRunHistory([]));
  }, [query?.id, query?.run_count]);

  useEffect(() => {
    if (!query) return;
    setSchedDraft(query.schedule ?? defaultSchedule());
  }, [query?.id]);

  useEffect(() => {
    if (!query) return;
    setFolderDraft(query.folder_name ?? 'Uncategorized');
    setNewFolderMode(false);
    setNewFolderName('');
    listLibraryFolders().then(setFolders).catch(() => {});
  }, [query?.id]);

  useEffect(() => {
    if (initialTab && ['info','sql','history','schedule'].includes(initialTab)) {
      setActiveTab(initialTab as typeof activeTab);
    }
  }, [initialTab, query?.id]);

  if (!query) return null;

  const handleRun = async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await runSavedQuery(query.id);
      setRunResult(result);
      if (result.success) {
        getQueryRunHistory(query.id).then(setRunHistory).catch(() => {});
        setActiveTab('history');
      } else {
        setActiveTab('info');
      }
      onRefresh?.();
    } catch (err: unknown) {
      const errorResult = { success: false as const, error: err instanceof Error ? err.message : String(err) };
      setRunResult(errorResult);
      setActiveTab('info');
    } finally {
      setRunning(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(query.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    onDelete?.(query.id);
    setShowDeleteConfirm(false);
  };

  const handleFolderSave = async () => {
    const name = newFolderMode ? newFolderName.trim() : folderDraft;
    if (!name || name === query.folder_name) { setNewFolderMode(false); return; }
    setFolderSaving(true);
    try {
      await updateSavedQuery(query.id, { folder_name: name });
      setNewFolderMode(false);
      onRefresh?.();
    } catch {
      // silently handle
    } finally {
      setFolderSaving(false);
    }
  };

  const timeAgo = (ts: string | null): string => {
    if (!ts) return 'Never';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const formatDate = (ts: string): string => {
    return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const tables = extractTablesFromSql(query.sql);

  return (
    <div style={{
      width: 380, flexShrink: 0, background: '#fff', borderLeft: `1px solid rgba(0,0,0,0.08)`,
      display: 'flex', flexDirection: 'column', overflow: 'hidden', fontFamily: T.fontBody
    }}>
      {/* Header */}
      <div style={{ padding: '24px 24px 16px', borderBottom: `1px solid rgba(0,0,0,0.05)`, display: 'flex', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.2rem', color: T.text, lineHeight: 1.2, fontStyle: 'italic', letterSpacing: -0.5 }}>{query.title}</div>
          <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, marginTop: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {query.folder_name} <span style={{ opacity: 0.3 }}>/</span> {query.connection_id || 'LOCAL ENGINE'}
          </div>
        </div>
        <button onClick={onClose} style={{
          width: 28, height: 28, borderRadius: 0, background: 'transparent', border: `1px solid rgba(0,0,0,0.08)`,
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.text3,
          fontSize: '0.75rem', flexShrink: 0, transition: 'all 0.15s'
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = T.text; e.currentTarget.style.color = T.text; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'; e.currentTarget.style.color = T.text3; }}
        ><X size={14} /></button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: `1px solid rgba(0,0,0,0.05)`, background: 'rgba(0,0,0,0.01)' }}>
        {(['info','sql','history','schedule'] as const).map((t) => (
          <div key={t} onClick={() => setActiveTab(t)} style={{
            flex: 1, padding: '12px 6px', textAlign: 'center', fontSize: '0.62rem', fontFamily: T.fontMono, fontWeight: 800,
            color: activeTab === t ? T.text : T.text3, cursor: 'pointer', borderBottom: `2px solid ${activeTab === t ? T.text : 'transparent'}`,
            transition: 'all 0.15s', textTransform: 'uppercase', letterSpacing: '0.08em'
          }}
          >
            {t}
          </div>
        ))}
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }} className="custom-scroll">

        {/* INFO TAB */}
        {activeTab === 'info' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Section label="Operational Metadata">
              <InfoRow label="Created" value={formatDate(query.created_at)} icon={<Clock size={12} />} />
              <InfoRow label="Last run" value={timeAgo(query.last_run_at).toUpperCase()} color={query.last_run_at ? T.text : undefined} icon={<Activity size={12} />} />
              <InfoRow label="Frequency" value={`${query.run_count} TOTAL RUNS`} icon={<Terminal size={12} />} />
              <InfoRow label="Source" value={query.connection_id || 'DEFAULT'} color={T.text} icon={<Database size={12} />} />
              {tables.length > 0 && <InfoRow label="Lineage" value={tables.join(', ').toUpperCase()} icon={<FileText size={12} />} />}
            </Section>

            <Section label="Organizational Unit">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0' }}>
                <div style={{ flex: 1 }}>
                  {!newFolderMode ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <select
                        value={folderDraft ?? 'Uncategorized'}
                        onChange={e => {
                          if (e.target.value === '__new__') { setNewFolderMode(true); }
                          else { setFolderDraft(e.target.value); }
                        }}
                        style={{
                          background: '#fff', border: `1px solid rgba(0,0,0,0.1)`, borderRadius: 0,
                          padding: '6px 10px', color: T.text, fontSize: '0.72rem',
                          fontFamily: T.fontMono, outline: 'none', cursor: 'pointer', width: '100%',
                          fontWeight: 700, textTransform: 'uppercase'
                        }}
                      >
                        <option value="Uncategorized">Uncategorized</option>
                        {folders.filter(f => f.name !== 'Uncategorized' && f.name !== 'Public Library').map(f => (
                          <option key={f.name} value={f.name}>{f.name}</option>
                        ))}
                        <option disabled>──────────</option>
                        <option value="__new__">＋ NEW DIRECTORY</option>
                      </select>
                      {folderDraft !== query.folder_name && (
                        <button onClick={handleFolderSave} disabled={folderSaving} style={{
                          padding: '6px 12px', borderRadius: 0, fontSize: '0.62rem', fontFamily: T.fontMono,
                          cursor: 'pointer', border: `1px solid ${T.text}`, fontWeight: 900,
                          background: T.text, color: '#fff', textTransform: 'uppercase'
                        }}>{folderSaving ? '...' : 'MOVE'}</button>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input
                        autoFocus
                        value={newFolderName}
                        onChange={e => setNewFolderName(e.target.value)}
                        placeholder="NAME..."
                        onKeyDown={e => { if (e.key === 'Enter') handleFolderSave(); if (e.key === 'Escape') setNewFolderMode(false); }}
                        style={{
                          background: '#fff', border: `1px solid ${T.text}`, borderRadius: 0,
                          padding: '6px 10px', color: T.text, fontSize: '0.72rem',
                          fontFamily: T.fontMono, outline: 'none', width: '100%',
                        }}
                      />
                      <button onClick={handleFolderSave} disabled={folderSaving} style={{
                        padding: '6px 12px', borderRadius: 0, fontSize: '0.62rem', fontFamily: T.fontMono,
                        cursor: 'pointer', background: T.text, color: '#fff', border: 'none', fontWeight: 900
                      }}>{folderSaving ? '...' : 'CREATE'}</button>
                    </div>
                  )}
                </div>
              </div>
            </Section>

            {query.description && (
              <Section label="Executive Summary">
                <div style={{ fontSize: '0.8rem', color: T.text2, lineHeight: 1.7, padding: '16px', background: 'rgba(0,0,0,0.02)', borderLeft: `3px solid ${T.text}` }}>
                  {query.description}
                </div>
              </Section>
            )}

            {query.tags.length > 0 && (
              <Section label="Taxonomy">
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {query.tags.map(t => (
                    <span key={t} style={{ 
                      padding: '4px 10px', borderRadius: 0, fontSize: '0.58rem', fontFamily: T.fontMono, 
                      border: `1px solid rgba(0,0,0,0.08)`, background: '#fff', color: T.text2,
                      fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em'
                    }}>
                      {t}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {runResult && (
              <Section label="Execution Status">
                <div style={{ 
                  padding: '16px', borderRadius: 0, 
                  background: runResult.success ? 'rgba(34,211,165,0.05)' : 'rgba(248,113,113,0.05)', 
                  border: `1px solid ${runResult.success ? 'rgba(34,211,165,0.15)' : 'rgba(248,113,113,0.15)'}`, 
                  color: runResult.success ? T.green : T.red, fontSize: '0.72rem', fontFamily: T.fontMono,
                  fontWeight: 700
                }}>
                  {runResult.success ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ textTransform: 'uppercase' }}>SUCCESS</div>
                      <div style={{ color: T.text3, fontWeight: 400 }}>{runResult.row_count} rows in {runResult.execution_time_ms}ms</div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ textTransform: 'uppercase' }}>FAILED</div>
                      <div style={{ color: T.red, fontWeight: 400 }}>{runResult.error}</div>
                    </div>
                  )}
                </div>
              </Section>
            )}
          </div>
        )}

        {/* SQL TAB */}
        {activeTab === 'sql' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 800, color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, letterSpacing: '0.1em' }}>Source Code</span>
              <button onClick={handleCopy} style={{ 
                padding: '4px 12px', borderRadius: 0, border: `1px solid ${copied ? T.green : 'rgba(0,0,0,0.1)'}`, 
                background: copied ? 'rgba(34,211,165,0.05)' : '#fff', color: copied ? T.green : T.text, 
                fontSize: '0.62rem', fontFamily: T.fontMono, fontWeight: 800, cursor: 'pointer' 
              }}>
                {copied ? 'COPIED' : 'COPY'}
              </button>
            </div>
            <div style={{
              background: '#1a1a1a', border: 'none', borderRadius: 0,
              padding: '20px', fontFamily: T.fontMono, fontSize: '0.72rem', lineHeight: 1.8,
              maxHeight: 400, overflowY: 'auto', color: '#fff',
              boxShadow: 'inset 0 0 10px rgba(0,0,0,0.3)'
            }} className="custom-scroll">
              {highlightSqlInline(query.sql, 'panel')}
            </div>
          </div>
        )}

        {/* HISTORY TAB */}
        {activeTab === 'history' && (
          <Section label="Timeline">
            {runHistory.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {runHistory.map((run, i) => (
                  <div key={run.id} style={{ 
                    display: 'flex', alignItems: 'flex-start', gap: 16, padding: '16px 0', 
                    borderBottom: i < runHistory.length - 1 ? `1px solid rgba(0,0,0,0.05)` : 'none' 
                  }}>
                    <div style={{ 
                      width: 8, height: 8, borderRadius: 0, marginTop: 4,
                      background: run.success ? T.green : T.red, flexShrink: 0
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 800, color: T.text, display: 'flex', alignItems: 'center', gap: 8, fontFamily: T.fontMono }}>
                        {run.success ? `${run.row_count} ROWS` : 'ERROR'}
                        {i === 0 && <span style={{ fontSize: '0.55rem', padding: '2px 6px', background: T.text, color: '#fff' }}>LATEST</span>}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: T.text3, fontFamily: T.fontMono, marginTop: 4, textTransform: 'uppercase' }}>
                        {run.execution_time_ms.toFixed(0)}ms · {timeAgo(run.ran_at)}
                      </div>
                      {run.error && <div style={{ color: T.red, fontSize: '0.65rem', marginTop: 8, fontFamily: T.fontMono }}>{run.error}</div>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState message="No execution records found." sub="Run this query to begin instrumentation." icon={<Activity size={24} />} />
            )}
          </Section>
        )}

        {/* SCHEDULE TAB */}
        {activeTab === 'schedule' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Section label="Automated Scheduling">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, background: 'rgba(0,0,0,0.02)', padding: '20px', border: '1px solid rgba(0,0,0,0.05)' }}>
                <SettingsRow label="Status">
                  <Toggle on={schedDraft.enabled} onToggle={() => setSchedDraft({ ...schedDraft, enabled: !schedDraft.enabled })} />
                </SettingsRow>

                {schedDraft.enabled && (
                  <>
                    <SettingsRow label="Frequency">
                      <div style={{ display: 'flex', border: '1px solid rgba(0,0,0,0.1)', background: '#fff' }}>
                        {(['daily','weekly','monthly'] as const).map(f => (
                          <button key={f} onClick={() => setSchedDraft({ ...schedDraft, frequency: f })} style={{
                            padding: '6px 12px', border: 'none', borderRight: f !== 'monthly' ? '1px solid rgba(0,0,0,0.1)' : 'none',
                            background: schedDraft.frequency === f ? T.text : 'transparent',
                            color: schedDraft.frequency === f ? '#fff' : T.text3,
                            fontSize: '0.62rem', fontFamily: T.fontMono, fontWeight: 800, cursor: 'pointer', textTransform: 'uppercase'
                          }}>{f}</button>
                        ))}
                      </div>
                    </SettingsRow>

                    {schedDraft.frequency === 'weekly' && (
                      <SettingsRow label="Window">
                        <select 
                          value={schedDraft.day_of_week ?? 'monday'} 
                          onChange={e => setSchedDraft({ ...schedDraft, day_of_week: e.target.value as any })}
                          style={selectStyle}
                        >
                          {DAYS_OF_WEEK.map(d => <option key={d} value={d}>{d.toUpperCase()}</option>)}
                        </select>
                      </SettingsRow>
                    )}

                    <SettingsRow label="Timestamp">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <input type="number" min={1} max={12} value={schedDraft.hour % 12 || 12}
                          onChange={e => {
                            const h12 = Math.min(12, Math.max(1, Number(e.target.value)));
                            const isPm = schedDraft.hour >= 12;
                            setSchedDraft({ ...schedDraft, hour: isPm ? (h12 === 12 ? 12 : h12 + 12) : (h12 === 12 ? 0 : h12) });
                          }}
                          style={{ ...selectStyle, width: 44, textAlign: 'center' }}
                        />
                        <span style={{ fontFamily: T.fontMono }}>:</span>
                        <input type="number" min={0} max={59} value={String(schedDraft.minute).padStart(2, '0')}
                          onChange={e => setSchedDraft({ ...schedDraft, minute: Math.min(59, Math.max(0, Number(e.target.value))) })}
                          style={{ ...selectStyle, width: 44, textAlign: 'center' }}
                        />
                        <button onClick={() => {
                          const isPm = schedDraft.hour >= 12;
                          setSchedDraft({ ...schedDraft, hour: isPm ? schedDraft.hour - 12 : schedDraft.hour + 12 });
                        }} style={{
                          padding: '4px 8px', background: '#fff', border: '1px solid rgba(0,0,0,0.1)', 
                          fontSize: '0.62rem', fontFamily: T.fontMono, fontWeight: 800, cursor: 'pointer'
                        }}>{schedDraft.hour >= 12 ? 'PM' : 'AM'}</button>
                      </div>
                    </SettingsRow>

                    <SettingsRow label="Timezone">
                      <select value={schedDraft.timezone} onChange={e => setSchedDraft({ ...schedDraft, timezone: e.target.value })} style={{ ...selectStyle, width: 140 }}>
                        {COMMON_TIMEZONES.map(tz => <option key={tz} value={tz}>{tz.split('/').pop()?.replace(/_/g, ' ')}</option>)}
                      </select>
                    </SettingsRow>
                  </>
                )}
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                <button 
                  onClick={async () => {
                    setSchedSaving(true);
                    try { await setQuerySchedule(query.id, schedDraft); onRefresh?.(); } catch { }
                    setSchedSaving(false);
                  }} 
                  disabled={schedSaving || !query.connection_id} 
                  style={{
                    flex: 1, padding: '12px', border: 'none', background: T.text, color: '#fff',
                    fontSize: '0.72rem', fontWeight: 900, fontFamily: T.fontMono, cursor: 'pointer',
                    opacity: schedSaving || !query.connection_id ? 0.5 : 1, textTransform: 'uppercase'
                  }}
                >
                  {schedSaving ? 'COMMITTING...' : 'COMMIT SCHEDULE'}
                </button>
                {query.schedule && (
                  <button onClick={async () => {
                    setSchedSaving(true);
                    try { await removeQuerySchedule(query.id); setSchedDraft(defaultSchedule()); onRefresh?.(); } catch { }
                    setSchedSaving(false);
                  }} style={{
                    padding: '12px', border: '1px solid rgba(0,0,0,0.1)', background: '#fff', color: T.red,
                    fontSize: '0.72rem', fontWeight: 900, fontFamily: T.fontMono, cursor: 'pointer', textTransform: 'uppercase'
                  }}>ABORT</button>
                )}
              </div>
            </Section>
          </div>
        )}

      </div>

      {/* Action Buttons */}
      <div style={{ padding: '24px', borderTop: `1px solid rgba(0,0,0,0.08)`, display: 'flex', flexDirection: 'column', gap: 12, flexShrink: 0, background: 'rgba(0,0,0,0.01)' }}>
        <PanelBtn label={running ? 'EXECUTING...' : 'RUN ANALYTICS'} type="accent" onClick={handleRun} disabled={running} icon={<Play size={14} />} />
        <PanelBtn label="ARCHIVE QUERY" type="danger" onClick={handleDelete} icon={<Trash2 size={14} />} />
      </div>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(10px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: 20
        }} onClick={() => setShowDeleteConfirm(false)}>
          <div style={{
            width: '100%', maxWidth: 360, background: '#fff', border: `2px solid ${T.text}`,
            padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 24,
            animation: 'popIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
          }} onClick={e => e.stopPropagation()}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: T.fontHead, fontWeight: 900, fontSize: '1.4rem', color: T.text, marginBottom: 12, fontStyle: 'italic' }}>Destructive Action</div>
              <div style={{ fontSize: '0.85rem', color: T.text3, lineHeight: 1.6 }}>
                Are you certain you wish to archive <span style={{ color: T.text, fontWeight: 800 }}>"{query.title}"</span>? This operation cannot be reversed.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={() => setShowDeleteConfirm(false)} style={{
                flex: 1, padding: '12px', border: `1px solid rgba(0,0,0,0.1)`,
                background: 'transparent', color: T.text, fontSize: '0.72rem', cursor: 'pointer',
                fontFamily: T.fontMono, fontWeight: 800, textTransform: 'uppercase'
              }}>Cancel</button>
              <button onClick={confirmDelete} style={{
                flex: 1, padding: '12px', border: 'none', background: T.red, color: '#fff', 
                fontSize: '0.72rem', cursor: 'pointer', fontFamily: T.fontMono, fontWeight: 800,
                textTransform: 'uppercase'
              }}>Confirm Archive</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .custom-scroll::-webkit-scrollbar { width: 2px; }
        .custom-scroll::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); }
        @keyframes popIn { from { opacity: 0; transform: scale(0.98) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
      `}</style>
    </div>
  );
}

function Section({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {label && <div style={{ fontSize: '0.58rem', fontWeight: 900, color: T.text3, textTransform: 'uppercase', fontFamily: T.fontMono, letterSpacing: '0.15em' }}>{label}</div>}
      {children}
    </div>
  );
}

function InfoRow({ label, value, color, icon }: { label: string, value: string, color?: string, icon?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: `1px solid rgba(0,0,0,0.05)` }}>
      <span style={{ color: T.text3, display: 'flex' }}>{icon}</span>
      <span style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, width: 80, flexShrink: 0, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: '0.75rem', color: color || T.text, flex: 1, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</span>
    </div>
  );
}

function SettingsRow({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ fontSize: '0.7rem', color: T.text, fontWeight: 800, fontFamily: T.fontMono, textTransform: 'uppercase' }}>{label}</span>
      {children}
    </div>
  );
}

function Toggle({ on, onToggle }: { on: boolean, onToggle: () => void }) {
  return (
    <div onClick={onToggle} style={{
      width: 36, height: 20, borderRadius: 0, background: on ? T.text : 'rgba(0,0,0,0.1)',
      cursor: 'pointer', position: 'relative', flexShrink: 0, transition: 'all 0.2s',
      border: `1px solid ${on ? T.text : 'rgba(0,0,0,0.1)'}`
    }}>
      <div style={{ position: 'absolute', width: 14, height: 14, borderRadius: 0, background: on ? '#fff' : '#fff', top: 2, right: on ? 2 : 18, transition: 'right 0.2s' }} />
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 0, border: `1px solid rgba(0,0,0,0.1)`,
  background: '#fff', color: T.text, fontSize: '0.7rem', fontFamily: T.fontMono,
  outline: 'none', cursor: 'pointer', appearance: 'none' as const, fontWeight: 700
};

function PanelBtn({ label, type, onClick, disabled, icon }: { label: string, type: 'accent'|'ghost'|'danger', onClick?: () => void, disabled?: boolean, icon?: React.ReactNode }) {
  const getStyle = (): React.CSSProperties => {
    if (type === 'accent') return { background: T.text, color: '#fff', border: 'none' };
    if (type === 'danger') return { background: 'transparent', border: `1px solid rgba(0,0,0,0.1)`, color: T.red };
    return { background: 'transparent', border: `1px solid rgba(0,0,0,0.1)`, color: T.text };
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ 
      width: '100%', padding: '12px 16px', borderRadius: 0, fontSize: '0.72rem', cursor: disabled ? 'not-allowed' : 'pointer', 
      fontFamily: T.fontMono, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, fontWeight: 900, 
      transition: 'all 0.15s', opacity: disabled ? 0.5 : 1, textTransform: 'uppercase', ...getStyle() 
    }}
      onMouseEnter={e => { if(!disabled && type !== 'accent') e.currentTarget.style.borderColor = T.text; }}
      onMouseLeave={e => { if(!disabled && type !== 'accent') e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'; }}
    >
      {icon} {label}
    </button>
  );
}

function EmptyState({ message, sub, icon }: { message: string; sub?: string; icon?: React.ReactNode }) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 20px', border: `1px dashed rgba(0,0,0,0.08)`, borderRadius: 0 }}>
      <div style={{ color: T.text3, opacity: 0.3, marginBottom: 12, display: 'flex', justifyContent: 'center' }}>{icon}</div>
      <div style={{ fontSize: '0.85rem', color: T.text, fontWeight: 900, fontFamily: T.fontHead, fontStyle: 'italic', marginBottom: 4 }}>{message}</div>
      {sub && <div style={{ fontSize: '0.72rem', color: T.text3, lineHeight: 1.5 }}>{sub}</div>}
    </div>
  );
}
