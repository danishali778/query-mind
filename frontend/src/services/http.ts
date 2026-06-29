import { API_BASE } from '../config';
import type { ApiErrorResponse } from '../types/api';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

type ApiRequestInit = RequestInit & {
  skipAuthRedirect?: boolean;
};

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  return typeof value === 'object' && value !== null && 'error' in value;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (isApiErrorResponse(payload)) {
    return payload.error.message;
  }

  if (payload && typeof payload === 'object' && 'detail' in payload && typeof payload.detail === 'string') {
    return payload.detail;
  }

  return fallback;
}

export async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const { skipAuthRedirect, ...fetchInit } = init || {};
  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchInit,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(fetchInit.headers || {}),
    },
  });

  const payload = await parseResponseBody(response);
  if (!response.ok) {
    if (response.status === 401 && !skipAuthRedirect) {
      console.warn('Session invalid or expired. Redirecting to auth.');
      if (window.location.pathname !== '/auth') {
        window.location.href = '/auth';
      }
    }
    throw new Error(getErrorMessage(payload, `Request failed with status ${response.status}`));
  }

  return payload as T;
}

export function jsonRequest<T>(path: string, method: HttpMethod, body?: unknown, init?: Omit<ApiRequestInit, 'method' | 'body'>): Promise<T> {
  return request<T>(path, {
    ...init,
    method,
    body: body ? JSON.stringify(body) : undefined,
  });
}
