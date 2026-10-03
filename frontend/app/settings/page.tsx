"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { fetchMe, type AuthUser } from "@/lib/auth";
import {
  disconnectConnection,
  fetchConnection,
  initiateConnection,
  type Connection,
} from "@/lib/connections";

export default function SettingsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [connections, setConnections] = useState<Record<string, Connection | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const me = await fetchMe();
    setUser(me);
    if (me === null) {
      setConnections({});
      setLoading(false);
      return;
    }
    // Tenant selection: the selected tenant scopes the connection request.
    // Authorization is enforced server-side via the caller's membership.
    const stored = window.localStorage.getItem("floww.auth.selected-tenant");
    if (!stored) {
      setConnections({});
      setLoading(false);
      return;
    }
    for (const platform of ["whatsapp", "instagram"] as const) {
      const result = await fetchConnection(stored, platform);
      if (result.ok) {
        setConnections((current) => ({ ...current, [platform]: result.data }));
      } else if (result.status === 401) {
        setConnections((current) => ({ ...current, [platform]: null }));
      } else if (result.status === 0) {
        setError("API is not reachable. Is the backend running?");
      } else {
        setError(
          result.error?.message ??
            `Could not load the connection status (HTTP ${result.status}).`,
        );
      }
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleConnect(platform: "whatsapp" | "instagram") {
    setActionError(null);
    const tenantId = window.localStorage.getItem("floww.auth.selected-tenant");
    if (!tenantId) {
      setActionError("Select a business first.");
      return;
    }
    setActing(true);
    const result = await initiateConnection(tenantId, platform);
    setActing(false);
    if (result.ok) {
      await load();
      return;
    }
    if (result.status === 401) {
      await fetchMe(); // clears a stale token
      router.push("/login");
      return;
    }
    setActionError(
      result.error?.message ??
        `Could not start the connection (HTTP ${result.status}).`,
    );
  }

  async function handleDisconnect(platform: "whatsapp" | "instagram") {
    setActionError(null);
    const tenantId = window.localStorage.getItem("floww.auth.selected-tenant");
    if (!tenantId) {
      setActionError("Select a business first.");
      return;
    }
    setActing(true);
    const result = await disconnectConnection(tenantId, platform);
    setActing(false);
    if (result.ok) {
      await load();
      return;
    }
    if (result.status === 401) {
      await fetchMe(); // clears a stale token
      router.push("/login");
      return;
    }
    setActionError(
      result.error?.message ??
        `Could not disconnect (HTTP ${result.status}).`,
    );
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
        / Settings
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      {error && (
        <p role="alert" className="text-sm font-medium text-red-600">
          {error}
        </p>
      )}

      {!user && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-medium">Sign in to continue</h2>
          <p className="mt-2 text-sm text-slate-600">
            Integrations require an authenticated account.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Sign in
          </Link>
        </section>
      )}

      {user && !error && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
            Integrations
          </h2>

          {(["whatsapp", "instagram"] as const).map((platform) => {
            const connection = connections[platform];
            return (
            <div key={platform} className="mt-3 rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {platform === "whatsapp" ? "WhatsApp" : "Instagram"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Status:{" "}
                    <span
                      className={
                        connection?.status === "connected"
                          ? "font-medium text-emerald-600"
                          : connection?.status === "initiated"
                            ? "font-medium text-amber-600"
                            : "font-medium text-slate-600"
                      }
                    >
                      {connection?.status === "connected"
                        ? "Connected"
                        : connection?.status === "initiated"
                          ? "Initiated — awaiting Meta authorization"
                          : "Not Connected"}
                    </span>
                  </p>
                  {connection?.status === "connected" &&
                    (connection.waba_id || connection.phone_number_id) && (
                      <p className="mt-1 text-xs text-slate-500">
                        {connection.waba_id && (
                          <>
                            WABA: <span className="font-mono">{connection.waba_id}</span>{" "}
                          </>
                        )}
                        {connection.phone_number_id && (
                          <>
                            Connection ID:{" "}
                            <span className="font-mono">{connection.phone_number_id}</span>
                          </>
                        )}
                      </p>
                    )}
                </div>
                <div className="flex shrink-0 gap-2">
                  {connection?.status !== "connected" && (
                    <button
                      onClick={() => handleConnect(platform)}
                      disabled={acting}
                      className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                    >
                      {acting ? "Working…" : "Connect"}
                    </button>
                  )}
                  {connection?.status === "connected" && (
                    <button
                      onClick={() => handleDisconnect(platform)}
                      disabled={acting}
                      className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {acting ? "Working…" : "Disconnect"}
                    </button>
                  )}
                </div>
              </div>
              {connection?.status === "initiated" && (
                <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  The connection was started, but Meta authorization is not
                  configured yet. Complete the Meta setup to finish connecting.
                </p>
              )}
            </div>
            );
          })}
        </section>
      )}
    </main>
  );
}
