/**
 * Backend API client (Phase 1 foundation).
 *
 * The base URL comes from NEXT_PUBLIC_API_URL (see .env.example). Requests
 * are never cached and time out quickly so a backend outage surfaces as an
 * explicit "unavailable" state instead of an infinite spinner.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthStatus = {
  status: string;
  version: string;
  environment: string;
};

export async function getHealth(): Promise<HealthStatus | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as HealthStatus;
  } catch {
    return null;
  }
}
