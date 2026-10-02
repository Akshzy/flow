# HANDOFF — PHASE 07 (RECOVERY, STATE AUDIT, COMPLETION & VERIFICATION)

## Phase

Phase 07 — AI Order Extraction (recovery run after an interrupted previous
run)

## Status

VERIFIED (local implementation + verification complete; the real AI provider
integration remains a deterministic test double — SIMULATOR_ONLY for the AI
layer; production Meta remains blocked/unknown)

## Recovery summary

The previous Phase 07 run was interrupted. Repository evidence (STEP 0-5):

- **Two Phase 7 commits existed**: `4e7013c` ("Complete Phase 07: AI Order
  Extraction" — pushed, remotely tagged `phase-07-complete`, models.py
  CLEAN) and `7a46642` (a second commit — HEAD, tagged
  `phase-07-complete` LOCALLY ONLY, models.py CORRUPTED).
- **The interrupted run's edits were mangled by a tool-interface anomaly**:
  the word `ForeignKey(` became `Friendship=` (6 regions) and the pattern
  escapes were corrupted (`\b` became the backspace byte 0x08) — the
  committed 7a46642 code could not even import (IndentationError).
- **Uncommitted leftovers**: broken models.py fixes (6 malformed
  `ForeignKey=` kwarg regions), a weakened test (`assert output == {` →
  `return {` — an assertion converted into a vacuous return), buggy test
  additions (`OrderStatusCandidate` undefined, wrong pytest marker), and two
  `.backup` files.
- The interrupted run's HANDOFF_07.md claimed 189 tests passing and
  DISMISSED the MissingGreenlet reports as "not caused by our changes" —
  not investigated.

## What was already complete (recovered from 4e7013c, the clean baseline)

- `app/extraction.py`: ExtractionStatus, OrderItem/OrderCandidate schema,
  the deterministic AI test double, `validate_and_determine_status`
- `app/extraction_service.py`: `extract_and_save_candidate` (idempotent by
  message_id)
- `migrations/versions/0006_order_extraction_candidate.py`
- `app/models.py`: OrderExtractionCandidate model
- `app/pipeline/consumer.py`: the Phase 7 extraction integration
- `tests/test_extraction.py`: 7 unit tests

## WORK COMPLETED THIS RUN

1. **Restored** `backend/app/models.py` and `backend/tests/test_extraction.py`
   from the clean `4e7013c` (the broken working-tree remnants discarded —
   a targeted `git checkout 4e7013c -- <files>`, no destructive Git
   operations).
2. **BUG FIX — model/migration mismatch** (the real cause of the interrupted
   run's failures): the Message model declared `updated_at` (added in
   4e7013c) but migration 0005's table did not create it → every message
   insert failed with `UndefinedColumn: column messages.updated_at does not
   exist` → all 15 pipeline tests failed from a clean database. FIXED with
   **migration 0007** (`messages.updated_at` added; historical migrations
   not modified).
3. **BUG FIX — model annotations**: the interrupted run rewrote ALL model
   annotations to SQLAlchemy TYPES (`Mapped[Uuid]`, `Mapped[Text]`,
   `Mapped[Uuid | None]`, `Mapped[Text | None]`, `Mapped[JSONB]`) and
   dropped `timezone=True` from `PlatformConnection.disconnected_at` (a real
   model/migration mismatch — migration 0003 created TIMESTAMPTZ). FIXED:
   28× Uuid, 15+6× Text, 2× Uuid|None, 6× Text|None, 1× timezone — all
   restored to `Mapped[uuid.UUID]`/`Mapped[str]`/`DateTime(timezone=True)`,
   matching the authoritative migrations.
4. **BUG FIX — duplicate ExtractionStatus**: the interrupted run defined a
   second `ExtractionStatus(str, enum.Enum)` in models.py. DEDUPLICATED —
   models.py now imports it from `app.extraction` (single source of truth;
   no circular import); converted to `enum.StrEnum` (project convention).
5. **BUG FIX — deprecated pydantic API**: `@validator` →
   `@field_validator` (Pydantic V1 style deprecated since V2.0; the warning
   is gone).
6. **BUG FIX — extraction-retry gap**: the consumer ran the extraction only
   for events created in that call (`if created`) — a retry after an
   extraction failure marked the event PROCESSED WITHOUT ever creating the
   candidate. RESTRUCTURED: the extraction now runs for every event that
   reaches the message stage (including retried events); the service is
   idempotent (an existing candidate is returned without re-extraction).
   Verified: extraction failure → event FAILED + message durable (the
   Phase 6 boundary held) → bounded retry → candidate created + event
   PROCESSED.
7. **Extraction double extended** to the Phase 7 mandatory test corpus
   (deterministic phrase-pattern matching; SIMULATOR_ONLY for the AI layer):
   complete orders (qty/size/color), product-without-quantity (quantity key
   absent → NEEDS_REVIEW), multiple products (multi-item candidates),
   contradictory quantities (ambiguity → NEEDS_REVIEW), correction/ambiguity
   markers (NEEDS_REVIEW), and the no-invention fallback (unrelated chat,
   typos, Malayalam/Manglish, cancellations, prompt injection → INVALID;
   injected instructions have no effect beyond the literal text).
8. **Corpus tests added** (15 new tests) + **pipeline extraction integration
   tests** (3 new tests: candidate creation via the real gateway boundary,
   extraction idempotency, extraction-failure/retry).
