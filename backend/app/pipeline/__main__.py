"""Pipeline CLI: process pending events deterministically.

Usage (from the backend directory):

    python -m app.pipeline process [--limit N] [--retry-failed]

The database URL comes from the environment or backend/.env (via app
config). Each event is processed in its own transaction; failures are
recorded (FAILED + attempts + error) and the event remains inspectable.
Retry behavior is bounded by MAX_PROCESSING_ATTEMPTS — no loops.
"""

import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Floww message pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser(
        "process", help="process pending events (bounded, deterministic)"
    )
    process_parser.add_argument("--limit", type=int, default=100)
    process_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="also retry FAILED events (bounded by MAX_PROCESSING_ATTEMPTS)",
    )

    args = parser.parse_args()

    # On Windows, psycopg's async mode requires a SelectorEventLoop (same
    # policy as tests/dev.py and the simulator).
    if sys.platform == "win32":
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from app.config import load_settings
    from app.db import create_engine, create_session_factory
    from app.pipeline.consumer import process_pending_events

    try:
        settings = load_settings()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    async def _run() -> int:
        engine = create_engine(settings.database_url)
        try:
            factory = create_session_factory(engine)
            async with factory() as db:
                result = await process_pending_events(
                    db, limit=args.limit, retry_failed=args.retry_failed
                )
            print(
                f"processed: {result.processed}, already_processed: "
                f"{result.already_processed}, failed: {result.failed}, "
                f"skipped: {result.skipped}"
            )
            for error in result.errors:
                print(f"  failed: {error}")
            return 0 if result.failed == 0 else 1
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
