"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import {
  fetchMe,
  getSelectedTenantId,
  type AuthUser,
} from "@/lib/auth";
import {
  fetchConversationThread,
  fetchConversations,
  type ConversationSummary,
  type ConversationThread,
} from "@/lib/conversations";
import {
  approveResponse,
  createResponse,
  editResponse,
  sendResponse,
  type ResponseDraft,
} from "@/lib/responses";

const INTENT_TONES: Record<string, "success" | "warning" | "neutral"> = {
  order_confirmation: "success",
  unsupported: "warning",
  unknown: "neutral",
};

/** Conversations (Phase 10): the list + the thread + the controlled
 * response workflow — the visual centerpiece. AI SUGGESTED is clearly
 * distinguished from SELLER action; nothing sends without the seller's
 * explicit approval. */
export default function ConversationsPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<ConversationThread | null>(null);
  const [response, setResponse] = useState<ResponseDraft | null>(null);
  const [draftContent, setDraftContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [sendResult, setSendResult] = useState<{ ok: boolean; message: string } | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError(null);
    const me = await fetchMe();
    setUser(me);
    if (me === null) {
      setLoading(false);
      return;
    }
    const tenantId = getSelectedTenantId();
    if (!tenantId) {
      setConversations([]);
      setLoading(false);
      return;
    }
    const result = await fetchConversations(tenantId);
    if (result.status === 0) {
      setError("API is not reachable. Is the backend running?");
    } else {
      setConversations(result.ok ? result.data : []);
      const params = new URLSearchParams(window.location.search);
      const fromQuery = params.get("c");
      const list = result.ok ? result.data : [];
      if (fromQuery && list.some((c) => c.id === fromQuery)) {
        setSelectedId(fromQuery);
      } else if (list.length > 0) {
        setSelectedId((current) => current ?? list[0].id);
      }
    }
    setLoading(false);
  }, []);

  const loadThread = useCallback(async (conversationId: string) => {
    setActionError(null);
    setSendResult(null);
    setResponse(null);
    setEditing(false);
    setDraftContent("");
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    const result = await fetchConversationThread(tenantId, conversationId);
    if (result.ok) {
      setThread(result.data);
    } else if (result.status === 0) {
      setError("API is not reachable. Is the backend running?");
    } else {
      setThread(null);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedId) void loadThread(selectedId);
  }, [selectedId, loadThread]);

  async function handleGenerate() {
    if (!selectedId || !thread) return;
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    setActionError(null);
    const result = await createResponse(tenantId, selectedId);
    setActing(false);
    if (result.ok) {
      setResponse(result.data);
      setDraftContent(result.data.content);
    } else {
      setActionError(
        result.error?.message ?? `Could not generate a response (HTTP ${result.status}).`,
      );
    }
  }

  async function handleSaveEdit() {
    if (!response) return;
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    const result = await editResponse(tenantId, response.id, draftContent);
    setActing(false);
    if (result.ok) {
      setResponse(result.data);
      setEditing(false);
    } else {
      setActionError(result.error?.message ?? "Could not save the edit.");
    }
  }

  async function handleApprove() {
    if (!response) return;
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    const result = await approveResponse(tenantId, response.id);
    setActing(false);
    if (result.ok) {
      setResponse(result.data);
    } else {
      setActionError(result.error?.message ?? "Could not approve.");
    }
  }

  async function handleSend() {
    if (!response || !thread) return;
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    const platform = "whatsapp";
    const to = thread.customer_id;
    const result = await sendResponse(tenantId, response.id, to, platform);
    setActing(false);
    if (result.ok) {
      setResponse(result.data);
      setSendResult({ ok: true, message: "Sent." });
    } else {
      setSendResult({
        ok: false,
        message:
          result.error?.message ?? `Send failed (HTTP ${result.status}). You can retry.`,
      });
    }
  }

  if (loading) return <LoadingState />;
  if (!user) return <ErrorState message="Please sign in to view your conversations." />;

  return (
    <>
      <PageHeader title="Conversations" description="Messages from your connected channels." />

      {error && <ErrorState message={error} />}

      {!error && conversations && conversations.length === 0 && (
        <EmptyState
          message="No conversations yet."
          hint="Connect WhatsApp or Instagram in Integrations to start receiving conversations."
        />
      )}

      {!error && conversations && conversations.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
          <Card title="Conversations" className="h-fit">
            <ul className="flex flex-col gap-1">
              {conversations.map((conversation) => (
                <li key={conversation.id}>
                  <button
                    onClick={() => setSelectedId(conversation.id)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                      conversation.id === selectedId
                        ? "bg-indigo-50 text-indigo-900"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <span className="block truncate text-sm font-medium">
                      {conversation.latest_message ?? "(no messages)"}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-400">
                      {conversation.latest_message_at
                        ? new Date(conversation.latest_message_at).toLocaleString()
                        : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          <div className="flex min-w-0 flex-col gap-4">
            {thread && (
              <>
                <Card title="Context">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="text-slate-500">Customer:</span>
                    <span className="font-mono text-xs text-slate-700">
                      {thread.customer_id.slice(0, 8)}
                    </span>
                    <Badge tone={INTENT_TONES[thread.intent] ?? "neutral"}>
                      {thread.intent}
                    </Badge>
                    {thread.order_id && (
                      <Link
                        href={`/orders/${thread.order_id}`}
                        className="text-xs font-medium text-indigo-600 underline"
                      >
                        Order ({thread.order_status})
                      </Link>
                    )}
                  </div>
                </Card>

                <Card title="Conversation">
                  <ul className="flex flex-col gap-2">
                    {thread.messages.map((message) => (
                      <li
                        key={message.id}
                        className="max-w-[85%] rounded-xl bg-slate-100 px-3.5 py-2 text-sm text-slate-800"
                      >
                        {message.body ?? `(${message.message_type})`}
                        <span className="mt-0.5 block text-[10px] text-slate-400">
                          {message.created_at
                            ? new Date(message.created_at).toLocaleString()
                            : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card title="Response">
                  {!response && (
                    <div>
                      {thread.intent !== "order_confirmation" && (
                        <p className="text-sm text-slate-600">
                          This conversation has no confirmed order yet, so no
                          response can be generated. Confirm an order first.
                        </p>
                      )}
                      <button
                        onClick={handleGenerate}
                        disabled={acting || thread.intent !== "order_confirmation"}
                        className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                      >
                        {acting ? "Working…" : "Generate AI suggested response"}
                      </button>
                    </div>
                  )}

                  {response && (
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2">
                        <Badge tone={response.origin === "ai_suggested" ? "info" : "neutral"}>
                          {response.origin === "ai_suggested" ? "AI SUGGESTED" : "SELLER WRITTEN"}
                        </Badge>
                        <Badge tone={response.status === "sent" ? "success" : response.status === "approved" ? "warning" : "neutral"}>
                          {response.status.toUpperCase()}
                        </Badge>
                      </div>

                      {editing ? (
                        <div className="flex flex-col gap-2">
                          <label className="sr-only" htmlFor="response-content">
                            Response content
                          </label>
                          <textarea
                            id="response-content"
                            value={draftContent}
                            onChange={(event) => setDraftContent(event.target.value)}
                            rows={4}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={handleSaveEdit}
                              disabled={acting}
                              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => {
                                setEditing(false);
                                setDraftContent(response.content);
                              }}
                              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                            >
                              Cancel edit
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="rounded-lg bg-slate-50 p-3">
                          <p className="text-sm text-slate-800">{response.content}</p>
                          {response.status === "draft" && (
                            <button
                              onClick={() => setEditing(true)}
                              className="mt-2 text-xs font-medium text-indigo-600 underline"
                            >
                              Edit
                            </button>
                          )}
                        </div>
                      )}

                      {sendResult && (
                        <p
                          role="status"
                          className={`text-sm font-medium ${
                            sendResult.ok ? "text-emerald-600" : "text-red-600"
                          }`}
                        >
                          {sendResult.ok ? "Sent" : sendResult.message}
                        </p>
                      )}

                      {response.status === "draft" && (
                        <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                          <button
                            onClick={handleApprove}
                            disabled={acting}
                            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                          >
                            {acting ? "Working…" : "Approve"}
                          </button>
                        </div>
                      )}

                      {response.status === "approved" && (
                        <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                          <button
                            onClick={handleSend}
                            disabled={acting}
                            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                          >
                            {acting ? "Sending…" : "Approve & Send"}
                          </button>
                        </div>
                      )}

                      {response.status === "sent" && (
                        <p className="text-xs text-slate-500">
                          Sent
                          {response.sent_at
                            ? ` at ${new Date(response.sent_at).toLocaleString()}`
                            : ""}
                          . The seller approved this response.
                        </p>
                      )}

                      {response.last_send_error && response.status !== "sent" && (
                        <p className="text-xs text-red-600">
                          Last send error: {response.last_send_error}
                        </p>
                      )}
                    </div>
                  )}

                  {actionError && (
                    <p role="alert" className="mt-3 text-sm font-medium text-red-600">
                      {actionError}
                    </p>
                  )}
                </Card>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
