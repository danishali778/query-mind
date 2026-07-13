import { useCallback, useEffect, useRef, useState } from 'react';
import {
  dismissQuestionSuggestion,
  getQuestionSuggestions,
  refreshQuestionSuggestions,
} from '../services/api';
import type {
  QuestionSuggestionResponse,
  SuggestionSurface,
} from '../types/questionSuggestions';

const POLL_MS = 3000;

export function useQuestionSuggestions(connectionId: string | null | undefined, surface: SuggestionSurface) {
  const [data, setData] = useState<QuestionSuggestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const attemptedFingerprints = useRef(new Set<string>());
  const requestGeneration = useRef(0);
  const scopeKeyRef = useRef('');

  const applyIfCurrent = useCallback((generation: number, response: QuestionSuggestionResponse) => {
    if (requestGeneration.current === generation) setData(response);
  }, []);

  useEffect(() => {
    requestGeneration.current += 1;
    const generation = requestGeneration.current;
    const controller = new AbortController();
    let timer: number | undefined;
    const scopeKey = `${connectionId || ''}:${surface}`;
    if (scopeKeyRef.current !== scopeKey) {
      scopeKeyRef.current = scopeKey;
      setData(null);
      setError(null);
    }
    if (!connectionId) {
      setLoading(false);
      return () => controller.abort();
    }

    const poll = async (): Promise<void> => {
      if (controller.signal.aborted) return;
      try {
        const response = await getQuestionSuggestions(connectionId, surface, undefined, controller.signal);
        applyIfCurrent(generation, response);
        if (response.status === 'queued' || response.status === 'running') {
          timer = window.setTimeout(() => void poll(), POLL_MS);
        }
      } catch (err) {
        if (!controller.signal.aborted && requestGeneration.current === generation) {
          setError(err instanceof Error ? err.message : 'Could not refresh suggestions.');
        }
      }
    };

    const start = async () => {
      setLoading(true);
      try {
        const response = await getQuestionSuggestions(connectionId, surface, undefined, controller.signal);
        applyIfCurrent(generation, response);
        if (
          response.refresh_required
          && !attemptedFingerprints.current.has(`${connectionId}:${response.context_fingerprint}`)
        ) {
          attemptedFingerprints.current.add(`${connectionId}:${response.context_fingerprint}`);
          setRefreshing(true);
          try {
            const queued = await refreshQuestionSuggestions(
              connectionId,
              surface,
              response.context_fingerprint,
              false,
              controller.signal,
            );
            applyIfCurrent(generation, queued);
            if (queued.status === 'queued' || queued.status === 'running') {
              timer = window.setTimeout(() => void poll(), POLL_MS);
            }
          } catch (err) {
            if (!controller.signal.aborted && requestGeneration.current === generation) {
              setError(err instanceof Error ? err.message : 'Personalization is unavailable.');
            }
          } finally {
            if (!controller.signal.aborted) setRefreshing(false);
          }
        } else if (response.status === 'queued' || response.status === 'running') {
          timer = window.setTimeout(() => void poll(), POLL_MS);
        }
      } catch (err) {
        if (!controller.signal.aborted && requestGeneration.current === generation) {
          setError(err instanceof Error ? err.message : 'Could not load suggestions.');
        }
      } finally {
        if (!controller.signal.aborted && requestGeneration.current === generation) setLoading(false);
      }
    };
    void start();
    return () => {
      controller.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [applyIfCurrent, connectionId, surface, reloadToken]);

  const refresh = useCallback(async () => {
    if (!connectionId || !data) return;
    setRefreshing(true);
    setError(null);
    try {
      const response = await refreshQuestionSuggestions(
        connectionId,
        surface,
        data.context_fingerprint,
        true,
      );
      setData(response);
      if (response.status === 'queued' || response.status === 'running') {
        setReloadToken((value) => value + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not refresh suggestions.');
    } finally {
      setRefreshing(false);
    }
  }, [connectionId, data, surface]);

  const dismiss = useCallback(async (suggestionId: string) => {
    if (!connectionId || !data) return;
    setData((current) => current ? {
      ...current,
      suggestions: current.suggestions.filter((item) => item.id !== suggestionId),
    } : current);
    try {
      const response = await dismissQuestionSuggestion(
        connectionId,
        surface,
        suggestionId,
        data.context_fingerprint,
      );
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not dismiss suggestion.');
    }
  }, [connectionId, data, surface]);

  return {
    suggestions: data?.suggestions ?? [],
    status: data?.status ?? null,
    loading,
    refreshing,
    error,
    failure: data?.failure ?? null,
    refresh,
    dismiss,
  };
}
