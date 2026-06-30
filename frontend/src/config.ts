const fallbackApiBase = 'http://localhost:8000/api';

function normalizeLoopbackApiBase(rawApiBase: string): string {
  const apiBase = rawApiBase.trim().replace(/\/$/, '') || fallbackApiBase;

  if (typeof window === 'undefined') {
    return apiBase;
  }

  try {
    const apiUrl = new URL(apiBase);
    const browserHost = window.location.hostname;
    const loopbackHosts = new Set(['localhost', '127.0.0.1']);

    if (loopbackHosts.has(apiUrl.hostname) && loopbackHosts.has(browserHost)) {
      apiUrl.hostname = browserHost;
      return apiUrl.toString().replace(/\/$/, '');
    }
  } catch {
    return apiBase;
  }

  return apiBase;
}

export const API_BASE = normalizeLoopbackApiBase(
  import.meta.env.VITE_API_BASE_URL || fallbackApiBase
);
