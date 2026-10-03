"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge, Card, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { fetchMe, getSelectedTenantId, type AuthUser } from "@/lib/auth";
import {
  disconnectConnection,
  fetchConnection,
  initiateConnection,
  type Connection,
} from "@/lib/connections";

/** Integrations (Phase 10): WhatsApp and Instagram connection management —
 * the existing Phase 9 APIs; honest states; no fake Meta configuration. */
export default function IntegrationsPage() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connections, setConnections] = useState<Record<string, Connection | null>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

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
      setConnections({});
      setLoading(false);
      return;
    }
    for (const platform of ["whatsapp", "instagram"] as const) {
      const result = await fetchConnection(tenantId, platform);
      if (result.status === 0) {
        setError("API is not reachable. Is the backend running?");
      } else {
        setConnections((current) => ({
          ...current,
          [platform]: result.ok ? result.data : null,
        }));
      }
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleConnect(platform: "whatsapp" | "instagram") {
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    setActionError(null);
    const result = await initiateConnection(tenantId, platform);
    setActing(false);
    if (result.ok) {
      await load();
    } else {
      setActionError(
        result.error?.message ?? `Could not start the connection (HTTP ${result.status}).`,
      );
    }
  }

  async function handleDisconnect(platform: "whatsapp" | "instagram") {
    const tenantId = getSelectedTenantId();
    if (!tenantId) return;
    setActing(true);
    setActionError(null);
    const result = await disconnectConnection(tenantId, platform);
    setActing(false);
    if (result.ok) {
      await load();
    } else {
      setActionError(result.error?.message ?? "Could not disconnect.");
    }
  }

  if (loading) return <LoadingState />;
  if (!user) return <ErrorState message="Please sign in to manage integrations." />;

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connect your messaging channels. Authorization happens through Meta; Floww never asks for your passwords."
      />
      {error && <ErrorState message={error} />}
      {!error && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {(["whatsapp", "instagram"] as const).map((platform) => {
            const connection = connections[platform];
            return (
              <Card key={platform}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">
                      {platform === "whatsapp" ? "WhatsApp" : "Instagram"}
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      {platform === "whatsapp"
                        ? "WhatsApp Business Platform (Cloud API)"
                        : "Messenger API support for Instagram (requires an Instagram Business or Creator account linked to a Facebook Page)"}
                    </p>
                  </div>
                  <Badge
                    tone={
                      connection?.status === "connected"
                        ? "success"
                        : connection?.status === "initiated"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {connection?.status === "connected"
                      ? "Connected"
                      : connection?.status === "initiated"
                        ? "Configuration Required"
                        : "Disconnected"}
                  </Badge>
                </div>

                {connection?.status === "connected" && (
                  <p className="mt-3 text-xs text-slate-500">
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

                {connection?.status === "initiated" && (
                  <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    Meta authorization is not configured yet. Complete the Meta
                    setup to finish connecting.
                  </p>
                )}

                {actionError && (
                  <p role="alert" className="mt-3 text-sm font-medium text-red-600">
                    {actionError}
                  </p>
                )}

                <div className="mt-4 flex gap-2">
                  {connection?.status !== "connected" && (
                    <button
                      onClick={() => handleConnect(platform)}
                      disabled={acting}
                      className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                    >
                      {acting ? "Working…" : "Connect"}
                    </button>
                  )}
                  {connection?.status === "connected" && (
                    <button
                      onClick={() => handleDisconnect(platform)}
                      disabled={acting}
                      className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <p className="mt-6 text-xs text-slate-500">
        Looking for account settings?{" "}
        <Link href="/settings" className="font-medium text-slate-700 underline">
          Settings
        </Link>
      </p>
    </>
  );
}