9. **B011 fixes** in tests (`assert False` → `pytest.raises(ValidationError)`).
10. **Cleanup**: the `.backup` artifacts removed; ruff/mypy clean.

## BUGS FOUND (exact list)

1. `messages.updated_at` model column without a migration column
   (UndefinedColumn on every message insert — all 15 pipeline tests failed
   from a clean database)
2. Model annotations rewritten to SQLAlchemy types (Mapped[Uuid]/Mapped[Text]
   /Mapped[JSONB]) — 51 annotations
3. `PlatformConnection.disconnected_at` lost `timezone=True` (model/migration
   mismatch — the DB column is TIMESTAMPTZ)
4. Duplicate `ExtractionStatus(str, enum.Enum)` in models.py (+ the
   `(str, Enum)` base instead of StrEnum)
5. Deprecated pydantic `@validator` usage
6. The extraction-retry gap (a retry after an extraction loss produced
   PROCESSED events with no candidate)
7. Tool-interface corruption in 7a46642 (ForeignKey→Friendship, backspace
   bytes in the regex, broken indentation) + a weakened test + broken
   working-tree remnants

## BUGS FIXED

All of the above (1-7): migration 0007; 51 annotation restorations; the
timezone restoration; the ExtractionStatus dedup + StrEnum; @field_validator;
the consumer extraction restructure; the file restorations + corpus
extension + test fixes.

## MISSINGGREENLET

**RESOLVED (did not reproduce)** — Evidence: the Phase 6 fix (re-fetch the
event fresh after a rollback; a rollback expires ORM attributes and reading
them triggers sync IO → MissingGreenlet) is present in the recovered code;
the full suite passes 189→207→(final) with the pipeline FAILURE scenarios
included; the pipeline+extraction tests were run 3 consecutive times (24/24,
42/42, 42/42) with zero intermittent failures. The interrupted run's claim
("occurs in the original code as well") did not reproduce.

## Tests

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-7) | `cd backend && python -m pytest -q` | **207 passed, exit 0** (191.29s) |
| Phase 7 extraction tests | `python -m pytest tests/test_extraction.py` | 22 passed (7 existing + 15 corpus) |
| Phase 6 pipeline tests | `python -m pytest tests/test_pipeline.py` | 20 passed (17 + 3 extraction integration) |
| Stability repeat (×2) | pipeline + extraction | 42/42, 42/42 — deterministic |
| Frontend tests | `cd frontend && npm test` | 30 passed (30), exit 0 |
| Frontend build | `npm run build` | ✓ 8/8 pages, exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Formatting | `python -m ruff format --check .` | 55 files formatted |
| Type check (backend) | `python -m mypy app` | no issues in 29 source files |
| Migrations | clean DB → head | 0001-0007 applied, exit 0 |

## Security

- No secrets/API keys/Meta tokens/credentials in the diff (scanned)
- No customer message bodies logged (the pipeline logs IDs/statuses only)
- No client-controlled tenant assignment (the pipeline uses the event's
  server-controlled tenant; verified by tests)
- No fabricated Meta production behavior (the AI layer is SIMULATOR_ONLY;
  the real AI provider integration is a later phase)
- No unsafe debug endpoints; the simulator remains env-gated
- AI safety (AI_POLICY.md): the double never invents data (verified by the
  corpus tests); extraction output is a CANDIDATE (never authoritative);
  uncertain/ambiguous → NEEDS_REVIEW; deterministic validation

## Known limitations

- The AI layer uses a deterministic phrase-pattern test double
  (SIMULATOR_ONLY vocabulary: shirt/pizza/shoes/book/cake/bag/charger/mug +
  the corpus phrases). The real AI provider integration is a LATER phase and
  must never be faked; the double must be replaced by a structured-output
  model adapter at that point (with the same deterministic validation).
- Typos of products outside the stand-in vocabulary → INVALID (deterministic;
  the candidate is recorded, not discarded) — a real AI provider would
  handle open vocabulary.
- Manglish containing a recognized product but an unrecognizable quantity →
  NEEDS_REVIEW (quantity missing; no invention).
- The extraction has no price/currency fields (no concrete requirement in
  the simulator contract; add with a concrete requirement only).
- Multiple orders in one conversation = multiple messages → multiple
  candidates (one candidate per message, by design).

## Deferred (Phase 08+)

- Phase 08 — Order Management: the seller review UI/API over
  `order_extraction_candidates` (NEEDS_REVIEW/EXTRACTED → confirmed orders),
  the order state machine, the audit trail. NO order_service/orders table
  exists yet (the interrupted run's broken test referenced a nonexistent
  `app.order_service` — never implemented).
- Production Meta integration (blocked/unknown since Phase 5); Embedded
  Signup; Business Verification.
- Phase 09+ (Instagram), Phase 12 (billing), Phase 13 (hardening),
  Phase 14 (deployment).

## Git checkpoint

- The remote `phase-07-complete` tag (4e7013c) is PRESERVED (not moved).
- The LOCAL `phase-07-complete` tag pointed at the corrupted 7a46642 — it is
  PRESERVED as a historical artifact (never force-moved, never pushed).
- Per the recovery instructions, the verified final state is tagged with a
  new immutable verification tag: `phase-07-verified` (created after the
  final commit).

## Next phase

Phase 08 — Order Management (NOT STARTED).

Do not start the next phase until this handoff is reviewed.
