/** Conversations client (Phase 10) — wired to the backend's actual contract. */

import { apiFetch, type ApiResult } from "./auth";

export type ConversationSummary = {
  id: string;
  customer_id: string;
  status: string;
  latest_message: string | null;
  latest_message_at: string | null;
};

export type ConversationThread = {
  id: string;
  customer_id: string;
  status: string;
  intent: string;
  order_id: string | null;
  order_status: string | null;
  messages: {
    id: string;
    external_event_id: string | null;
    message_type: string;
    body: string | null;
    created_at: string | null;
  }[];
};

export function fetchConversations(
  tenantId: string,
): Promise<ApiResult<ConversationSummary[]>> {
  return apiFetch<ConversationSummary[]>(`/tenants/${tenantId}/conversations`);
}

export function fetchConversationThread(
  tenantId: string,
  conversationId: string,
): Promise<ApiResult<ConversationThread>> {
  return apiFetch<ConversationThread>(
    `/tenants/${tenantId}/conversations/${conversationId}`,
  );
}
