# HANDOFF — PHASE 10

## Phase

Phase 10 — Controlled Seller Responses + Application Experience

## Status

COMPLETE (local implementation + verification, including live visual
verification; the production Meta send is UNKNOWN_META and blocked — never a
fake success)

## Starting baseline (verified)

- HEAD = `f81de82` = `phase-09-complete` (origin/main synced, tree clean)

## Controlled response architecture

```text
Confirmed order (Phase 8)
        ↓
Deterministic intent classification (app.response_service.classify_intent —
from existing state: a conversation with a CONFIRMED order →
order_confirmation; else unsupported; NO LLM, no fuzzy matching)
        ↓
Response draft (origin: ai_suggested — a deterministic template built ONLY
from the confirmed order's actual items; missing information never invented;
unsupported intents → 422 no_response_available)
        ↓
Seller review (the UI distinguishes AI SUGGESTED from SELLER WRITTEN; the
seller may edit the draft — the origin becomes seller_written)
        ↓
EXPLICIT approval (the ONLY path to send; no automatic AI → SEND transition
exists anywhere)
        ↓
Send (via the platform adapter boundary; the tenant's opt-in control
`tenants.responses_enabled` must be enabled; the production Meta send is
UNKNOWN_META and refused — the failure is recorded (last_send_error,
send_attempts, bounded by MAX_SEND_ATTEMPTS=5) and the response stays
APPROVED/retryable; NEVER a fake success)
        ↓
SENT (audited)
```

- Lifecycle states: DRAFT → APPROVED → SENT; FAILED (a send failure —
  bounded retry via send). DB CHECK constraints enforce the intent/origin/
  status values.
- The audit trail: `response_events` (append-only) — created/approved/
  send_failed/sent with the actor; the response CONTENT is never logged
  (verified by a log-capture test).
- Idempotency: concurrent approvals (3 concurrent → exactly one 200; the
  response is approved once — verified); the send is bounded; double-sends
  of a SENT response are rejected (SENT is terminal).

## Frontend application shell

- `components/app-shell.tsx` — ONE consistent layout: a dark navy sidebar
  (Dashboard/Conversations/Orders/Products/Customers/Integrations/Settings +
  the account + sign out), a topbar (mobile navigation toggle + the account
  email), the main workspace, and the privacy footer. The `(app)` route
  group wraps all authenticated pages; unauthenticated users are redirected
  to /login.
- `components/ui.tsx` — the shared primitives: PageHeader, Card, Badge
  (neutral/success/warning/danger/info), EmptyState, LoadingState,
  ErrorState — reused across ALL pages (no duplicated visuals).
- The Floww visual language: the indigo→violet gradient brand mark, the
  indigo accent for the primary actions, rounded cards, restrained shadows,
  clean typography.

## Implemented pages (all verified live: HTTP 200 + content)

1. **Dashboard** (`/`): REAL values derived from the backend APIs (New/needs
   review, Confirmed, Completed, Conversations counts — never manufactured
   numbers) + Recent conversations + an empty state when there is no data.
