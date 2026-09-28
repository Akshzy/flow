/**
 * Frontend authentication client tests (Phase 2).
 *
 * The mocked fetch replays the backend's ACTUAL contract (exact routes,
 * status codes and response shapes implemented in app/routers/auth.py and
 * app/routers/tenants.py) so the client behavior is tested at the network
 * boundary against the real API contract. Live end-to-end verification
 * against the running backend is performed separately (see HANDOFF_02).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  authHeaders,
  clearSelectedTenantId,
  clearToken,
  createTenant,
  fetchMe,
  fetchTenants,
  getSelectedTenantId,
  getToken,
  login,
  logout,
  register,
  setSelectedTenantId,
  setToken,
} from "./auth";

// --- Backend contract fixtures (exact shapes from the backend) --------------

const USER = {
  id: "64349b1a-72e1-4dc3-a5db-9999d06db836",
  email: "user1@example.com",
  status: "active",
  created_at: "2026-09-28T12:00:00Z",
};

const TOKEN = "test-session-token-value";
const ERROR_BODY = (code: string, message: string) => ({
  error: { code, message },
  request_id: "0123456789abcdef0123456789abcdef",
});

function headerOf(init?: RequestInit, name = "Authorization"): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.[name];
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Route the mocked fetch exactly like the backend router table. */
function mockBackend() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.endsWith("/auth/register") && method === "POST") {
      const body = JSON.parse(String(init?.body));
      if (body.email === "taken@example.com") {
        return jsonResponse(
          409,
          ERROR_BODY("conflict", "An account with this email already exists."),
        );
      }
      if (body.password.length < 8 || !body.email.includes("@")) {
        return jsonResponse(422, {
          error: {
            code: "validation_error",
            message: "Request validation failed.",
            details: { errors: [{ loc: ["body", "email"], msg: "invalid" }] },
          },
          request_id: "0123456789abcdef0123456789abcdef",
        });
      }
      // The backend returns the created user's own identity.
      return jsonResponse(201, { ...USER, email: body.email });
    }

    if (url.endsWith("/auth/login") && method === "POST") {
      const body = JSON.parse(String(init?.body));
      if (body.email === "user1@example.com" && body.password === "password-123") {
        return jsonResponse(200, {
          token: TOKEN,
          token_type: "bearer",
          expires_at: "2026-10-05T12:00:00Z",
          user: USER,
        });
      }
      return jsonResponse(
        401,
        ERROR_BODY("invalid_credentials", "Invalid email or password."),
      );
    }

    if (url.endsWith("/auth/me") && method === "GET") {
      const auth = headerOf(init);
      if (auth === `Bearer ${TOKEN}`) {
        return jsonResponse(200, USER);
      }
      return jsonResponse(
        401,
        ERROR_BODY("unauthorized", "Authentication required."),
      );
    }

    if (url.endsWith("/auth/logout") && method === "POST") {
      return jsonResponse(200, { status: "ok", logged_out: true });
    }

    if (url.endsWith("/tenants") && method === "GET") {
      const auth = headerOf(init);
      if (auth === `Bearer ${TOKEN}`) {
        return jsonResponse(200, [
          {
            id: "11111111-1111-1111-1111-111111111111",
            name: "Tenant A Business",
            status: "active",
            created_at: "2026-09-28T12:00:00Z",
            role: "owner",
          },
          {
            id: "22222222-2222-2222-2222-222222222222",
            name: "Second Shop",
            status: "active",
            created_at: "2026-09-28T12:01:00Z",
            role: "member",
          },
        ]);
      }
      return jsonResponse(
        401,
        ERROR_BODY("unauthorized", "Authentication required."),
      );
    }

    if (url.endsWith("/tenants") && method === "POST") {
      const auth = headerOf(init);
      if (auth !== `Bearer ${TOKEN}`) {
        return jsonResponse(
          401,
          ERROR_BODY("unauthorized", "Authentication required."),
        );
      }
      const body = JSON.parse(String(init?.body));
      if (!body.name) {
        return jsonResponse(422, {
          error: { code: "validation_error", message: "Request validation failed." },
          request_id: "0123456789abcdef0123456789abcdef",
        });
      }
      return jsonResponse(201, {
        id: "33333333-3333-3333-3333-333333333333",
        name: body.name,
        status: "active",
        created_at: "2026-09-28T12:02:00Z",
        role: "owner",
      });
    }

    return new Response("Not Found", { status: 404 });
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

// --- Token storage helpers ---------------------------------------------------

