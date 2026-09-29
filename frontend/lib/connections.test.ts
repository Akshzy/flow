/**
 * WhatsApp connection client tests (Phase 4).
 *
 * The mocked fetch replays the backend's ACTUAL contract (exact routes,
 * status codes and response shapes implemented in
 * app/routers/connections.py) so the client behavior is tested at the
 * network boundary against the real API contract.
 *
 * REAL META API TEST = BLOCKED (required credentials unavailable in this
 * environment); these are deterministic local adapter-boundary tests.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  disconnectConnection,
  fetchConnection,
  initiateConnection,
} from "./connections";
import { setToken } from "./auth";

const TOKEN = "test-session-token-value";
const TENANT_A = "11111111-1111-1111-1111-111111111111";
const TENANT_B = "22222222-2222-2222-2222-222222222222";

const CONNECTION_CONNECTED = {
  id: "33333333-3333-3333-3333-333333333333",
  platform: "whatsapp",
  status: "connected",
  waba_id: "999888777",
  phone_number_id: "555666444",
  connected_at: "2026-09-29T12:00:00Z",
  disconnected_at: null,
};

const ERROR_BODY = (code: string, message: string) => ({
  error: { code, message },
  request_id: "0123456789abcdef0123456789abcdef",
});

/**
 * Route the mocked fetch exactly like the backend router table:
 * - GET    /tenants/{id}/connection → status (member) | 403 (non-member)
 * - POST   /tenants/{id}/connection/initiate → 200 initiated | 409 conflict | 403
 * - DELETE /tenants/{id}/connection → 200 disconnected | 404 no active | 403
 */
function mockBackend() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const auth = (init?.headers as Record<string, string> | undefined)?.[
      "Authorization"
    ];
    const authed = auth === `Bearer ${TOKEN}`;

    const match = url.match(/\/tenants\/([0-9a-f-]+)\/connection/);
    const tenantId = match?.[1];

    if (url.endsWith("/connection/initiate") && method === "POST") {
      if (!authed) {
        return jsonResponse(
          401,
          ERROR_BODY("unauthorized", "Authentication required."),
        );
      }
      if (tenantId === TENANT_B) {
        return jsonResponse(
          403,
          ERROR_BODY("forbidden", "You do not have access to this tenant."),
        );
      }
      return jsonResponse(200, {
        platform: "whatsapp",
        status: "initiated",
        detail: "Meta authorization is pending configuration.",
      });
    }

    if (url.endsWith("/connection") && method === "DELETE") {
      if (!authed) {
        return jsonResponse(
          401,
          ERROR_BODY("unauthorized", "Authentication required."),
        );
      }
      if (tenantId === TENANT_B) {
        return jsonResponse(
          403,
          ERROR_BODY("forbidden", "You do not have access to this tenant."),
        );
      }
      return jsonResponse(200, {
        id: CONNECTION_CONNECTED.id,
        platform: "whatsapp",
        status: "disconnected",
        waba_id: null,
        phone_number_id: null,
        connected_at: CONNECTION_CONNECTED.connected_at,
        disconnected_at: "2026-09-29T13:00:00Z",
      });
    }

    if (url.endsWith("/connection") && method === "GET") {
      if (!authed) {
        return jsonResponse(
          401,
          ERROR_BODY("unauthorized", "Authentication required."),
        );
      }
      if (tenantId === TENANT_B) {
        return jsonResponse(
          403,
          ERROR_BODY("forbidden", "You do not have access to this tenant."),
        );
      }
      return jsonResponse(200, {
        id: null,
        platform: "whatsapp",
        status: "disconnected",
        waba_id: null,
        phone_number_id: null,
        connected_at: null,
        disconnected_at: null,
      });
    }

    return new Response("Not Found", { status: 404 });
  });
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("connection status", () => {
  it("returns the initial disconnected state", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await fetchConnection(TENANT_A);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.status).toBe("disconnected");
      expect(result.data.platform).toBe("whatsapp");
      expect(result.data.id).toBeNull();
    }
  });

  it("fails safely without a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await fetchConnection(TENANT_A);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
  });

  it("never contains credential material", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await fetchConnection(TENANT_A);
    if (result.ok) {
      const dumped = JSON.stringify(result.data);
      expect(dumped).not.toContain("access_token");
      expect(dumped).not.toContain("credentials");
      expect(dumped).not.toContain("Bearer");
    }
  });
});

describe("connection initiation", () => {
  it("starts the lifecycle and reports the pending Meta authorization", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);

    const result = await initiateConnection(TENANT_A);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.status).toBe("initiated");
      // No fake Meta success: the detail states authorization is pending.
      expect(result.data.detail).toContain("pending");
    }

    // The initiation call carries the bearer token (server-side authz).
    const call = fetchMock.mock.calls[0];
    expect((call?.[1] as RequestInit).method).toBe("POST");
    expect(
      ((call?.[1] as RequestInit).headers as Record<string, string>)[
        "Authorization"
      ],
    ).toBe(`Bearer ${TOKEN}`);
  });

  it("fails safely without a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await initiateConnection(TENANT_A);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
    if (!result.ok) {
      expect(result.error?.code).toBe("unauthorized");
    }
  });

  it("surfaces duplicate-connection conflicts", async () => {
    // A backend that reports an existing connected connection.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          409,
          ERROR_BODY("conflict", "WhatsApp is already connected for this business."),
        ),
      ),
    );
    const result = await initiateConnection(TENANT_A);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(409);
    if (!result.ok) {
      expect(result.error?.code).toBe("conflict");
    }
  });
});

describe("disconnect", () => {
  it("disconnects and reports the disconnected state", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);

    const result = await disconnectConnection(TENANT_A);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.status).toBe("disconnected");
    }
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("DELETE");
  });

  it("surfaces the no-active-connection failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          404,
          ERROR_BODY("not_found", "No active WhatsApp connection to disconnect."),
        ),
      ),
    );
    const result = await disconnectConnection(TENANT_A);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(404);
    if (!result.ok) {
      expect(result.error?.code).toBe("not_found");
    }
  });
});

// --- Tenant isolation (client boundary; server-side enforcement is the
// real boundary and is verified by the backend tests) ------------------------

describe("tenant isolation", () => {
  it("cross-tenant status access is denied (403)", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await fetchConnection(TENANT_B);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(403);
    if (!result.ok) {
      expect(result.error?.code).toBe("forbidden");
    }
  });

  it("cross-tenant initiation is denied (403)", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await initiateConnection(TENANT_B);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(403);
  });

  it("cross-tenant disconnect is denied (403)", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await disconnectConnection(TENANT_B);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(403);
  });
});

describe("API failure handling", () => {
  it("fails safely when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    setToken(TOKEN);
    const result = await fetchConnection(TENANT_A);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(0);
    if (!result.ok) {
      expect(result.error?.code).toBe("network_error");
    }
  });
});
