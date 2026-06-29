import { jsonRequest, request } from './http';
import type { AuthCredentialsRequest, AuthSessionResponse } from '../types/api';

export function signUp(data: AuthCredentialsRequest) {
  return jsonRequest<AuthSessionResponse>('/auth/signup', 'POST', data);
}

export function signIn(data: AuthCredentialsRequest) {
  return jsonRequest<AuthSessionResponse>('/auth/login', 'POST', data);
}

export function signOut() {
  return request<{ message: string; status?: string | null }>('/auth/logout', { method: 'POST' });
}

export function refreshAuthSession() {
  return request<AuthSessionResponse>('/auth/refresh', { method: 'POST', skipAuthRedirect: true });
}

export function getAuthSession() {
  return request<AuthSessionResponse>('/auth/session', { skipAuthRedirect: true });
}
