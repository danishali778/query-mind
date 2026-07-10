import { jsonRequest, refreshAuthSession as refreshHttpAuthSession, request } from './http';
import type { AuthCredentialsRequest, AuthSessionResponse } from '../types/api';

export function signUp(data: AuthCredentialsRequest) {
  return jsonRequest<AuthSessionResponse>('/auth/signup', 'POST', data, { skipAuthRefresh: true });
}

export function signIn(data: AuthCredentialsRequest) {
  return jsonRequest<AuthSessionResponse>('/auth/login', 'POST', data, { skipAuthRefresh: true });
}

export function signOut() {
  return request<{ message: string; status?: string | null }>('/auth/logout', { method: 'POST', skipAuthRefresh: true });
}

export function refreshAuthSession() {
  return refreshHttpAuthSession<AuthSessionResponse>();
}

export function getAuthSession() {
  return request<AuthSessionResponse>('/auth/session', { skipAuthRedirect: true, skipAuthRefresh: true });
}
