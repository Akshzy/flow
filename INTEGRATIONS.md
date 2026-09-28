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
