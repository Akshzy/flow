# INTEGRATIONS

## Meta

The application must use official Meta APIs and authorization mechanisms.

Do not use:

- WhatsApp Web scraping
- browser automation against consumer WhatsApp
- stolen/session cookies
- customer passwords
- unofficial APIs

### Verification requirement

Before implementing a Meta-dependent phase, verify current official Meta documentation for:

- product/API version
- authentication/onboarding flow
- required permissions
- account requirements
- business/WABA/phone relationships where applicable
- webhook subscription
- webhook verification
- token behavior
- review requirements
- development vs production limitations
- current deprecations

Record exact verified facts in the relevant phase evidence.

### Phase 03 verification record (overnight run)

- Official documentation reachability: the WhatsApp Business Platform docs
  site (developers.facebook.com/docs/whatsapp/, canonical URL) was reachable
  (HTTP 200) from this environment; the detailed page content is
  client-rendered and detailed current requirements (permissions, scopes,
  token lifetimes, Embedded Signup specifics) could NOT be extracted —
  classified UNKNOWN pending verification in the phases that implement
  Meta-specific code.
- Existing Meta app (owner-attested, NOT technically verified): name "floww",
  type Business, mode Development, WhatsApp product added, WhatsApp API setup
  configured, test phone number configured, WABA configured, phone number ID
  configured, access token generated. The access token was NOT requested,
  printed, logged, or stored — it remains with the owner.
- Real Meta API verification: BLOCKED — required credentials unavailable in
  this environment (owner unavailable; not requested per safety rules).
- Privacy Policy URL for Meta app review: /privacy exists in the app;
  PUBLIC PRIVACY URL = NOT AVAILABLE (no public deployment yet).

### Phase 04 verification record (autonomous run)

Official Meta resources consulted (each fetched once, HTTP 200):

1. "Unified Onboarding on WhatsApp" (June 16, 2026, developers.meta.com,
   by a Meta Partner Engineer) — VERIFIED: "Embedded Signup v4 is a new
   unified onboarding architecture that allows developers to integrate
   WhatsApp, Messenger, and Instagram Direct APIs through a single
   streamlined flow instead of separate integrations", with a migration
   path from legacy v2/v3.
2. "WhatsApp Account Model Evolution" (June 16, 2026, by a Meta Business
   Engineer) — VERIFIED: "A new account architecture for the WhatsApp
   Business Platform splits the existing WhatsApp Business Account (WABA)
   into two types: a WhatsApp Account (WAAC) for phone numbers and a
   Messaging Account (PMA) for templates and billing", enabling a single
   phone number to be shared across multiple partners/integrations while
   keeping billing separate; changes affect Embedded Signup and Cloud API
   calls.
3. "WhatsApp Usernames" (June 16, 2026, by Meta Business/Partner
   Engineers) — VERIFIED: WhatsApp is introducing Usernames and a new
   backend identifier, the Business Scoped User ID (BSUID), which will
   replace phone numbers for users who adopt usernames; includes the
   30-day phone number visibility rule and the contact-book service /
   REQUEST_CONTACT_INFO button.

Still UNKNOWN (detailed implementation specifics live in the video
content/dashboard, not the extractable static documentation — and no
Meta implementation decisions requiring them were made in this run):

- exact Embedded Signup v4 session/configuration parameters
- exact OAuth scopes/permissions for the authorization flow
- exact token exchange endpoints and request/response shapes
- exact authorization callback payload structures
- current de-authorization endpoint/behavior
- applicability of the Admin Verification path to this app's setup

REAL META API VERIFICATION = BLOCKED — required credentials unavailable in
this environment; the owner's access token was never requested, printed,
logged, or stored.

PUBLIC META CALLBACK = BLOCKED — the backend is not publicly deployed; the
frontend is deployed at https://flow-psi-lac.vercel.app/ but the backend
callback infrastructure is not available.

## Instagram

Verify current official requirements before implementation, including:

- account type
- login/authorization model
- messaging permissions
- webhook/event requirements
- token handling
- review requirements
- development/production limitations

## Other providers

Use the same evidence standard.

Never treat a third-party blog as sufficient proof for a critical current API behavior when official documentation exists.

### Phase 05 verification record (autonomous run)

- META webhook verification (hub.mode/hub.challenge/hub.verify_token) and
  the X-Hub-Signature-256 signature scheme: UNKNOWN_META — the webhook docs
  pages are client-rendered (one fetch attempt per resource; only a JS shell
  was retrievable). The production Meta webhook boundary is NOT implemented
  and is explicitly blocked (503 webhook_not_configured in production); see
  WEBHOOK_SPEC.md and DECISIONS.md ADR-012.
- SIMULATOR_ONLY: a Floww-defined HMAC-SHA256 contract (raw bytes,
  constant-time compare, env-gated) is implemented for deterministic local
  testing — never Meta's production scheme.
- Connection resolution uses VERIFIED_META identifiers (phone_number_id /
  waba_id mapped in platform_connections — server-controlled mappings); the
  payload's tenant fields are never trusted (verified by tests + live run).

### Phase 09 verification record (Instagram)

VERIFIED_META (official Meta documentation, fetched once per resource):

- Instagram messaging for Floww's use case is "Messenger API support for
  Instagram" (also known as the Instagram Messaging API in the Developer
  Policies) — for Instagram PROFESSIONAL accounts (Business or Creator)
  linked to a Facebook Page (developers.facebook.com/docs/instagram-platform).
- Two Instagram API variants exist: "Instagram API with Instagram Login"
  (Instagram Business/Creator accounts) and "Instagram API with Business
  Login for Instagram" (requires a linked Facebook Page).
- Embedded Signup v4 is a unified onboarding architecture covering WhatsApp,
  Messenger, and Instagram Direct APIs (Phase 4's verified resource).
- The Instagram Messaging documentation structure exists: Messages, Send a
  Message, Webhooks, App Review, Private Replies, Story Mention, Moderate
  Conversations API, User Profile API, Conversation Routing.

UNKNOWN_META (the detailed docs pages are client-rendered; not extractable):

- Exact scopes/permissions for Instagram messaging
- Exact webhook payload structure/fields for Instagram messages
- Exact token exchange endpoints/parameters and token lifetimes
- Exact onboarding/session parameters (Embedded Signup v4 vs standalone)
- Exact account identifiers (IG-scoped vs page-scoped) for connection
  resolution
- Webhook subscription mechanism details

REAL META API VERIFICATION = BLOCKED (no credentials in this environment;
never requested per the safety rules).

SIMULATOR_ONLY: the Instagram connection-identifier semantics (the
payload's phone_number_id for Instagram connections) and the Instagram
payload contract are Floww-defined for deterministic local testing — never
production Meta proof.

### Phase 10 verification record (controlled seller responses)

- The Meta SEND API (send a message via the platform): UNKNOWN_META — the
  exact send endpoint/parameters have not been verified from official
  documentation in this environment. The response service's send workflow
  goes through the platform adapter boundary; with no verified production
  sender the send fails with a controlled error
  (`platform_send_unavailable`, 503) — the response stays APPROVED
  (retryable, bounded by MAX_SEND_ATTEMPTS=5). A fake success is never
  reported; a deterministic test double is used for the send-success tests
  only.
- The Instagram Messaging doc's "Send a Message" section exists in the
  navigation; its detailed content is client-rendered (not extractable).
