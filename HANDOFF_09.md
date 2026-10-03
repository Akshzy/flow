# HANDOFF — PHASE 09

## Phase

Phase 09 — Instagram Integration

## 1. Phase 09 status

COMPLETE (local implementation + verification, including live E2E; the
Instagram authorization flow is UNKNOWN_META and blocked — the adapter
refuses to guess)

## 2. Starting commit

`c290e38` (= `phase-08-complete`, origin/main synced, working tree clean)

## 3. Final commit

(the phase-09 commit — see `git log` after the checkpoint)

## 4. Instagram architecture

Instagram reuses the EXISTING architecture (no parallel subsystem):

- the connection platform CHECK includes whatsapp/instagram (migration 0009)
- Instagram connections reuse the lifecycle (initiated/connected/
  disconnected), the partial unique index over ACTIVE connections per
  (tenant, platform), the credential store, and the audit events
- the connection API is platform-aware: `?platform=instagram` (default
  whatsapp — backward compatible) on GET status / POST initiate / DELETE
  disconnect
- the webhook gateway is platform-aware: the payload's `platform` field
  (default whatsapp — the Phase 5 contract stays backward compatible) drives
  the connection resolution; `/webhooks/instagram` is a route alias for the
  same handler (the route is cosmetic; the payload's platform + the
  connection mappings are authoritative)
- customer identity: UNCHANGED — UNIQUE (tenant, platform, external_user_id)
  was already platform-scoped: an Instagram identity never merges with a
  WhatsApp identity (verified: the same external id on both platforms → two
  identities)
- conversations: UNCHANGED — per (tenant, customer, connection); the
  connection carries the platform
- the message pipeline, AI extraction and order management: UNCHANGED —
  Instagram messages normalize into the SAME canonical message and flow
  through the existing extraction/order pipeline (verified E2E: an Instagram
  event → message → candidate → order with the instagram platform chain)

## 5. Meta documentation sources

(each fetched once per the network protocol)

1. https://developers.facebook.com/docs/instagram-platform — VERIFIED_META
2. https://developers.facebook.com/documentation/business-messaging/instagram-messaging — VERIFIED_META (structure)

## 6. Verified facts (VERIFIED_META)

- Instagram messaging for Floww's use case is "Messenger API support for
  Instagram" (aka the Instagram Messaging API) — for Instagram PROFESSIONAL
  accounts (Business or Creator) linked to a Facebook Page
- Two Instagram API variants: with Instagram Login; with Business Login for
  Instagram
- Embedded Signup v4 covers WhatsApp, Messenger, and Instagram Direct (the
  Phase 4 verified resource)
- The Instagram Messaging doc structure: Messages, Send a Message, Webhooks,
  App Review, Private Replies, Story Mention, Moderate Conversations API,
  User Profile API, Conversation Routing

## 7. UNKNOWN_META items

- Exact scopes/permissions for Instagram messaging
- Exact webhook payload structure/fields for Instagram messages
- Exact token exchange endpoints/parameters and token lifetimes
- Exact onboarding/session parameters (Embedded Signup v4 vs standalone)
- Exact account identifiers (IG-scoped vs page-scoped) for connection
  resolution
- Webhook subscription mechanism details

## 8. Implemented capabilities

- The platform abstraction (Platform.INSTAGRAM; migration 0009 extends the
  CHECK constraint)
- The platform-aware connection API (initiate/status/disconnect per platform;
  idempotent initiate; 409 conflict when connected; OWNER-only actions;
  forged tenant ids → 404; cross-tenant → 403)
- The platform-aware webhook gateway (the payload's platform field;
  /webhooks/instagram; the resolution per platform; idempotency intact)
- Identity separation (verified: the same external id on both platforms →
  two distinct identities)
- The pipeline E2E (an Instagram event → message → extraction candidate →
  order with the instagram platform chain — verified live)
- The frontend Settings page: per-platform connection cards (WhatsApp +
  Instagram) with honest states (Not Connected / Initiated — awaiting Meta
  authorization / Connected / disconnected) — never a fake OAuth success

## 9. Simulator limitations

- The Instagram connection-identifier semantics (the payload's
  phone_number_id for Instagram connections) and the Instagram payload
  contract are SIMULATOR_ONLY (Floww-defined for deterministic local
  testing) — NOT_PRODUCTION_META_PROOF.
