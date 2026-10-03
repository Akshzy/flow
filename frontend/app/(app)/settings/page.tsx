"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Card, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";

/** Settings (Phase 10): only ACTUAL backend functionality — the account
 * (from /auth/me) and the selected business. No non-functional settings. */
export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const me = await fetchMe();
    setUser(me);
    setTenantId(getSelectedTenantId());
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState />;
  if (!user) return <ErrorState message="Please sign in to view your settings." />;

  return (
    <>
      <PageHeader title="Settings" />
      {error && <ErrorState message={error} />}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Account">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Email</dt>
            <dd className="font-medium text-slate-800">{user.email}</dd>
            <dt className="text-slate-500">User ID</dt>
            <dd className="font-mono text-xs text-slate-700">{user.id}</dd>
            <dt className="text-slate-500">Status</dt>
            <dd className="font-medium text-slate-800">{user.status}</dd>
          </dl>
        </Card>
        <Card title="Business">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Selected business</dt>
            <dd className="font-mono text-xs text-slate-700">
              {tenantId ? tenantId.slice(0, 8) : "— none selected —"}
            </dd>
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            Manage messaging channel connections under{" "}
            <Link href="/integrations" className="font-medium text-slate-700 underline">
              Integrations
            </Link>
            .
          </p>
        </Card>
      </div>
    </>
  );
}
