"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";
import { fetchConversations, type ConversationSummary } from "@/lib/conversations";
import { fetchCustomers, type Customer } from "@/lib/customers";
import { fetchOrders, type Order } from "@/lib/orders";

/** The Dashboard (Phase 10): real values derived from the backend APIs —
 * never manufactured numbers. */
export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [customers, setCustomers] = useState<Customer[] | null>(null);

  const load = useCallback(async () => {
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
      setOrders([]);
      setConversations([]);
      setCustomers([]);
      setLoading(false);
      return;
    }
    const [ordersResult, conversationsResult, customersResult] = await Promise.all([
      fetchOrders(tenantId),
      fetchConversations(tenantId),
      fetchCustomers(tenantId),
    ]);
    if (ordersResult.status === 0 || conversationsResult.status === 0 || customersResult.status === 0) {
      setError("API is not reachable. Is the backend running?");
      setLoading(false);
      return;
    }
    setOrders(ordersResult.ok ? ordersResult.data : []);
    setConversations(conversationsResult.ok ? conversationsResult.data : []);
    setCustomers(customersResult.ok ? customersResult.data : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState />;

  if (!user) return <ErrorState message="Please sign in to view your dashboard." />;

  const confirmed = (orders ?? []).filter((o) => o.status === "confirmed").length;
  const needsReview = (orders ?? []).filter(
    (o) => o.status === "needs_review" || o.status === "new",
  ).length;
  const activeConversations = (conversations ?? []).length;
  const completed = (orders ?? []).filter((o) => o.status === "completed").length;

  const stats = [
    { label: "New / needs review", value: needsReview, href: "/orders" },
    { label: "Confirmed orders", value: confirmed, href: "/orders" },
    { label: "Completed orders", value: completed, href: "/orders" },
    { label: "Conversations", value: activeConversations, href: "/conversations" },
  ];

  const recent = (conversations ?? []).slice(0, 5);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Signed in as ${user.email}`}
        actions={
          <Link
            href="/orders"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
          >
            Review orders
          </Link>
        }
      />

      {error && <ErrorState message={error} />}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <Link key={stat.label} href={stat.href} className="group">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow group-hover:shadow-md">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {stat.label}
              </p>
              <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
                {stat.value}
              </p>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-6">
        <Card title="Recent conversations">
          {recent.length === 0 ? (
            <EmptyState
              message="No conversations yet."
              hint="Connect WhatsApp or Instagram in Integrations to start receiving conversations."
            />
          ) : (
            <ul className="flex flex-col divide-y divide-slate-100">
              {recent.map((conversation) => (
                <li key={conversation.id} className="py-3">
                  <Link
                    href={`/conversations?c=${conversation.id}`}
                    className="flex items-center justify-between gap-4 hover:text-indigo-600"
                  >
                    <span className="truncate text-sm text-slate-700">
                      {conversation.latest_message ?? "(no messages)"}
                    </span>
                    <span className="shrink-0 text-xs text-slate-400">
                      {conversation.latest_message_at
                        ? new Date(conversation.latest_message_at).toLocaleString()
                        : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
