# HANDOFF — PHASE 08

## Phase

Phase 08 — Order Management

## Status

COMPLETE (local implementation + verification; live run verified;
SIMULATOR_ONLY — no production Meta behavior)

## Phase objective

Turn a verified AI-generated OrderCandidate into a tenant-safe,
deterministic, seller-reviewable Order lifecycle. The seller remains
authoritative; the AI is not.

## Starting baseline (verified)

- HEAD = `469ad1a` = `phase-07-verified` (the verified Phase 07 state)
- Working tree clean; phase-01…07 history intact; all tags on origin

## Implemented

### A. Order data model (migration 0008)
- `orders`: uuid PK; tenant FK (CASCADE); customer FK (from the Phase 6
  customer model via the proven chain candidate → message → customer);
  **UNIQUE `extraction_candidate_id`** (one order per candidate —
  database-level idempotency); conversation FK (traceability); the
  authoritative lifecycle status with a DB CHECK constraint
  (new/needs_review/confirmed/processing/completed/cancelled/failed);
  timestamps. **NO price fields** (none exist in the extraction contract —
  nothing is invented).
- `order_items`: order FK (CASCADE); tenant FK; product/quantity/
  variant/size/color **verbatim from the Phase 7 extraction**; a DB CHECK
  constraint (quantity > 0).
- `order_events`: append-only audit trail — order creation, item edits and
  every status transition with the acting user; never logs secrets or
  message bodies.

### B. Deterministic conversion (`app/order_service.create_order_from_candidate`)
- EXTRACTED (valid) candidate → Order **NEW**
- NEEDS_REVIEW (uncertain) candidate → Order **NEEDS_REVIEW** (the review
  requirement is retained; never auto-confirmed)
- INVALID candidate → **no order** (nothing valid to review; recorded via
  the extraction status)
- No silent data loss: the candidate's items are persisted verbatim;
  INCOMPLETE items (missing quantity/product) are NOT persisted as order
  items (the OrderItem schema requires product + quantity and none is
  invented) — they remain review-visible in the candidate's extracted_data;
  the seller's explicit, audited correction completes them.
- Idempotency: the UNIQUE constraint + SAVEPOINT create-or-reuse — repeated
  or concurrent conversion returns the existing order (one order per
  candidate; verified: 4 concurrent conversions → 1 order).
- Transactional: candidate + order + items + the audit event commit
  together in the caller's transaction — a failure rolls everything back
  (no orphans, no falsely completed extraction state; verified).

### C. The enforced state machine (`app.order_service.VALID_TRANSITIONS`)
- NEW → NEEDS_REVIEW | CONFIRMED | CANCELLED
- NEEDS_REVIEW → CONFIRMED | CANCELLED
- CONFIRMED → PROCESSING | CANCELLED
- PROCESSING → COMPLETED | CANCELLED
- COMPLETED / CANCELLED / FAILED — terminal (COMPLETED → PROCESSING can
  never silently succeed → 400 `invalid_transition`)
- Every applied transition appends an audit event (from_status → to_status
  + the actor).

### D. Seller review API (`app/routers/orders.py`)
- `GET  /tenants/{id}/orders` — member: the tenant-scoped list
- `GET  /tenants/{id}/orders/{order_id}` — member: inspect (with items)
- `GET  /tenants/{id}/orders/{order_id}/events` — member: the audit history
- `PATCH /tenants/{id}/orders/{order_id}` — OWNER: correct items (audited;
  quantities/products change only through this action)
- `POST /tenants/{id}/orders/{order_id}/confirm` — OWNER: → CONFIRMED (the
  confirm action IS the human-review decision; no automatic confirmation
  exists anywhere)
- `POST .../process` — OWNER: → PROCESSING; `POST .../complete` — OWNER: →
  COMPLETED; `POST .../cancel` — OWNER: → CANCELLED
- Invalid transitions → 400 `invalid_transition`; validation failures →
  422; consistent error envelope; all authorization server-side (a
  forged/foreign order id → 404 with no existence inference; a non-member →
  403).

### E. Frontend (`/orders` + `lib/orders.ts`)
- The seller order workflow: the order list (tenant-scoped), item
  inspection, lifecycle-state labels (New/Needs Review/Confirmed/
  Processing/Completed/Cancelled/Failed), Confirm / Start processing / Mark
  completed / Cancel actions (role-appropriate), review-required hints,
  safe error states; the shell header now links to Orders (additive only).
- `lib/orders.test.ts`: 11 boundary tests vs the backend's exact contract.

