"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge, Card, ErrorState, LoadingState } from "@/components/ui";
import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";
import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  fetchOrder,
  fetchOrderEvents,
  processOrder,
  type Order,
  type OrderEvent,
} from "@/lib/orders";

const STATUS_TONES: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  new: "info",
  needs_review: "warning",
  confirmed: "info",
  processing: "info",
  completed: "success",
  cancelled: "danger",
  failed: "danger",
};

/** Order detail (Phase 10): structured around the business workflow — the
 * header, the customer, the items, the delivery address (first-class, with
 * an explicit missing state — the backend has no address data, so it is
 * never invented), and the real lifecycle timeline. */
export default function OrderDetailPage() {
  const params = useParams<{ orderId: string }>();
  const orderId = params?.orderId;
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [events, setEvents] = useState<OrderEvent[] | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    if (!orderId) return;
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
      setError("No business selected. Open the dashboard first.");
      setLoading(false);
      return;
    }
    const [orderResult, eventsResult] = await Promise.all([
      fetchOrder(tenantId, orderId),
      fetchOrderEvents(tenantId, orderId),
    ]);
    if (orderResult.status === 404) {
      setError("Order not found.");
      setLoading(false);
      return;
    }
    if (orderResult.status === 403) {
      setError("You do not have access to this order.");
      setLoading(false);
      return;
    }
    if (orderResult.status === 0) {
      setError("API is not reachable. Is the backend running?");
      setLoading(false);
      return;
    }
    setOrder(orderResult.ok ? orderResult.data : null);
    setEvents(eventsResult.ok ? eventsResult.data : null);
    setLoading(false);
  }, [orderId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(
    action: (t: string, o: string) => Promise<{ ok: boolean; status: number; error?: { message: string } }>,
  ) {
    const tenantId = getSelectedTenantId();
    if (!tenantId || !order) return;
    setActing(true);
    setActionError(null);
    const result = await action(tenantId, order.id);
    setActing(false);
    if (result.ok) {
      await load();
      return;
    }
    setActionError(
      result.error?.message ?? `The action failed (HTTP ${result.status}).`,
    );
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!user) return <ErrorState message="Please sign in." />;
  if (!order) return <ErrorState message="Order not found." />;

  const actionable = ["new", "needs_review", "confirmed", "processing"].includes(
    order.status,
  );

  return (
    <>
      <p className="text-xs uppercase tracking-wide text-slate-500">
        <Link href="/orders" className="font-medium text-slate-900 underline">
          Orders
        </Link>{" "}
        / {order.id.slice(0, 8)}
      </p>

      <div className="mt-2 mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Order <span className="font-mono text-lg">{order.id.slice(0, 8)}</span>
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Customer <span className="font-mono text-xs">{order.customer_id.slice(0, 8)}</span>
          </p>
        </div>
        <Badge tone={STATUS_TONES[order.status] ?? "neutral"}>
          {(STATUS_TONES[order.status] ?? order.status).toUpperCase()}
        </Badge>
      </div>

      {actionError && (
        <p role="alert" className="mb-4 text-sm font-medium text-red-600">
          {actionError}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Order items">
          <ul className="flex flex-col divide-y divide-slate-100">
            {order.items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="text-sm text-slate-800">
                  <span className="font-medium">{item.quantity}×</span> {item.product}
                  {item.size && <span className="text-slate-500"> · {item.size}</span>}
                  {item.color && <span className="text-slate-500"> · {item.color}</span>}
                  {item.variant && <span className="text-slate-500"> · {item.variant}</span>}
                </span>
              </li>
            ))}
          </ul>
        </Card>

        {/* Delivery address — FIRST-CLASS, with an explicit missing state.
            The backend has no address data; it is never invented. */}
        <Card title="Delivery address">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm font-medium text-amber-800">
              Delivery address missing
            </p>
            <p className="mt-1 text-xs text-amber-700">
              The customer has not provided a delivery address yet. Floww does
              not guess addresses — the seller should request it from the
              customer.
            </p>
          </div>
        </Card>

        <Card title="Lifecycle">
          <ol className="flex flex-col gap-2">
            {(events ?? []).map((event, index) => (
              <li key={index} className="flex items-start gap-3 text-sm">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-500" />
                <span>
                  <span className="font-medium text-slate-800">{event.event}</span>
                  {event.from_status && event.to_status && (
                    <span className="text-slate-500">
                      {" "}
                      ({event.from_status} → {event.to_status})
                    </span>
                  )}
                  {event.detail && (
                    <span className="block text-xs text-slate-500">{event.detail}</span>
                  )}
                  {event.created_at && (
                    <span className="block text-[10px] text-slate-400">
                      {new Date(event.created_at).toLocaleString()}
                    </span>
                  )}
                </span>
              </li>
            ))}
            {(events ?? []).length === 0 && (
              <li className="text-sm text-slate-500">No lifecycle events yet.</li>
            )}
          </ol>
        </Card>

        {actionable && (
          <Card title="Seller actions">
            <div className="flex flex-wrap gap-2">
              {(order.status === "new" || order.status === "needs_review") && (
                <button
                  onClick={() => act(confirmOrder)}
                  disabled={acting}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  Confirm order
                </button>
              )}
              {order.status === "confirmed" && (
                <button
                  onClick={() => act(processOrder)}
                  disabled={acting}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  Start processing
                </button>
              )}
              {order.status === "processing" && (
                <button
                  onClick={() => act(completeOrder)}
                  disabled={acting}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Mark completed
                </button>
              )}
              <button
                onClick={() => act(cancelOrder)}
                disabled={acting}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel order
              </button>
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
