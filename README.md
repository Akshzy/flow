# OrderFlow AI — Pi Agent Development Pack

This repository must be developed strictly one phase at a time.

## Repository structure

```text
backend/    FastAPI (Python) backend foundation
  app/        application (config, logging, errors, db, middleware, main)
  migrations/ Alembic migrations
  tests/      pytest suite (unit, API, integration, migration, failure)
frontend/   Next.js 15 + TypeScript + Tailwind 4 frontend foundation
scripts/    pg.mjs — embedded PostgreSQL lifecycle (dev/test)
.github/    CI workflow (backend + frontend checks)
```

## Getting started (Phase 1)

Prerequisites: Python 3.12+ (validated on 3.14), Node 22+.

### 1. Install dependencies

```bash
# backend (virtualenv recommended)
cd backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # Windows
# or: python -m venv .venv && .venv/bin/pip install -e ".[dev]"  # Linux/macOS

# frontend + embedded PostgreSQL binaries (from the repository root)
cd ..
npm install
cd frontend && npm install && cd ..
```

### 2. Configure

```bash
cp backend/.env.example backend/.env   # then edit values (never commit)
```

### 3. Start the database and the backend

```bash
npm run db:up                        # embedded PostgreSQL (port 55432)
cd backend && python scripts/dev.py  # uvicorn on http://127.0.0.1:8000
cd ..
```

- `GET /health` — liveness (process up; no dependency checks)
- `GET /ready` — readiness (verifies database connectivity; 503 when down)

### 4. Run migrations

```bash
cd backend && DATABASE_URL=... python -m alembic upgrade head
cd ..
# or set DATABASE_URL in backend/.env and run: python -m alembic upgrade head
```

### 5. Tests and checks

```bash
# backend
cd backend
python -m pytest            # tests (fresh embedded PostgreSQL per session)
python -m ruff check .      # lint
python -m ruff format --check .
python -m mypy app          # type check
cd ..

# frontend
cd frontend
npm run build
npm run typecheck
npm run lint
cd ..
```

### 6. Stop the database

```bash
npm run db:down
```

## Non-negotiable rule

Pi MUST NOT begin Phase N+1 until Phase N has:

1. Been implemented.
2. Passed required automated tests.
3. Passed required integration tests where applicable.
4. Passed build/type/lint/static checks where applicable.
5. Passed acceptance criteria.
6. Had failure and edge cases tested.
7. Been documented.
8. Had `PROJECT_STATUS.md` updated.
9. Had a `HANDOFF_NN.md` created.
10. Had git diff and secret checks completed.
11. Been committed.
12. Been tagged.
13. Been explicitly marked `COMPLETE`.

If any mandatory item is not verified, the phase is `BLOCKED`.

Pi MUST STOP after completing a phase. It must not continue automatically.

## Truth model

Every significant claim must be classified as:

- VERIFIED
- INFERRED
- UNKNOWN
- NOT IMPLEMENTED
- BLOCKED

Never replace UNKNOWN with an assumption.

A mock, stub, fixture, local simulation, or unit test MUST NOT be reported as a real external integration.

## Phase lifecycle

READ → INSPECT → PLAN → IMPLEMENT → TEST → VERIFY → FIX → RETEST → DOCUMENT → GIT CHECKPOINT → STOP

## Core files

- `AGENT_RULES.md`
- `PRODUCT.md`
- `REQUIREMENTS.md`
- `ARCHITECTURE.md`
- `DATA_MODEL.md`
- `INTEGRATIONS.md`
- `WEBHOOK_SPEC.md`
- `AI_POLICY.md`
- `TEST_STRATEGY.md`
- `PHASES.md`
- `PHASE_GATE.md`
- `DECISIONS.md`
- `RISKS.md`
- `PROJECT_STATUS.md`

## Phase documents

Each phase has a corresponding `PHASE_XX_*.md` specification and a `PROMPT_PHASE_XX.md` execution prompt.

The prompts are intentionally repetitive. This is deliberate: each phase must be independently executable and independently verifiable.
