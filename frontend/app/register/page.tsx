"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { login, register } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const result = await register(email, password);
    setSubmitting(false);
    if (result.ok) {
      // Registration succeeded: continue into the authenticated state by
      // signing in with the new credentials.
      const loginResult = await login(email, password);
      if (loginResult.ok) {
        router.push("/");
        return;
      }
      // Registered but auto-login failed: continue via the login page.
      router.push("/login");
      return;
    }
    if (result.status === 0) {
      setError("API is not reachable. Is the backend running?");
    } else if (result.status === 409) {
      setError("An account with this email already exists.");
    } else if (result.status === 422) {
      setError(
        "Please provide a valid email and a password of at least 8 characters.",
      );
    } else {
      setError(
        result.error?.message ?? `Registration failed (HTTP ${result.status}).`,
      );
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-6 px-6 py-20">
      <h1 className="text-2xl font-semibold tracking-tight">
        Create your Floww account
      </h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <span className="text-xs font-normal text-slate-500">
            At least 8 characters.
          </span>
        </label>

        {error && (
          <p role="alert" className="text-sm font-medium text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-slate-900 underline">
          Sign in
        </Link>
      </p>
    </main>
  );
}