### F. AI safety (AI_POLICY.md)
- Phase 8 never calls an AI provider, never silently corrects AI output,
  never invents quantities/prices/products/customer data, never
  auto-confirms uncertain orders (verified: an INVALID candidate creates no
  order; a NEEDS_REVIEW candidate's order retains the review requirement).

### G. Simulator boundary
- Untouched: the Phase 5/6/7 simulator behavior remains intact (all
  simulator/pipeline/extraction tests pass unchanged); no Meta production
  behavior was added.

## Test matrix results (mandatory coverage)

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | valid candidate → Order | PASS | `test_candidate_creates_order_with_items` (verbatim items) |
| 2 | order item persistence | PASS | same test (product/quantity/size/color) |
| 3 | NEEDS_REVIEW candidate | PASS | `test_needs_review_candidate_retains_review_requirement` |
| 4 | confirmed order | PASS | `test_valid_transitions_apply` |
| 5 | processing transition | PASS | same |
| 6 | completed transition | PASS | same |
| 7 | cancellation | PASS | `test_cancellation_from_non_terminal_states` + `test_needs_review_to_cancelled_supported` |
| 8 | invalid transition | PASS | `test_invalid_transitions_rejected` (COMPLETED → PROCESSING → 400; state unchanged) |
| 9 | duplicate candidate | PASS | `test_repeated_processing_creates_one_order` |
| 10 | concurrent duplicate candidate | PASS | `test_concurrent_conversion_creates_one_order` (4 concurrent → 1 order) |
| 11 | tenant isolation | PASS | `test_tenant_isolation_on_orders` (403/404; state untouched) |
| 12 | forged tenant ID | PASS | same (404, no existence inference) |
| 13 | forged order ID | PASS | same |
| 14 | unauthorized user | PASS | `test_order_api_requires_authentication` (401) |
| 15 | unauthorized tenant member | PASS | `test_seller_edit_requires_owner_role` (member reads, cannot edit) |
| 16 | transaction rollback | PASS | `test_order_creation_rollback_is_atomic` (no orphan order/items/candidate) |
| 17 | partial order-item failure | PASS | same (atomic rollback) |
| 18 | missing/invalid candidate data | PASS | `test_invalid_candidate_creates_no_order` |
| 19 | no fabricated values | PASS | no price fields anywhere; the corpus no-invention tests (Phase 7) |
| 20 | repeated processing | PASS | `test_repeated_processing_creates_one_order` |
| 21 | restart/retry behavior | PASS | Phase 6/7 restart + retry tests (intact) |
| 22 | API validation | PASS | `test_api_validation_rejects_invalid_items` |
| 23 | API error envelope | PASS | 400/401/403/404/422 envelope tests |
| 24 | frontend order workflow | PASS | `lib/orders.test.ts` (11 tests) |

## Test results

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-8) | `cd backend && python -m pytest -q` | **222 passed, exit 0** (129.12s) |
| Phase 8 orders tests | `python -m pytest tests/test_orders.py` | 15 passed |
| Repeated testing (mandatory ×3) | orders + pipeline + extraction | **57/57, 57/57, 57/57** — deterministic |
| Frontend tests | `cd frontend && npm test` | **41 passed (41), exit 0** |
| Frontend build | `npm run build` | ✓ 9/9 pages (incl. `/orders`), exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Formatting | `python -m ruff format --check .` | 58 files formatted |
| Type check (backend) | `python -m mypy app` | no issues in 31 source files |
| Migrations | clean DB → head | 0001-0008 applied, exit 0; rollback to 0007 + reapply verified |

## Live verification

Ran the real app + real PostgreSQL (fresh DB → migrations 0001-0008):

1. Simulator → HTTP → event → processor → candidate + Order (NEW) —
   verified (the pipeline tests + the Phase 7 E2E)
2. The seller review flow: confirm → PROCESSING → COMPLETED → CANCELLED
   (all audited in order_events) — verified by the API tests against the
   real app
3. The atomic rollback: a forced mid-transaction failure → no orphan
   order/items/candidate; the retry succeeds end-to-end — verified

## Security

- Tenant isolation: server-side, verified (403/404; no existence inference)
- Authorization: OWNER-only mutations; members read-only (verified)
- No client-controlled tenant/customer/order/audit assignment
- No secrets in the diff (scanned); no message bodies in logs
- The AI authority boundary: the seller/system validation determines the
  order; the AI candidate is never auto-confirmed (verified)
- Simulator-only functionality remains env-gated (unchanged)

## Known limitations

- No price/currency fields (the extraction contract has none; add with a
  concrete requirement only — e.g. a Phase 11 export or a billing need).
- The PATCH replaces ALL items (the seller's explicit correction); there is
  no per-item add/remove API.
- No order-list pagination (the list is bounded by the tenant's data).
- The audit trail is append-only via order_events; there is no separate
  admin/UI for the audit log beyond the order events endpoint.
- Conversation closure/ordering of the review queue are future scope.

## Deferred (Phase 09+)

- Phase 09 — Instagram integration; Phase 10 — controlled seller responses;
  Phase 11 — exports; Phase 12 — billing; Phase 13 — hardening;
  Phase 14 — deployment. Production Meta remains blocked/unknown.

## Git checkpoint

Commit: (phase-08 commit — see `git log` after checkpoint)
Tag: phase-08-complete

## Next phase

Phase 09 — Instagram Integration (NOT STARTED).

Do not start the next phase until this handoff is reviewed.
