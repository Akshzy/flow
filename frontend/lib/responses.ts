/** Controlled responses client (Phase 10) — wired to the backend contract. */

import { apiFetch, type ApiResult } from "./auth";

export type ResponseDraft = {
  id: string;
  conversation_id: string;
  order_id: string | null;
  intent: string;
  origin: string;
  status: string;
  content: string;
  send_attempts: number;
  last_send_error: string | null;
  sent_at: string | null;
};

export function createResponse(
  tenantId: string,
  conversationId: string,
): Promise<ApiResult<ResponseDraft>> {
  return apiFetch<ResponseDraft>(
    `/tenants/${tenantId}/conversations/${conversationId}/responses`,
    { method: "POST" },
  );
}

export function fetchResponse(
  tenantId: string,
  responseId: string,
): Promise<ApiResult<ResponseDraft>> {
  return apiFetch<ResponseDraft>(`/tenants/${tenantId}/responses/${responseId}`);
}

export function editResponse(
  tenantId: string,
  responseId: string,
  content: string,
): Promise<ApiResult<ResponseDraft>> {
  return apiFetch<ResponseDraft>(`/tenants/${tenantId}/responses/${responseId}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export function approveResponse(
  tenantId: string,
  responseId: string,
): Promise<ApiResult<ResponseDraft>> {
  return apiFetch<ResponseDraft>(
    `/tenants/${tenantId}/responses/${responseId}/approve`,
    { method: "POST" },
  );
}

export function sendResponse(
  tenantId: string,
  responseId: string,
  to: string,
  platform: string,
): Promise<ApiResult<ResponseDraft>> {
  return apiFetch<ResponseDraft>(
    `/tenants/${tenantId}/responses/${responseId}/send`,
    { method: "POST", body: JSON.stringify({ to, platform }) },
  );
}
