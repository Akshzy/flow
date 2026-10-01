# HANDOFF — PHASE 06

## Phase

Phase 06 — Deterministic Message Pipeline (autonomous run)

## 1. Phase 06 objective

Deterministically transform Phase 05's durable PENDING_PROCESSING events
into Floww's internal messaging model (customer → conversation → message)
and mark the source events processed — no AI, no LLM, no fuzzy matching.

## 2. Actual implementation

- **Normalization** (`app/pipeline/normalization.py`): a persisted event's
  raw payload is re-validated (deterministic) into `NormalizedMessage`
  (platform, tenant, connection, external event id, external user id,
  message type, body, external timestamp). Message type: "text" when a text
  body exists; otherwise the event type ("messages" without a body →
  body=None). Unsupported types raise a controlled error — recorded as
  FAILED by the consumer, never silently discarded. The raw source event
  stays preserved in the Phase 05 record; the full external payload is not
  copied into downstream tables.
- **Consumer** (`app/pipeline/consumer.py`): `process_event` (one event, one
  transaction) and `process_pending_events` (bounded batch,
  `ProcessingResult`).
- **CLI** (`app/pipeline/__main__.py`): `python -m app.pipeline process
  [--limit N] [--retry-failed]` — the documented processing command.

## 3. Event normalization contract

`webhook_events.raw_payload` (JSONB, validated at ingestion) →
`NormalizedMessage`. Identity: the simulator contract's `from` field (the
platform sender identifier) — explicit platform identifiers ONLY. The raw
event is preserved in Phase 05; the normalized representation contains only
what Phase 6 needs.

## 4. Customer identity strategy

- `customers`: internal Floww ID (uuid) + tenant (tenant-owned). No phone
  column, no speculative fields.
- `customer_platform_identities`: customer FK + tenant + platform +
  `external_user_id`; UNIQUE (tenant, platform, external_user_id).
- Resolution: fast-path lookup by identity → create-or-reuse via SAVEPOINT
  (a concurrent racing insert violates the unique constraint, rolls back
  only the savepoint, and the existing identity wins) — one customer per
  identity, database-enforced (verified: concurrent creation → 1 customer).
- The phone number is NOT the immutable primary key (BSUID/usernames will
  replace it for username adopters — verified Meta account-model evolution).

## 5. Conversation strategy

One OPEN conversation per (tenant, customer, connection) — partial unique
index `uq_conversations_open`; deterministic resolution (never text- or
similarity-based); concurrent resolution cannot duplicate (verified).

## 6. Message identity/idempotency

UNIQUE `source_event_id` (FK → webhook_events): one message per source
event. The same event processed 1x/2x/5x/concurrently → one logical message
(verified). Message idempotency is database-level, not application checks.

## 7. Processing lifecycle

```text
PENDING_PROCESSING
   ↓ (consumer: normalize → customer → conversation → message, one
        transaction; success marks)
PROCESSED (processed_at set; downstream records durable)
   ↓ (a failed attempt records)
FAILED (attempts+1, last_processing_error; inspectable)
```

## 8. Transaction boundaries

ONE transaction per event (the caller's session): normalize → customer →
conversation → message → event PROCESSED. All-or-rollback:
- the event is marked PROCESSED only when the downstream records are durable
  in the same transaction (no event=processed with message=missing);
- message-level idempotency (UNIQUE source_event_id) prevents
  message=duplicated after a retry.

## 9. Retry behavior

- Bounded: MAX_PROCESSING_ATTEMPTS = 5 (processing_attempts counts failed
  attempts; events at/over the cap are skipped — verified).
- A failure rolls the transaction back, re-fetches the event fresh (a
  rollback expires ORM attributes — accessing them would trigger sync IO),
  records the failure in a separate small transaction, and leaves the event
  inspectable + retryable.
- Retry is EXPLICIT (`--retry-failed`) — no automatic loops.

## 10. Simulator behavior

The Phase 05 simulator is the authoritative development input; the Phase 6
tests follow simulator → HTTP webhook → persisted event → processor →
customer/conversation/message. The simulator was extended only by bug fixes
(a concurrent scenario now uses a fresh id per run so the database-level
race is exercised; a persistence-failure hook was wired into the CLI). No
competing fake webhook contract was created; the HTTP gateway is never
bypassed.

## 11. Production Meta UNKNOWN items

- The webhook verification handshake (hub.mode/hub.challenge/hub.verify_token)
- The signature scheme (X-Hub-Signature-256)
- The production webhook payload structure and event identifiers
- Subscription requirements
- BSUID/usernames production semantics (verified at the announcement level;
  exact API semantics unverified)

The simulator is SIMULATOR_ONLY — NOT VERIFIED_META. No production Meta
payload assumptions were invented; the pipeline consumes the SIMULATOR_ONLY
contract and must be reconciled with the verified Meta payload shape before
production ingestion.

## 12. Test results

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-6) | `cd backend && python -m pytest -q` | **182 passed, exit 0** (104.20s) |
| Phase 6 pipeline tests | `python -m pytest tests/test_pipeline.py` | 17 passed |
| Frontend tests | `cd frontend && npm test` | **30 passed (30), exit 0** |
| Frontend build | `npm run build` | ✓ 8/8 pages, exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Formatting | `python -m ruff format --check .` | all formatted |
| Migrations | clean DB → `alembic upgrade head` | 0001-0005 applied, exit 0; rollback to 0004 + re-upgrade verified |

## 13. E2E evidence (live)

Real FastAPI app + real embedded PostgreSQL; real HTTP submissions:

1. `python -m simulator setup --database-url ...` → fixture connection ready
2. Simulator run: **16/16 scenarios PASS** (202 accepted ×3 valid; 200
   duplicate ×4; 422 ×3 (malformed/missing/unsupported); 401 ×2; 404; 413;
   concurrent [200,202,200,200,200] — exactly one 202)
3. `python -m app.pipeline process` → **processed: 5, failed: 0, skipped: 0**
4. Database inspection:
   - event states: `{'processed': 5}` (all with processed_at)
   - customers: 2 (2 senders), identities: 2, conversations: 2, messages: 5
   - every message: type "text", conversation "open", event "processed"
   - **5/5 messages with a fully consistent tenant chain**
     (message.tenant = conversation.tenant = customer.tenant = event.tenant)
5. The gateway's idempotency held throughout (6 events submitted earlier in
   the run produced no duplicates)

## 14. Known limitations

- The pipeline consumes the SIMULATOR_ONLY payload contract; production Meta
  payload shapes are UNKNOWN_META and must be reconciled before production
  ingestion.
- No conversation closure flow (all conversations stay open; closure is
  future scope).
- No queue/worker: the CLI processor is the execution model (deterministic;
  a worker can be added in a later phase if required).
- Message ordering: `external_timestamp` (when provided) / `created_at` —
  no global sequence.
- The customer has no profile fields (name etc.) — none were required by the
  simulator contract; add with a concrete requirement only.

## 15. Deferred Phase 07 work

- AI order extraction from PROCESSED text messages (consume via
  `processing_state = 'processed'` + `message_type = 'text'`)
- Structured extraction schema + deterministic validation + ambiguity
  handling + human-review candidate creation (AI_POLICY.md applies: AI
  output is untrusted; no invention; deterministic validation)
- Conversation closure/management if extraction requires it

## 16. Exact Git checkpoint

Commit: (phase-06 commit — see `git log` after checkpoint)
Tag: phase-06-complete

## Next phase

Phase 07 — AI Order Extraction.

Do not start the next phase until this handoff is reviewed.
