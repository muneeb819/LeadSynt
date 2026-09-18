// Thin fetch wrapper around the same-origin /api proxy.
// The browser never holds DB credentials or backend URLs — only the JWT.

const TOKEN_KEY = "leadsynt_access_token";
const REFRESH_KEY = "leadsynt_refresh_token";

export class ApiClientError extends Error {
  code: string;
  status: number;
  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh: string): void {
  window.localStorage.setItem(TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export async function refreshTokens(): Promise<boolean> {
  const refresh = window.localStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  try {
    const res = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const body = await res.json();
    setTokens(body.access_token, body.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const doFetch = (token: string | null) => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string> | undefined),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return fetch(`/api/v1${path}`, { ...init, headers });
  };

  let res = await doFetch(getToken());

  // One transparent refresh-and-retry (never on /auth/* endpoints).
  if (res.status === 401 && !path.startsWith("/auth/")) {
    if (await refreshTokens()) {
      res = await doFetch(getToken());
    }
  }

  const text = await res.text();
  const body = text ? JSON.parse(text) : null;

  if (!res.ok) {
    if (res.status === 401) clearTokens();
    const err = body as { error?: { code: string; message: string } } | null;
    throw new ApiClientError(
      err?.error?.message || `HTTP ${res.status}`,
      err?.error?.code || "http_error",
      res.status,
    );
  }
  return body as T;
}
