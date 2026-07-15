export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = typeof window === 'undefined' ? null : localStorage.getItem('token');

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return headers;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
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
