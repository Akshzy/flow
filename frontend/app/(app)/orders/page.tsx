"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";
import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  fetchOrders,
  processOrder,
  type Order,
} from "@/lib/orders";

const STATUS_LABELS: Record<string, string> = {
  new: "New",
  needs_review: "Needs Review",
  confirmed: "Confirmed",
  processing: "Processing",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
};

export default function OrdersPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actingOrderId, setActingOrderId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const me = await fetchMe();
    setUser(me);
    if (me === null) {
      setOrders(null);
      setLoading(false);
      return;
    }
    const tenantId = getSelectedTenantId();
    if (!tenantId) {
      setOrders([]);
      setLoading(false);
      return;
    }
    const result = await fetchOrders(tenantId);
    if (result.ok) {
      setOrders(result.data);
    } else if (result.status === 0) {
      setError("API is not reachable. Is the backend running?");
    } else {
      setError(
        result.error?.message ??
          `Could not load the orders (HTTP ${result.status}).`,
      );
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(
    orderId: string,
    action: (t: string, o: string) => Promise<{ ok: boolean; status: number; error?: { message: string } }>,
  ) {
    setActionError(null);
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActingOrderId(orderId);
    const result = await action(tenantId, orderId);
    setActingOrderId(null);
    if (result.ok) {
      await load();
      return;
    }
    if (result.status === 0) {
      setActionError("API is not reachable. Is the backend running?");
    } else {
      setActionError(
        result.error?.message ?? `The action failed (HTTP ${result.status}).`,
      );
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-20">
        <p className="text-slate-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      <p className="text-xs uppercase tracking-wide text-slate-500">
        <Link href="/" className="font-medium text-slate-900 underline">
          Floww
        </Link>{" "}
        / Orders
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">Orders</h1>

      {error && (
        <p role="alert" className="text-sm font-medium text-red-600">
          {error}
        </p>
      )}

      {!user && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium">Sign in to continue</h2>
          <Link
            href="/login"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Sign in
          </Link>
        </section>
      )}

      {user && !error && orders && orders.length === 0 && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-600">
            No orders yet. Orders appear here when messages from your connected
            channels are processed.
          </p>
        </section>
      )}

      {user && !error && orders && orders.length > 0 && (
        <section className="flex flex-col gap-3">
          {orders.map((order) => (
            <article
              key={order.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-medium text-slate-900">
                  Order{" "}
                  <span className="font-mono text-xs text-slate-500">
                    {order.id.slice(0, 8)}
                  </span>
                </h2>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-700">
                  {STATUS_LABELS[order.status] ?? order.status}
                </span>
              </div>

              <ul className="mt-3 flex flex-col gap-1">
                {order.items.map((item) => (
                  <li key={item.id} className="text-sm text-slate-700">
                    <span className="font-medium">{item.quantity}×</span>{" "}
                    {item.product}
                    {item.size && <span className="text-slate-500"> · {item.size}</span>}
                    {item.color && <span className="text-slate-500"> · {item.color}</span>}
                    {item.variant && <span className="text-slate-500"> · {item.variant}</span>}
                  </li>
                ))}
              </ul>

              {(order.status === "new" || order.status === "needs_review") && (
                <p className="mt-2 text-xs text-amber-700">
                  {order.status === "needs_review"
                    ? "This order needs review — check the extracted items before confirming."
                    : "Awaiting confirmation."}
                </p>
              )}

              {actionError && actingOrderId === order.id && (
                <p role="alert" className="mt-2 text-sm font-medium text-red-600">
                  {actionError}
                </p>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {(order.status === "new" || order.status === "needs_review") && (
                  <button
                    onClick={() => act(order.id, confirmOrder)}
                    disabled={actingOrderId === order.id}
                    className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                  >
                    Confirm
                  </button>
                )}
                {order.status === "confirmed" && (
                  <button
                    onClick={() => act(order.id, processOrder)}
                    disabled={actingOrderId === order.id}
                    className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                  >
                    Start processing
                  </button>
                )}
                {order.status === "processing" && (
                  <button
                    onClick={() => act(order.id, completeOrder)}
                    disabled={actingOrderId === order.id}
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    Mark completed
                  </button>
                )}
                {["new", "needs_review", "confirmed", "processing"].includes(
                  order.status,
                ) && (
                  <button
                    onClick={() => act(order.id, cancelOrder)}
                    disabled={actingOrderId === order.id}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
