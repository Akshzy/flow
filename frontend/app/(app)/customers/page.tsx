"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge, Card, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";
import { fetchCustomers, type Customer } from "@/lib/customers";

/** Customers (Phase 10): the customer, the platform identities, and the
 * order count — only data the backend supports. */
export default function CustomersPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      setCustomers([]);
      setLoading(false);
      return;
    }
    const result = await fetchCustomers(tenantId);
    if (result.status === 0) {
      setError("API is not reachable. Is the backend running?");
    } else {
      setCustomers(result.ok ? result.data : []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState />;
  if (!user) return <ErrorState message="Please sign in to view your customers." />;

  return (
    <>
      <PageHeader title="Customers" description="Customers from your connected channels." />
      {error && <ErrorState message={error} />}
      {!error && customers && customers.length === 0 && (
        <EmptyState message="No customers yet." hint="Customers appear when messages are processed." />
      )}
      {!error && customers && customers.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
                  <th className="py-2.5 pr-4 font-semibold">Customer</th>
                  <th className="py-2.5 pr-4 font-semibold">Platform identities</th>
                  <th className="py-2.5 pr-4 font-semibold">Orders</th>
                  <th className="py-2.5 font-semibold">Last order</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="py-2.5 pr-4 font-mono text-xs text-slate-700">
                      {customer.id.slice(0, 8)}
                    </td>
                    <td className="py-2.5 pr-4">
                      <span className="flex flex-wrap gap-1">
                        {customer.identities.map((identity, index) => (
                          <Badge key={index} tone="info">
                            {identity.platform}: {identity.external_user_id}
                          </Badge>
                        ))}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-700">{customer.order_count}</td>
                    <td className="py-2.5 text-xs text-slate-500">
                      {customer.last_order_at
                        ? new Date(customer.last_order_at).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
