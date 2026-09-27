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