- REAL META API TEST = BLOCKED (no credentials; never requested).

## 10. Webhook behavior

- POST /webhooks/instagram (the same handler as /webhooks/whatsapp): the
  size limit → the SIMULATOR_ONLY HMAC auth → validation → the platform-
  aware resolution → idempotency (the dedup key includes the platform) →
  durable persistence → the prompt ack. The WhatsApp behavior is unchanged
  (all WhatsApp webhook tests pass unchanged).

## 11. Identity model

`customer_platform_identities`: UNIQUE (tenant, platform, external_user_id)
— platform-scoped identity; no phone-number-based identity; no cross-
platform merging (verified).

## 12. Security verification

- Tenant isolation: cross-tenant → 403; forged tenant ids → 404 (verified)
- Authorization: OWNER-only initiation/disconnect (verified)
- IDOR: forged ids never resolve (verified)
- Credentials: never in responses/logs/frontend/Git (the Phase 4 store
  reused; no second mechanism)
- Logs: no message bodies (unchanged from Phase 5)
- Webhook security: the signature requirement + the idempotency intact
- No client-controlled tenant assignment (the resolution is server-side)
- No fake OAuth popup/state

## 13. Test matrix results

| Suite | Command | Result |
|---|---|---|
| Backend full (Phases 1-9) | `cd backend && python -m pytest -q` | **234 passed, exit 0** (129.66s) |
| Phase 9 Instagram tests | `python -m pytest tests/test_instagram.py` | 12 passed |
| Stability (x3 consecutive) | instagram tests | **12/12, 12/12, 12/12** — deterministic |
| Frontend tests | `cd frontend && npm test` | **41 passed (41), exit 0** |
| Frontend build | `npm run build` | 9/9 pages, exit 0 |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Lint | `npm run lint` / `python -m ruff check .` | exit 0 (both) |
| Formatting | `python -m ruff format --check .` | 59 files formatted |
| Type check (backend) | `python -m mypy app` | no issues in 31 source files |
| Migrations | clean DB → head | 0001-0009 applied, exit 0; rollback to 0008 + reapply verified |
| Regression | WhatsApp + Phase 01-08 | all pass unchanged (the pipeline/webhook/orders/extraction suites) |

## 14. Migration status

- Migration 0009 (the platform CHECK extended) — clean-DB verified;
  downgrade to 0008 (restores whatsapp-only) + reapply verified; the
  Instagram connection insert allowed (verified).

## 15. Known limitations

- The Instagram authorization flow (scopes/tokens/webhook payloads) is
  UNKNOWN_META and blocked — the adapter refuses to guess (the same boundary
  as WhatsApp since Phase 5).
- The Instagram connection-identifier semantics are SIMULATOR_ONLY (the real
  IG-scoped/page-scoped identifiers must be reconciled with the Messenger
  API for Instagram docs when verified).
- The privacy policy: the existing policy ALREADY accurately covers
  Instagram processing (section 5: "Meta products such as WhatsApp and
  Instagram") — NO policy change was needed (verified; the /privacy page
  still builds).
- No Instagram webhook subscription UI (the production webhook is blocked).

## 16. Manual Meta actions required

1. Configure the Meta app's Privacy Policy URL to the public /privacy
   endpoint after deployment (unchanged from Phase 3 — R-007).
2. Add/verify the Instagram product permissions (the Messenger API support
   for Instagram requires an Instagram Business/Creator account linked to a
   Facebook Page) — with the owner, after the exact scopes are verified
   against official docs.
3. The Instagram webhook subscription — after the webhook payload structure
   is verified (UNKNOWN_META).

## 17. Deferred work

- Phase 10 — controlled seller responses (NOT STARTED)
- The production Instagram authorization/webhook boundary (after the

- The production Instagram authorization/webhook boundary (after the Meta
  specifics are verified)
- Phase 11 (exports), Phase 12 (billing), Phase 13 (hardening),
  Phase 14 (deployment)

## 18. Exact next phase

Phase 10 — Controlled Seller Responses.

## 19. Git verification

- origin/main → the phase-09 commit (fast-forward push)
- phase-09-complete → the phase-09 commit (verified remotely)
- phase-01 through phase-08 tags remain intact on origin
- working tree clean

## Next phase

Phase 10 — Controlled Seller Responses (NOT STARTED).

Do not start the next phase until this handoff is reviewed.
