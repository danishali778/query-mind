import { API_BASE } from '../config';
import { refreshAuthSession } from './http';
import { parseSseBlock, type ParsedSseEvent } from './chatStream';
import type { DashboardGenerationEvent } from '../types/api';

async function openStream(
  runId: string,
  lastEventId: string | undefined,
  signal: AbortSignal,
  refreshed = false,
) {
  const headers = new Headers({ Accept: 'text/event-stream' });
  if (lastEventId) headers.set('Last-Event-ID', lastEventId);
  const response = await fetch(`${API_BASE}/dashboard/generations/${runId}/events`, {
    method: 'GET',
    credentials: 'include',
    headers,
    signal,
  });
  if (response.status === 401 && !refreshed) {
    await refreshAuthSession<unknown>();
    return openStream(runId, lastEventId, signal, true);
  }
  if (!response.ok || !response.body) {
    throw new Error(`Dashboard generation stream failed with status ${response.status}`);
  }
  return response;
}

export async function consumeDashboardGenerationEvents(
  runId: string,
  options: {
    signal: AbortSignal;
    lastEventId?: string;
    onEvent: (event: ParsedSseEvent<DashboardGenerationEvent>) => void;
  },
): Promise<string | undefined> {
  const response = await openStream(runId, options.lastEventId, options.signal);
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastEventId = options.lastEventId;
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const parsed = parseSseBlock<DashboardGenerationEvent>(block);
      if (!parsed) continue;
      if (parsed.id) lastEventId = parsed.id;
      options.onEvent(parsed);
    }
    if (done) break;
  }
  return lastEventId;
}
