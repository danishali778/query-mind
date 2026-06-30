import { API_BASE } from '../config';
import type { ApiErrorResponse } from '../types/api';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type ApiErrorDetails = NonNullable<ApiErrorResponse['error']['details']>;

type ApiRequestInit = RequestInit & {
  skipAuthRedirect?: boolean;
  skipAuthRefresh?: boolean;
};

const AUTH_REFRESH_PATH = '/auth/refresh';
const AUTH_RETRY_EXCLUDED_PATHS = new Set([
  '/auth/login',
  '/auth/signup',
  '/auth/logout',
  '/auth/refresh',
  '/auth/session',
]);

export class ApiRequestError extends Error {
  status: number;
  code: string;
  details: ApiErrorDetails | null;

  constructor(
    message: string,
    options: { status: number; code: string; details?: ApiErrorDetails | null }
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? null;
  }
}

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

function getErrorCode(payload: unknown, fallback: string): string {
  return isApiErrorResponse(payload) ? payload.error.code : fallback;
}

function getErrorDetails(payload: unknown): ApiErrorDetails | null {
  return isApiErrorResponse(payload) ? payload.error.details ?? null : null;
}

function buildFetchInit(init?: ApiRequestInit): RequestInit {
  const fetchInit: ApiRequestInit = { ...(init || {}) };
  delete fetchInit.skipAuthRedirect;
  delete fetchInit.skipAuthRefresh;

  const headers = new Headers(fetchInit.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return {
    ...fetchInit,
    credentials: 'include',
    headers,
  };
}

function shouldRefreshAuth(path: string, init?: ApiRequestInit): boolean {
  const routePath = path.split('?')[0];
  if (init?.skipAuthRefresh) return false;
  return !AUTH_RETRY_EXCLUDED_PATHS.has(routePath);
}

async function fetchApi(path: string, init?: ApiRequestInit): Promise<{ response: Response; payload: unknown }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, buildFetchInit(init));
  } catch {
    throw new ApiRequestError('Network request failed.', {
      status: 0,
      code: 'network_error',
    });
  }

  const payload = await parseResponseBody(response);
  return { response, payload };
}

async function tryRefreshAuth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}${AUTH_REFRESH_PATH}`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.ok;
  } catch {
    return false;
  }
}

function handleAuthRedirect(skipAuthRedirect?: boolean) {
  if (skipAuthRedirect) return;

  console.warn('Session invalid or expired. Redirecting to auth.');
  if (window.location.pathname !== '/auth') {
    window.location.href = '/auth';
  }
}

function requestErrorFromResponse(response: Response, payload: unknown): ApiRequestError {
  const message = getErrorMessage(payload, `Request failed with status ${response.status}`);
  return new ApiRequestError(message, {
    status: response.status,
    code: getErrorCode(payload, `http_${response.status}`),
    details: getErrorDetails(payload),
  });
}

export async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const { response, payload } = await fetchApi(path, init);

  if (response.status === 401 && shouldRefreshAuth(path, init)) {
    const refreshed = await tryRefreshAuth();
    if (refreshed) {
      const retry = await fetchApi(path, { ...init, skipAuthRefresh: true });
      if (retry.response.ok) {
        return retry.payload as T;
      }
      if (retry.response.status === 401) {
        handleAuthRedirect(init?.skipAuthRedirect);
      }
      throw requestErrorFromResponse(retry.response, retry.payload);
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      handleAuthRedirect(init?.skipAuthRedirect);
    }
    throw requestErrorFromResponse(response, payload);
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

