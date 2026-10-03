/** Customers client (Phase 10) — wired to the backend contract. */

import { apiFetch, type ApiResult } from "./auth";

export type Customer = {
  id: string;
  identities: { platform: string; external_user_id: string }[];
  order_count: number;
  last_order_at: string | null;
};

export function fetchCustomers(tenantId: string): Promise<ApiResult<Customer[]>> {
  return apiFetch<Customer[]>(`/tenants/${tenantId}/customers`);
}
