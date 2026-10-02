/**
 * Order management client (Phase 8).
 *
 * Wired to the backend's actual contract (app/routers/orders.py):
 * - GET   /tenants/{tenantId}/orders                       → list (tenant-scoped)
 * - GET   /tenants/{tenantId}/orders/{orderId}             → inspect (with items)
 * - GET   /tenants/{tenantId}/orders/{orderId}/events      → audit history
 * - PATCH /tenants/{tenantId}/orders/{orderId}             → correct items (owner)
 * - POST  /tenants/{tenantId}/orders/{orderId}/confirm     → CONFIRMED (owner)
 * - POST  /tenants/{tenantId}/orders/{orderId}/process     → PROCESSING (owner)
 * - POST  /tenants/{tenantId}/orders/{orderId}/complete    → COMPLETED (owner)
 * - POST  /tenants/{tenantId}/orders/{orderId}/cancel      → CANCELLED (owner)
 *
 * Authorization stays server-side: every call is scoped by the caller's
 * bearer token; the seller's confirm action IS the human-review decision.
 */

import { apiFetch, type ApiResult } from "./auth";

export type OrderItem = {
  id: string;
  product: string;
  quantity: number;
  variant: string | null;
  size: string | null;
  color: string | null;
};

export type Order = {
  id: string;
  status: string;
  customer_id: string;
  extraction_candidate_id: string;
  items: OrderItem[];
};

export type OrderEvent = {
  event: string;
  from_status: string | null;
  to_status: string | null;
  actor_user_id: string | null;
  detail: string | null;
};

export function fetchOrders(tenantId: string): Promise<ApiResult<Order[]>> {
  return apiFetch<Order[]>(`/tenants/${tenantId}/orders`);
}

export function fetchOrder(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}`);
}

export function fetchOrderEvents(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<OrderEvent[]>> {
  return apiFetch<OrderEvent[]>(`/tenants/${tenantId}/orders/${orderId}/events`);
}

export function confirmOrder(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}/confirm`, {
    method: "POST",
  });
}

export function processOrder(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}/process`, {
    method: "POST",
  });
}

export function completeOrder(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}/complete`, {
    method: "POST",
  });
}

export function cancelOrder(
  tenantId: string,
  orderId: string,
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}/cancel`, {
    method: "POST",
  });
}

export function updateOrderItems(
  tenantId: string,
  orderId: string,
  items: { product: string; quantity: number }[],
): Promise<ApiResult<Order>> {
  return apiFetch<Order>(`/tenants/${tenantId}/orders/${orderId}`, {
    method: "PATCH",
    body: JSON.stringify({ items }),
  });
}
