/**
 * WhatsApp connection client (Phase 4).
 *
 * Wired to the backend's actual contract:
 * - GET    /tenants/{tenantId}/connection          → connection status
 * - POST   /tenants/{tenantId}/connection/initiate → start the lifecycle
 * - DELETE /tenants/{tenantId}/connection          → disconnect (owner only)
 *
 * Authorization stays server-side: every call is scoped by the caller's
 * bearer token; a tenant ID known to the client never grants access.
 * Responses never include credential material or raw Meta payloads.
 */

import { apiFetch, type ApiResult } from "./auth";

export type ConnectionStatus = "disconnected" | "initiated" | "connected";

export type Connection = {
  id: string | null;
  platform: string;
  status: ConnectionStatus;
  waba_id: string | null;
  phone_number_id: string | null;
  connected_at: string | null;
  disconnected_at: string | null;
};

export type InitiateResult = {
  platform: string;
  status: ConnectionStatus;
  detail: string | null;
};

export type PlatformParam = "whatsapp" | "instagram";

export function fetchConnection(
  tenantId: string,
  platform: PlatformParam = "whatsapp",
): Promise<ApiResult<Connection>> {
  return apiFetch<Connection>(`/tenants/${tenantId}/connection?platform=${platform}`);
}

export function initiateConnection(
  tenantId: string,
  platform: PlatformParam = "whatsapp",
): Promise<ApiResult<InitiateResult>> {
  return apiFetch<InitiateResult>(
    `/tenants/${tenantId}/connection/initiate?platform=${platform}`,
    { method: "POST" },
  );
}

export function disconnectConnection(
  tenantId: string,
  platform: PlatformParam = "whatsapp",
): Promise<ApiResult<Connection>> {
  return apiFetch<Connection>(`/tenants/${tenantId}/connection?platform=${platform}`, {
    method: "DELETE",
  });
}
