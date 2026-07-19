export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
let cachedCsrfToken: string | null = null;

function csrfToken(): string | null {
  if (cachedCsrfToken) return cachedCsrfToken;
  if (typeof document === 'undefined') return null;
  const entry = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('wcai_csrf='));
  return entry ? decodeURIComponent(entry.slice('wcai_csrf='.length)) : null;
}

export function setCsrfToken(token: string | null): void {
  cachedCsrfToken = token;
}

export async function ensureCsrfToken(): Promise<string> {
  const existing = csrfToken();
  if (existing) return existing;
  const response = await fetch(`${API_URL}/api/auth/csrf`, { credentials: 'include' });
  const data = await response.json().catch(() => ({})) as { csrfToken?: unknown };
  if (!response.ok || typeof data.csrfToken !== 'string' || !data.csrfToken) {
    throw new Error('Your secure session could not be refreshed. Please sign in again.');
  }
  cachedCsrfToken = data.csrfToken;
  return data.csrfToken;
}

export function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const csrf = csrfToken();
  if (csrf) headers.set('X-CSRF-Token', csrf);

  return headers;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    await ensureCsrfToken();
  }
  const headers = authHeaders(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: 'include' });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data?.detail === 'string'
      ? data.detail
      : typeof data?.detail?.error === 'string'
        ? data.detail.error
      : typeof data?.message === 'string'
        ? data.message
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return data as T;
}
