/**
 * Order management client tests (Phase 8).
 *
 * The mocked fetch replays the backend's ACTUAL contract (app/routers/orders.py).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  fetchOrder,
  fetchOrders,
  processOrder,
  updateOrderItems,
} from "./orders";
import { setToken } from "./auth";

const TOKEN = "test-session-token-value";
const TENANT = "11111111-1111-1111-1111-111111111111";
const ORDER = "33333333-3333-3333-3333-333333333333";

const ORDER_NEW = {
  id: ORDER,
  status: "new",
  customer_id: "44444444-4444-4444-4444-444444444444",
  extraction_candidate_id: "55555555-5555-5555-5555-555555555555",
  items: [
    { id: "66666666-6666-6666-6666-666666666666", product: "shirt", quantity: 2, variant: null, size: "large", color: "blue" },
  ],
};

const ERROR_BODY = (code: string, message: string) => ({
  error: { code, message },
  request_id: "0123456789abcdef0123456789abcdef",
});

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function headerOf(init?: RequestInit, name = "Authorization"): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.[name];
}

/** Route the mocked fetch exactly like the backend router table. */
function mockBackend() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const authed = headerOf(init) === `Bearer ${TOKEN}`;

    if (url.endsWith("/orders") && method === "GET") {
      if (!authed) {
        return jsonResponse(401, ERROR_BODY("unauthorized", "Authentication required."));
      }
      return jsonResponse(200, [ORDER_NEW]);
    }
    if (url.endsWith(`/orders/${ORDER}`) && method === "GET") {
      if (!authed) return jsonResponse(401, ERROR_BODY("unauthorized", "Authentication required."));
      return jsonResponse(200, ORDER_NEW);
    }
    if (/\/orders\/[0-9a-f-]+$/.test(url) && method === "PATCH") {
      if (!authed) return jsonResponse(401, ERROR_BODY("unauthorized", "Authentication required."));
      const body = JSON.parse(String(init?.body));
      if (!body.items?.length) {
        return jsonResponse(422, { error: { code: "validation_error", message: "Request validation failed." } });
      }
      return jsonResponse(200, {
        ...ORDER_NEW,
        items: body.items.map((item: Record<string, unknown>, index: number) => ({
          id: `66666666-6666-6666-6666-66666666666${index}`,
          variant: null,
          color: null,
          ...item,
        })),
      });
    }
    for (const action of ["confirm", "process", "complete", "cancel"]) {
      if (url.endsWith(`/orders/${ORDER}/${action}`) && method === "POST") {
        if (!authed) {
          return jsonResponse(401, ERROR_BODY("unauthorized", "Authentication required."));
        }
        const next = { confirm: "confirmed", process: "processing", complete: "completed", cancel: "cancelled" }[action];
        return jsonResponse(200, { ...ORDER_NEW, status: next });
      }
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

describe("order listing", () => {
  it("returns the tenant's orders with the auth header", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);
    const result = await fetchOrders(TENANT);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual([ORDER_NEW]);
    }
    expect(headerOf(fetchMock.mock.calls[0]?.[1])).toBe(`Bearer ${TOKEN}`);
  });

  it("fails safely without a token", async () => {
    vi.stubGlobal("fetch", mockBackend());
    const result = await fetchOrders(TENANT);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(401);
  });
});

describe("order inspection", () => {
  it("returns the order with its items", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await fetchOrder(TENANT, ORDER);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.items[0].product).toBe("shirt");
      expect(result.data.items[0].quantity).toBe(2);
    }
  });

  it("surfaces a missing order (404)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, ERROR_BODY("not_found", "Order not found."))),
    );
    setToken(TOKEN);
    const result = await fetchOrder(TENANT, ORDER);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(404);
  });
});

describe("seller review actions", () => {
  it("confirms an order", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);
    const result = await confirmOrder(TENANT, ORDER);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.status).toBe("confirmed");
    }
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/confirm");
  });

  it("processes and completes an order", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const processed = await processOrder(TENANT, ORDER);
    const completed = await completeOrder(TENANT, ORDER);
    expect(processed.ok && processed.data.status).toBe("processing");
    expect(completed.ok && completed.data.status).toBe("completed");
  });

  it("cancels an order", async () => {
    vi.stubGlobal("fetch", mockBackend());
    setToken(TOKEN);
    const result = await cancelOrder(TENANT, ORDER);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.status).toBe("cancelled");
    }
  });

  it("surfaces invalid transitions (400)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(400, ERROR_BODY("invalid_transition", "Invalid order transition: completed -> processing")),
      ),
    );
    setToken(TOKEN);
    const result = await processOrder(TENANT, ORDER);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(400);
    if (!result.ok) {
      expect(result.error?.code).toBe("invalid_transition");
    }
  });
});

describe("order item correction", () => {
  it("sends the corrected items (PATCH)", async () => {
    const fetchMock = mockBackend();
    vi.stubGlobal("fetch", fetchMock);
    setToken(TOKEN);
    const result = await updateOrderItems(TENANT, ORDER, [
      { product: "pizza", quantity: 5 },
    ]);
    expect(result.ok).toBe(true);
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).toEqual({ items: [{ product: "pizza", quantity: 5 }] });
  });

  it("surfaces validation failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(422, { error: { code: "validation_error", message: "Request validation failed." } }),
      ),
    );
    setToken(TOKEN);
    const result = await updateOrderItems(TENANT, ORDER, [
      { product: "", quantity: 0 },
    ]);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(422);
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
    const result = await fetchOrders(TENANT);
    expect(result.ok).toBe(false);
    expect(result.status).toBe(0);
    if (!result.ok) {
      expect(result.error?.code).toBe("network_error");
    }
  });
});
