"""Development server launcher.

On Windows, psycopg's async mode requires a SelectorEventLoop while uvicorn's
default loop factory uses the ProactorEventLoop. This launcher installs the
selector event loop policy on Windows (a no-op on other platforms) and starts
uvicorn without an explicit loop factory, so the policy applies.

Usage (from the backend directory):

    python scripts/dev.py [--host 127.0.0.1] [--port 8000] [--reload]
"""

import argparse
import asyncio
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Floww development server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    # Make the backend package importable (running this script puts the
    # scripts directory at sys.path[0], not the backend root).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    if sys.platform == "win32":
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        loop="none",
    )


if __name__ == "__main__":
    main()
