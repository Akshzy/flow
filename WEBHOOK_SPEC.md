# WEBHOOK SPECIFICATION

## Required behavior

A webhook endpoint must:

1. accept the provider's documented request format
2. perform required verification
3. validate signatures/tokens where documented
4. resolve the correct platform connection/tenant
5. persist the event
6. enforce idempotency
7. enqueue asynchronous processing
8. return the documented success response promptly

## Failure cases

Test:

- invalid verification
- invalid signature
- malformed payload
- unknown event
- duplicate event
- unknown tenant
- revoked connection
- database failure
- queue failure
- timeout
- provider retry

## Security

Do not trust tenant IDs supplied by an untrusted client.

Tenant resolution must be based on authenticated/verified provider information and stored connection metadata.

## Processing

Never perform expensive LLM inference synchronously inside the webhook request unless there is a verified, measured reason and explicit architecture approval.
