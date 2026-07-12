import { API_BASE } from '../config';
import { refreshAuthSession } from './http';
import type { ChatRunEvent } from '../types/api';

export interface ParsedSseEvent<T = ChatRunEvent> {
  id?: string;
  event: string;
  data: T;
}

export function parseSseBlock<T = ChatRunEvent>(block: string): ParsedSseEvent<T> | null {
  let id: string | undefined;
  let event = 'message';
  const data: string[] = [];
  for (const rawLine of block.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue;
    const separator = rawLine.indexOf(':');
    const field = separator < 0 ? rawLine : rawLine.slice(0, separator);
    let value = separator < 0 ? '' : rawLine.slice(separator + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'id') id = value;
    else if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  }
  if (!data.length) return null;
  return { id, event, data: JSON.parse(data.join('\n')) as T };
}

async function openStream(runId: string, lastEventId: string | undefined, signal: AbortSignal, refreshed = false) {
  const headers = new Headers({ Accept: 'text/event-stream' });
  if (lastEventId) headers.set('Last-Event-ID', lastEventId);
  const response = await fetch(`${API_BASE}/chat/runs/${runId}/events`, {
    method: 'GET', credentials: 'include', headers, signal,
  });
  if (response.status === 401 && !refreshed) {
    await refreshAuthSession<unknown>();
    return openStream(runId, lastEventId, signal, true);
  }
  if (!response.ok || !response.body) throw new Error(`Stream request failed with status ${response.status}`);
  return response;
}

export async function consumeChatRunEvents(
  runId: string,
  options: {
    signal: AbortSignal;
    lastEventId?: string;
    onEvent: (event: ParsedSseEvent) => void;
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
      const parsed = parseSseBlock(block);
      if (!parsed) continue;
      if (parsed.id) lastEventId = parsed.id;
      options.onEvent(parsed);
    }
    if (done) break;
  }
  return lastEventId;
}
