import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/config', () => ({ API_BASE: 'https://api.example.test/api' }));

import { request } from '../src/services/http';


function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
  } as Response;
}


describe('authentication refresh coordination', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('uses one refresh request for concurrent expired API calls', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
      .mockResolvedValueOnce(jsonResponse(200, { authenticated: true }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'one' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'two' }));
    vi.stubGlobal('fetch', fetchMock);

    const [one, two] = await Promise.all([
      request<{ id: string }>('/protected/one'),
      request<{ id: string }>('/protected/two'),
    ]);

    expect(one).toEqual({ id: 'one' });
    expect(two).toEqual({ id: 'two' });
    const refreshCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'));
    expect(refreshCalls).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it('does not retry the original request after a failed shared refresh', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'expired' }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(request('/protected', { skipAuthRedirect: true })).rejects.toMatchObject({ status: 401 });

    const refreshCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'));
    expect(refreshCalls).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
