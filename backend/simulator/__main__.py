"""Simulator CLI: run the deterministic scenario set against a live gateway.

Usage (from the backend directory):

    # 1. Create the test-only fixture connection (connected WhatsApp
    #    connection for the simulator's stable identifiers):
    python -m simulator setup --database-url postgresql+psycopg://.../floww

    # 2. Run the scenarios over HTTP against the running application:
    python -m simulator run --base-url http://127.0.0.1:8000 --secret <SIMULATOR_SIGNING_SECRET>

The secret must match the backend's SIMULATOR_SIGNING_SECRET (server-side
configuration; never commit real secrets). The simulator submits events over
HTTP only — it never writes into the event database.
"""

import argparse
import asyncio
import sys

from simulator.scenarios import ScenarioResult, run_all


def _print_results(results: list[ScenarioResult]) -> int:
    failures = 0
    print(f"{'SCENARIO':<28} {'EXPECTED':<50} {'HTTP':<6} RESULT")
    print("-" * 110)
    for result in results:
        if result.name == "concurrent_duplicates":
            statuses = (result.actual_body or {}).get("statuses", [])
            expected = result.expected
            ones = statuses.count(202)
            dups = statuses.count(200)
            ok = result.error is None and ones == 1 and dups == len(statuses) - 1
            print(f"{result.name:<28} {expected:<50} {statuses!s:<6} " + ("PASS" if ok else "FAIL"))
            if not ok:
                failures += 1
            continue
        ok = result.ok and _matches_expectation(result)
        print(
            f"{result.name:<28} {result.expected:<50} {result.actual_status!s:<6} "
            + ("PASS" if ok else "FAIL")
        )
        if result.error:
            print(f"{'':<28} error: {result.error}")
        if not ok:
            failures += 1
    print("-" * 110)
    print(f"{len(results) - failures}/{len(results)} scenarios passed")
    return 0 if failures == 0 else 1


def _matches_expectation(result: ScenarioResult) -> bool:
    """Deterministic expectation matching (status + body marker)."""
    expected = result.expected
    body = result.actual_body or {}
    if expected.startswith("202 accepted"):
        return body.get("status") == "accepted"
    if expected.startswith("200 duplicate"):
        return body.get("status") == "duplicate"
    if expected.startswith("200") and "forged tenant ignored" in expected:
        return body.get("status") == "accepted"
    if expected.startswith("401"):
        return (body.get("error") or {}).get("code") == "unauthorized"
    if expected.startswith("404"):
        return (body.get("error") or {}).get("code") == "unknown_connection"
    if expected.startswith("413"):
        return (body.get("error") or {}).get("code") == "payload_too_large"
    if expected.startswith("422"):
        return (body.get("error") or {}).get("code") == "validation_error"
    if expected.startswith("500"):
        return (body.get("error") or {}).get("code") == "internal_error"
    return False


class PersistenceFailureHook:
    """Forces a persistence failure for scenario 15 by temporarily renaming
    the events table (TEST-ONLY manipulation; fully recovered)."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://")

    def _set_table_available(self, available: bool) -> None:
        import psycopg

        action = (
            "ALTER TABLE IF EXISTS webhook_events_disabled RENAME TO webhook_events"
            if available
            else "ALTER TABLE IF EXISTS webhook_events RENAME TO webhook_events_disabled"
        )
        with psycopg.connect(self._database_url) as conn, conn.cursor() as cur:
            cur.execute(action)
        conn.close()

    def __call__(self, force: bool) -> None:
        self._set_table_available(available=not force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Floww webhook simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup", help="create the TEST-ONLY fixture connection (database write)"
    )
    setup_parser.add_argument("--database-url", required=True)

    run_parser = subparsers.add_parser("run", help="run the deterministic scenarios over HTTP")
    run_parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    run_parser.add_argument(
        "--secret",
        help="SIMULATOR_SIGNING_SECRET matching the backend configuration",
    )
    run_parser.add_argument("--database-url", help="enable the persistence-failure scenario")

    args = parser.parse_args()

    if args.command == "setup":
        from simulator.setup import ensure_fixture_connection

        connection_id = ensure_fixture_connection(args.database_url)
        print(f"Fixture connection ready: {connection_id}")
        return

    if not args.secret:
        print("error: --secret is required for the run command", file=sys.stderr)
        sys.exit(2)

    from simulator.client import SimulatorClient

    client = SimulatorClient(base_url=args.base_url, secret=args.secret)
    hook = PersistenceFailureHook(args.database_url) if args.database_url else None
    results = asyncio.run(run_all(client, persistence_failure_hook=hook))
    sys.exit(_print_results(results))


if __name__ == "__main__":
    main()
