import { useCallback, useEffect, useRef } from 'react';
import * as api from '../services/api';
import { consumeChatRunEvents } from '../services/chatStream';
import type { ChatRunAccepted, ChatRunEvent, ChatRunRequest, ChatRunSnapshot } from '../types/api';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export function useChatAgentRun(callbacks: {
  onAccepted: (run: ChatRunAccepted) => void;
  onEvent: (event: ChatRunEvent) => void;
  onSnapshot: (snapshot: ChatRunSnapshot) => void;
  onError: (error: unknown) => void;
}) {
  const callbacksRef = useRef(callbacks);
  useEffect(() => {
    callbacksRef.current = callbacks;
  }, [callbacks]);
  const controllerRef = useRef<AbortController | null>(null);
  const activeRunRef = useRef<string | null>(null);

  const disconnect = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    activeRunRef.current = null;
  }, []);

  const connect = useCallback(async (runId: string) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    activeRunRef.current = runId;
    let lastEventId: string | undefined;
    let failures = 0;
    let terminalSeen = false;

    while (!controller.signal.aborted && !terminalSeen && activeRunRef.current === runId) {
      try {
        lastEventId = await consumeChatRunEvents(runId, {
          signal: controller.signal,
          lastEventId,
          onEvent: ({ event, data }) => {
            if (event !== 'heartbeat') callbacksRef.current.onEvent(data);
            if (event === 'run.completed' || event === 'run.failed' || event === 'run.cancelled') terminalSeen = true;
          },
        });
        const snapshot = await api.getChatRun(runId);
        callbacksRef.current.onSnapshot(snapshot);
        if (TERMINAL.has(snapshot.status)) return;
      } catch (error) {
        if (controller.signal.aborted) return;
        callbacksRef.current.onError(error);
        failures += 1;
        if (failures >= 5) {
          try {
            const snapshot = await api.getChatRun(runId);
            callbacksRef.current.onSnapshot(snapshot);
            if (TERMINAL.has(snapshot.status)) return;
          } catch {
            // Keep reconnecting; the durable server run may still be active.
          }
        }
      }
      const delays = [1000, 2000, 4000, 8000, 15000];
      const delay = delays[Math.min(failures, delays.length - 1)] + Math.floor(Math.random() * 400);
      await new Promise(resolve => window.setTimeout(resolve, delay));
    }
    if (terminalSeen && !controller.signal.aborted) {
      try {
        callbacksRef.current.onSnapshot(await api.getChatRun(runId));
      } catch (error) {
        callbacksRef.current.onError(error);
      }
    }
  }, []);

  const start = useCallback(async (request: ChatRunRequest) => {
    const accepted = await api.startChatRun(request);
    callbacksRef.current.onAccepted(accepted);
    if (TERMINAL.has(accepted.status)) {
      callbacksRef.current.onSnapshot(await api.getChatRun(accepted.run_id));
    } else {
      void connect(accepted.run_id);
    }
    return accepted;
  }, [connect]);

  const attach = useCallback(async (runId: string) => {
    const snapshot = await api.getChatRun(runId);
    callbacksRef.current.onSnapshot(snapshot);
    if (!TERMINAL.has(snapshot.status)) void connect(runId);
  }, [connect]);

  const cancel = useCallback(async (runId: string) => {
    const snapshot = await api.cancelChatRun(runId);
    callbacksRef.current.onSnapshot(snapshot);
    return snapshot;
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return { start, attach, cancel, disconnect };
}
