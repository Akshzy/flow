import { getHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await getHealth();

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Floww</h1>
        <p className="mt-2 text-slate-600">
          Turn customer messages into structured, reviewable orders.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Backend API status
        </h2>
        {health ? (
          <div className="mt-3 space-y-1">
            <p className="flex items-center gap-2 text-lg font-medium text-emerald-600">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
              API reachable
            </p>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm text-slate-600">
              <dt>Version</dt>
              <dd className="font-mono">{health.version}</dd>
              <dt>Environment</dt>
              <dd className="font-mono">{health.environment}</dd>
            </dl>
          </div>
        ) : (
          <p className="mt-3 flex items-center gap-2 text-lg font-medium text-amber-600">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
            API unavailable — start the backend and reload this page
          </p>
        )}
      </section>
    </main>
  );
}