describe("token storage", () => {
  it("stores, reads and clears the session token", () => {
    expect(getToken()).toBeNull();
    setToken(TOKEN);
    expect(getToken()).toBe(TOKEN);
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("builds bearer auth headers only when a token exists", () => {
    expect(authHeaders()).toEqual({});
    setToken(TOKEN);
    expect(authHeaders()).toEqual({ Authorization: `Bearer ${TOKEN}` });
  });
});

describe("selected tenant persistence", () => {
  it("stores, reads and clears the selected tenant id", () => {
    expect(getSelectedTenantId()).toBeNull();
    setSelectedTenantId("22222222-2222-2222-2222-222222222222");
    expect(getSelectedTenantId()).toBe("22222222-2222-2222-2222-222222222222");
    clearSelectedTenantId();
    expect(getSelectedTenantId()).toBeNull();
  });
});

// --- Authentication flows -----------------------------------------------------

describe("login", () => {
  it("stores the token on success", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await login("user1@example.com", "password-123");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.token).toBe(TOKEN);
      expect(result.data.user.email).toBe("user1@example.com");
    }
    expect(getToken()).toBe(TOKEN);
  });

  it("returns a safe error on invalid credentials and stores no token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await login("user1@example.com", "wrong-password");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
    if (!result.ok) {
      expect(result.error?.code).toBe("invalid_credentials");
      // The safe message must not reveal whether the account exists.
      expect(result.error?.message).toBe("Invalid email or password.");
    }
    expect(getToken()).toBeNull();
  });
});

describe("registration", () => {
  it("returns the created user without storing a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await register("new-user@example.com", "password-123");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.email).toBe("new-user@example.com");
    }
    // Registration alone does not authenticate; login does.
    expect(getToken()).toBeNull();
  });

  it("surfaces duplicate accounts", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await register("taken@example.com", "password-123");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(409);
    if (!result.ok) {
      expect(result.error?.code).toBe("conflict");
    }
  });

  it("surfaces validation failures", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await register("not-an-email", "short");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(422);
    if (!result.ok) {
      expect(result.error?.code).toBe("validation_error");
    }
  });
});

describe("logout", () => {
  it("invalidates the backend session and clears the frontend state", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);
    setSelectedTenantId("11111111-1111-1111-1111-111111111111");

    await logout();

    // The backend logout endpoint was invoked.
    const logoutCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/auth/logout") &&
        (init?.method ?? "GET").toUpperCase() === "POST",
    );
    expect(logoutCall).toBeDefined();

    // Frontend auth state (token + selected tenant) is cleared.
    expect(getToken()).toBeNull();
    expect(getSelectedTenantId()).toBeNull();
  });
});

// --- Authenticated state handling ---------------------------------------------

describe("fetchMe", () => {
  it("returns the user for a valid session", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const me = await fetchMe();
    expect(me).not.toBeNull();
    expect(me?.email).toBe("user1@example.com");
    expect(getToken()).toBe(TOKEN); // token survives a refresh-equivalent call
  });

  it("clears stale tokens on 401 and returns null", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken("expired-or-revoked-token");
    const me = await fetchMe();
    expect(me).toBeNull();
    expect(getToken()).toBeNull();
  });

  it("returns null without a token and performs no request", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    const me = await fetchMe();
    expect(me).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

// --- Tenant loading / creation -------------------------------------------------

describe("fetchTenants", () => {
  it("returns the caller's tenants", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const tenants = await fetchTenants();
    expect(tenants).not.toBeNull();
    expect(tenants?.map((t) => t.name)).toEqual([
      "Tenant A Business",
      "Second Shop",
    ]);
    // Roles come from the backend (owner/member), not from the client.
    expect(tenants?.map((t) => t.role)).toEqual(["owner", "member"]);
  });

  it("fails safely without a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const tenants = await fetchTenants();
    expect(tenants).toBeNull();
  });
});

describe("createTenant", () => {
  it("creates a tenant with the auth header and returns it", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);

    const result = await createTenant("New Business");
    expect(result.ok).toBe(true);

    const call = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/tenants") &&
        (init?.method ?? "GET").toUpperCase() === "POST",
    );
    expect(call).toBeDefined();
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ name: "New Business" });
    expect(headerOf(call?.[1])).toBe(`Bearer ${TOKEN}`);

    if (result.ok) {
      expect(result.data.name).toBe("New Business");
      expect(result.data.role).toBe("owner"); // assigned server-side
    }
  });

  it("fails safely without a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await createTenant("Sneaky Shop");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
    if (!result.ok) {
      expect(result.error?.code).toBe("unauthorized");
    }
  });
});

// --- API failure handling --------------------------------------------------------

describe("API failure handling", () => {
  it("fails safely when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const result = await login("user1@example.com", "password-123");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(0);
    if (!result.ok) {
      expect(result.error?.code).toBe("network_error");
    }
    expect(getToken()).toBeNull();
  });

  it("fails safely on a non-JSON error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Internal Server Error", { status: 500 })),
    );
    const result = await login("user1@example.com", "password-123");
    expect(result.ok).toBe(false);
    expect(result.status).toBe(500);
  });
});