2. **Conversations** (`/conversations`): the list (customer/platform/latest
   message/timestamp) + the thread (messages/timestamps) + the Context panel
   (the intent badge + the order link) + **the response review UI** (the
   centerpiece): Generate AI suggested response → the AI SUGGESTED badge →
   Edit (the seller's edit → SELLER WRITTEN) → Approve → Approve & Send →
   Sent/Send failed (retryable). No response can be generated without a
   confirmed order (the state cannot back it).
3. **Orders** (`/orders`): the operational list (order/customer/items/
   status + the lifecycle actions).
4. **Order detail** (`/orders/[orderId]`): the header (the id/status/
   customer), the items, **the delivery address as a FIRST-CLASS section
   with an explicit "Delivery address missing" state** (the backend has no
   address data — it is never invented/guessed), the real lifecycle
   timeline (from order_events), and the seller actions.
5. **Customers** (`/customers`): the customer, the platform identities, the
   order count, the last order — only data the backend supports.
6. **Products** (`/products`): an HONEST "not available yet" state — NO
   product/catalog API exists and no fake CRUD was built (the catalog
   intelligence is a dedicated future phase).
7. **Integrations** (`/integrations`): WhatsApp + Instagram connection
   management (the existing Phase 9 APIs) with honest states (Connected /
   Configuration Required / Disconnected) + the platform requirements
   (from the verified Meta docs); no fake Meta configuration controls.
8. **Settings** (`/settings`): only ACTUAL backend functionality (the
   account from /auth/me + the selected business).
9. **Login/Register**: polished with the Floww visual identity (the real
   authentication API; no new providers).
10. **Privacy** (`/privacy`): unchanged (Phase 3).

## Delivery address handling

FIRST-CLASS in the order detail: an explicit "Delivery address missing"
state (the backend has no address data — the extraction contract has no
address fields and the customers table has no addresses). Floww does NOT
guess or invent addresses; the seller should request it from the customer.
When the backend gains address data, this section renders it prominently.

## Tests

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-10) | `cd backend && python -m pytest -q` | **242 passed, exit 0** (254.14s) |
| Phase 10 response tests | `python -m pytest tests/test_responses.py` | 8 passed |
| Frontend tests | `cd frontend && npm test` | **41 passed (41), exit 0** |
| Frontend build | `npm run build` | ✓ 9/9 pages (the (app) group), exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Formatting | `python -m ruff format --check .` | 61 files formatted |
| Type check (backend) | `python -m mypy app` | no issues in 33 source files |
| Migrations | clean DB → head | 0001-0010 applied, exit 0 |
| Regression | Phase 09 + all prior | all pass unchanged |

## Verification

- Live run (real app + real PostgreSQL + the real HTTP server):
  simulator → HTTP (202) → processor (1 processed) → the order confirmed
  (200) → **the response draft created (200, ai_suggested, "Hi! Your order
  has been received: 2x shirt. We will update you when it ships." — from the
  order's actual items)** → approved (200) → send refused (503
  `platform_send_unavailable` — NEVER a fake success).
- Visual verification: all 10 pages served HTTP 200; the Dashboard/
  Products/Login content verified; the (app) shell renders on every page;
  the mobile navigation (the collapsible drawer) implemented; the
  accessibility: labels (aria-label/sr-only/role=status/role=alert),
  button semantics, focus states via the browser defaults + the hover
  states.

## UNKNOWN_META boundaries

- The Meta SEND API (send a message): UNKNOWN_META — the production send is
  refused (503 `platform_send_unavailable`); the response stays
  APPROVED/retryable; a deterministic test double is used for the
  send-success tests only (never presented as production proof).
- The production webhook verification/signatures (blocked since Phase 5).
- The Instagram/WhatsApp exact scopes/tokens (blocked since Phase 4/9).

## Known limitations

- The production send is not implemented (UNKNOWN_META) — responses cannot
  actually reach customers until the Meta send API is verified and
  implemented behind the adapter.
- The Products page is an honest roadmap state (no catalog API).
- No conversations pagination/unread state (not supported by the backend).
- The dashboard values are derived client-side from the list APIs (bounded
  to 100 conversations/200 customers) — a dedicated stats API is future
  scope.
- The response send's `to` field is currently the conversation's customer
  id (the platform addressing semantics are UNKNOWN_META).

## Deferred (Phase 11+)

- Phase 11 — Excel/CSV export; Phase 12 — billing; Phase 13 — hardening;
  Phase 14 — deployment. The seller catalog/knowledge (RAG) and the
  autonomous chatbot behavior are intentionally NOT built (future phases).

## Git checkpoint

Commit: (phase-10 commit — see `git log` after the checkpoint)
Tag: phase-10-complete

## Next phase

Phase 11 — Excel/CSV Export (NOT STARTED).

Do not start the next phase until this handoff is reviewed.
