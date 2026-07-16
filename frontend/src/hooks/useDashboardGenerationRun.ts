import { useCallback, useEffect, useRef } from 'react';
import * as api from '../services/api';
import { consumeDashboardGenerationEvents } from '../services/dashboardGenerationStream';
import type {
  CreateDashboardGenerationRequest,
  DashboardGenerationEvent,
  DashboardGenerationRun,
} from '../types/api';
import {
  EXECUTION_STREAM_STOP_EVENTS,
  EXECUTION_TERMINAL_STATUSES,
  PLANNING_PAUSE_STATUSES,
  PLANNING_STREAM_STOP_EVENTS,
} from '../utils/dashboardGeneration';

type Phase = 'planning' | 'execution';

export function useDashboardGenerationRun(callbacks: {
  onAccepted?: (run: { run_id: string; status: string; events_url: string }) => void;
  onEvent?: (event: DashboardGenerationEvent) => void;
  onSnapshot: (snapshot: DashboardGenerationRun) => void;
  onError?: (error: unknown) => void;
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

  const connect = useCallback(async (runId: string, phase: Phase) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    activeRunRef.current = runId;
    let lastEventId: string | undefined;
    let failures = 0;
    let stopSeen = false;
    const stopEvents = phase === 'planning' ? PLANNING_STREAM_STOP_EVENTS : EXECUTION_STREAM_STOP_EVENTS;
    const pauseStatuses = phase === 'planning' ? PLANNING_PAUSE_STATUSES : EXECUTION_TERMINAL_STATUSES;

    while (!controller.signal.aborted && !stopSeen && activeRunRef.current === runId) {
      try {
        lastEventId = await consumeDashboardGenerationEvents(runId, {
          signal: controller.signal,
          lastEventId,
          onEvent: ({ event, data }) => {
            if (event !== 'heartbeat') callbacksRef.current.onEvent?.(data);
            if (stopEvents.has(event) || stopEvents.has(data.type)) {
              stopSeen = true;
              return true;
            }
            return false;
          },
        });
        failures = 0;
        const snapshot = await api.getDashboardGeneration(runId);
        callbacksRef.current.onSnapshot(snapshot);
        if (pauseStatuses.has(snapshot.status)) return;
      } catch (error) {
        if (controller.signal.aborted) return;
        callbacksRef.current.onError?.(error);
        failures += 1;
        if (failures >= 5) {
          try {
            const snapshot = await api.getDashboardGeneration(runId);
            callbacksRef.current.onSnapshot(snapshot);
            if (pauseStatuses.has(snapshot.status)) return;
          } catch {
            // Keep reconnecting; durable server run may still be active.
          }
        }
      }
      const delays = [1000, 2000, 4000, 8000, 15000];
      const delay = delays[Math.min(failures, delays.length - 1)] + Math.floor(Math.random() * 400);
      await new Promise((resolve) => window.setTimeout(resolve, delay));
    }

    if (stopSeen && !controller.signal.aborted) {
      try {
        callbacksRef.current.onSnapshot(await api.getDashboardGeneration(runId));
      } catch (error) {
        callbacksRef.current.onError?.(error);
      }
    }
  }, []);

  const startPlanning = useCallback(async (request: CreateDashboardGenerationRequest) => {
    const accepted = await api.createDashboardGeneration(request);
    callbacksRef.current.onAccepted?.(accepted);
    try {
      callbacksRef.current.onSnapshot(await api.getDashboardGeneration(accepted.run_id));
    } catch {
      // The stream remains authoritative if the initial snapshot races dispatch.
    }
    void connect(accepted.run_id, 'planning');
    return accepted;
  }, [connect]);

  const attach = useCallback(async (runId: string, phase: Phase = 'execution') => {
    const snapshot = await api.getDashboardGeneration(runId);
    callbacksRef.current.onSnapshot(snapshot);
    const pauseStatuses = phase === 'planning' ? PLANNING_PAUSE_STATUSES : EXECUTION_TERMINAL_STATUSES;
    if (!pauseStatuses.has(snapshot.status)) void connect(runId, phase);
    return snapshot;
  }, [connect]);

  const cancel = useCallback(async (runId: string) => {
    const snapshot = await api.cancelDashboardGeneration(runId);
    callbacksRef.current.onSnapshot(snapshot);
    return snapshot;
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return { startPlanning, attach, cancel, disconnect, connect };
}
