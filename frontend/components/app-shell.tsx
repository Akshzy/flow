"use client";

import Link from "next/link";
import { fetchMe, getToken, logout, type AuthUser } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "grid" },
  { href: "/conversations", label: "Conversations", icon: "chat" },
  { href: "/orders", label: "Orders", icon: "box" },
  { href: "/products", label: "Products", icon: "tag" },
  { href: "/customers", label: "Customers", icon: "users" },
  { href: "/integrations", label: "Integrations", icon: "plug" },
  { href: "/settings", label: "Settings", icon: "gear" },
] as const;

function NavIcon({ icon }: { icon: string }) {
  const common = "h-4 w-4 shrink-0";
  switch (icon) {
    case "grid":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M3 3h7v7H3V3zm7 7h7v7h-7v-7zM3 10h7v7H3v-7zM10 3h7v7h-7V3z" />
        </svg>
      );
    case "chat":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M2 4a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H8l-4 4v-4H4a2 2 0 01-2-2V4z" />
        </svg>
      );
    case "box":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M10 2l7 3.5v9L10 19l-7-4.5v-9L10 2zm0 2.2L5.4 6.5 10 8.8l4.6-2.3L10 4.2zM5 8.2v6l4 2.6v-6L5 8.2zm10 0l-4 2.6v6l4-2.6v-6z" />
        </svg>
      );
    case "tag":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M11 2l7 7-8.5 8.5a2 2 0 01-2.8 0L2 13V4a2 2 0 012-2h7zm-4.5 4a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" />
        </svg>
      );
    case "users":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M7 9a3 3 0 100-6 3 3 0 000 6zm7 1a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM7 11c-3 0-5 1.5-5 3.5V16h10v-1.5C12 12.5 10 11 7 11zm7 1c-.7 0-1.3.1-1.9.3 1.2.9 1.9 2.1 1.9 3.2V16h4v-1.2c0-1.7-2-2.8-4-2.8z" />
        </svg>
      );
    case "plug":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M7 2v4H6a3 3 0 00-3 3v2h14V9a3 3 0 00-3-3h-1V2h-2v4H9V2H7zm-4 11v2a3 3 0 003 3h8a3 3 0 003-3v-2H3z" />
        </svg>
      );
    default:
      return (
        <svg className={common} viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M10 6a4 4 0 100 8 4 4 0 000-8zm8.4 4.9l-1.8-.9a6.7 6.7 0 000-2l1.8-.9-1.6-2.8-1.9.7a6.8 6.8 0 00-1.7-1.1L13 1h-3.2l-.4 2a6.8 6.8 0 00-1.7 1.1l-1.9-.7-1.6 2.8 1.8.9a6.7 6.7 0 000 2l-1.8.9 1.6 2.8 1.9-.7c.5.5 1.1.8 1.7 1.1l.4 2H13l.4-2c.6-.3 1.2-.6 1.7-1.1l1.9.7 1.6-2.8z" />
        </svg>
      );
  }
}

/**
 * The Floww application shell (Phase 10): ONE consistent layout — a dark
 * navy sidebar, a topbar, and the main workspace. Desktop-first; the
 * sidebar collapses to a top-bar menu on mobile.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let active = true;
    fetchMe().then((me) => {
      if (!active) return;
      setUser(me);
      if (me === null) {
        router.replace("/login");
      }
    });
    return () => {
      active = false;
    };
  }, [router]);

  async function handleSignOut() {
    await logout();
    router.replace("/login");
  }

  const nav = (
    <nav aria-label="Main navigation" className="flex flex-col gap-1 px-3">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={() => setMenuOpen(false)}
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
        >
          <NavIcon icon={item.icon} />
          {item.label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between bg-slate-900 py-6 md:flex">
        <div>
          <div className="mb-8 px-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white">
                F
              </span>
              <span className="text-lg font-semibold tracking-tight text-white">
                Floww
              </span>
            </Link>
          </div>
          {nav}
        </div>
        <div className="px-6">
          {user && (
            <div className="flex items-center justify-between gap-2 rounded-lg bg-white/5 px-3 py-2">
              <span className="truncate text-xs font-medium text-slate-300">
                {user.email}
              </span>
              <button
                onClick={handleSignOut}
                className="shrink-0 text-xs font-medium text-indigo-300 underline-offset-2 hover:underline"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar (mobile navigation + desktop breadcrumb bar) */}
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-label="Toggle navigation"
              className="rounded-lg p-1.5 text-slate-700 hover:bg-slate-100 md:hidden"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path d="M2 4.5h16v2H2v-2zm0 5h16v2H2v-2zm0 5h16v2H2v-2z" />
              </svg>
            </button>
            <Link href="/" className="flex items-center gap-2 md:hidden">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white">
                F
              </span>
              <span className="font-semibold tracking-tight text-slate-900">
                Floww
              </span>
            </Link>
          </div>
          {user && (
            <span className="truncate text-xs font-medium text-slate-500">
              {user.email}
            </span>
          )}
        </header>

        {/* Mobile navigation drawer */}
        {menuOpen && (
          <div className="border-b border-slate-800 bg-slate-900 py-3 md:hidden">{nav}</div>
        )}

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>

        <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-500 md:px-8">
          <a href="/privacy" className="font-medium text-slate-600 underline hover:text-slate-900">
            Privacy Policy
          </a>
        </footer>
      </div>
    </div>
  );
}
