/**
 * Client-side authentication helpers (Phase 2).
 *
 * - The session token is stored in localStorage and sent as a bearer token.
 *   NOTE: localStorage is XSS-exposed; cookie-based sessions are a later
 *   hardening concern (recorded in HANDOFF_02).
 * - All API calls return {ok, status, data/error} so callers can handle
 *   failures consistently without try/catch noise.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "floww.auth.token";

export type AuthUser = {
  id: string;
  email: string;
  status: string;
  created_at: string;
};

export type Tenant = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  role: string | null;
};

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error?: { code: string; message: string } };

const SELECTED_TENANT_KEY = "floww.auth.selected-tenant";

/**
 * Selected-tenant persistence (frontend state only). The selected tenant ID
 * is never proof of authorization — every tenant-scoped API request is
 * authorized by the backend against the caller's membership.
 */
export function getSelectedTenantId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SELECTED_TENANT_KEY);
}

export function setSelectedTenantId(tenantId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SELECTED_TENANT_KEY, tenantId);
}

export function clearSelectedTenantId(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SELECTED_TENANT_KEY);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
        ...(init.headers ?? {}),
      },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) {
      let error: { code: string; message: string } | undefined;
      try {
        const body = (await response.json()) as { error?: { code: string; message: string } };
        error = body.error;
      } catch {
        // non-JSON error body
      }
      return { ok: false, status: response.status, error };
    }
    if (response.status === 204) {
      return { ok: true, status: 204, data: undefined as T };
    }
    return { ok: true, status: response.status, data: (await response.json()) as T };
  } catch {
    return {
      ok: false,
      status: 0,
      error: { code: "network_error", message: "API is not reachable." },
    };
  }
}

export async function register(
  email: string,
  password: string,
): Promise<ApiResult<AuthUser>> {
  const result = await apiFetch<AuthUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return result;
}

export async function login(
  email: string,
  password: string,
): Promise<ApiResult<{ token: string; user: AuthUser }>> {
  const result = await apiFetch<{ token: string; user: AuthUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (result.ok) {
    setToken(result.data.token);
  }
  return result;
}

export async function logout(): Promise<void> {
  // Invalidate the backend session (best effort) and clear the frontend
  // authentication state, including the selected tenant.
  await apiFetch("/auth/logout", { method: "POST" });
  clearToken();
  clearSelectedTenantId();
}

export async function fetchMe(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  const result = await apiFetch<AuthUser>("/auth/me");
  if (result.status === 401) {
    clearToken(); // stale token (invalid/expired/revoked session)
    return null;
  }
  return result.ok ? result.data : null;
}

export async function fetchTenants(): Promise<Tenant[] | null> {
  const result = await apiFetch<Tenant[]>("/tenants");
  return result.ok ? result.data : null;
}

export async function createTenant(name: string): Promise<ApiResult<Tenant>> {
  return apiFetch<Tenant>("/tenants", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}
