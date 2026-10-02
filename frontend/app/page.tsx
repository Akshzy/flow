"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import {
  createTenant,
  fetchMe,
  fetchTenants,
  getSelectedTenantId,
  logout,
  setSelectedTenantId as persistSelectedTenantId,
  type AuthUser,
  type Tenant,
} from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [tenantsError, setTenantsError] = useState<string | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [newTenantName, setNewTenantName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setTenantsError(null);
    const me = await fetchMe();
    setUser(me);
    if (me === null) {
      // Unauthenticated: protected UI stays hidden; token was cleared if stale.
      setTenants(null);
      setApiReachable(await getHealth().then((h) => h !== null));
      setLoading(false);
      return;
    }
    const tenantList = await fetchTenants();
    if (tenantList === null) {
      setTenantsError("Could not load your tenants. Is the backend running?");
    } else {
      setTenants(tenantList);
      // Restore the persisted selection if it is still valid; otherwise
      // select the first tenant.
      const stored = getSelectedTenantId();
      const valid = stored !== null && tenantList.some((t) => t.id === stored);
      setSelectedTenantId(valid ? stored : (tenantList[0]?.id ?? null));
    }
    setApiReachable(true);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreateTenant(event: React.FormEvent) {
    event.preventDefault();
    const name = newTenantName.trim();
    if (!name) return;
    setCreateError(null);
    setCreating(true);
    const result = await createTenant(name);
    setCreating(false);
    if (result.ok) {
      setNewTenantName("");
      // Select the new tenant: update local state and persist the selection.
      setSelectedTenantId(result.data.id);
      persistSelectedTenantId(result.data.id);
      await load();
      return;
    }
    if (result.status === 0) {
      setCreateError("API is not reachable. Is the backend running?");
    } else if (result.status === 401) {
      // Session expired/invalid: reset the frontend auth state.
      await logout();
      router.push("/login");
    } else {
      setCreateError(
        result.error?.message ?? `Could not create the tenant (HTTP ${result.status}).`,
      );
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setTenants(null);
    setSelectedTenantId(null);
    router.push("/login");
  }

  const selectedTenant = tenants?.find((t) => t.id === selectedTenantId) ?? null;

  if (loading) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-20">
        <p className="text-slate-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Floww</h1>
          <p className="mt-1 text-sm text-slate-500">
            API:{" "}
            {apiReachable ? (
              <span className="font-medium text-emerald-600">reachable</span>
            ) : (
              <span className="font-medium text-amber-600">unreachable</span>
            )}
          </p>
        </div>
        {user && (
          <div className="flex flex-col items-end gap-2">
            <span className="text-sm text-slate-600">{user.email}</span>
            <div className="flex gap-2">
              <Link
                href="/orders"
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
              >
                Orders
              </Link>
              <Link
                href="/settings"
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
              >
                Settings
              </Link>
              <button
                onClick={handleLogout}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
              >
                Sign out
              </button>
            </div>
          </div>
        )}
      </header>

      {!user && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium">Sign in to continue</h2>
          <p className="mt-2 text-sm text-slate-600">
            This area requires an authenticated account.
          </p>
          <div className="mt-4 flex gap-3">
            <Link
              href="/login"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Register
            </Link>
          </div>
        </section>
      )}

      {user && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
            Your businesses
          </h2>

          {tenantsError && (
            <p role="alert" className="mt-3 text-sm font-medium text-red-600">
              {tenantsError}
            </p>
          )}

          {!tenantsError && tenants && tenants.length === 0 && (
            <p className="mt-3 text-sm text-slate-600">
              You do not have any businesses yet. Create one below to get
              started.
            </p>
          )}

          {!tenantsError && tenants && tenants.length > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {tenants.map((tenant) => (
                <li key={tenant.id}>
                  <button
                    onClick={() => {
                      setSelectedTenantId(tenant.id);
                      persistSelectedTenantId(tenant.id);
                    }}
                    className={`w-full rounded-lg border px-4 py-3 text-left text-sm ${
                      tenant.id === selectedTenantId
                        ? "border-slate-900 bg-slate-50 font-medium"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span>{tenant.name}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs uppercase tracking-wide text-slate-600">
                        {tenant.role ?? "member"}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {selectedTenant && (
            <p className="mt-3 text-xs text-slate-500">
              Selected: <span className="font-medium">{selectedTenant.name}</span>{" "}
              ({selectedTenant.id})
            </p>
          )}

          <form
            onSubmit={handleCreateTenant}
            className="mt-4 flex flex-col gap-2 border-t border-slate-100 pt-4"
          >
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              Create a new business
              <input
                type="text"
                required
                maxLength={200}
                value={newTenantName}
                onChange={(event) => setNewTenantName(event.target.value)}
                placeholder="Business name"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </label>
            {createError && (
              <p role="alert" className="text-sm font-medium text-red-600">
                {createError}
              </p>
            )}
            <button
              type="submit"
              disabled={creating || !newTenantName.trim()}
              className="self-start rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create business"}
            </button>
          </form>
        </section>
      )}
    </main>
  );
}
