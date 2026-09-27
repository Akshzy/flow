# ARCHITECTURE

## High-level

Seller Web App
→ API
→ Authentication/Tenant Layer
→ Application Services
→ PostgreSQL

External platforms
→ Webhook Gateway
→ Event Store
→ Queue/Worker
→ Message Normalizer
→ AI Extraction
→ Deterministic Validation
→ Order Service
→ Seller Review
→ Export

## Recommended stack

Frontend:
- Next.js
- TypeScript
- Tailwind

Backend:
- FastAPI
- Python

Data:
- PostgreSQL
- Redis/queue

Storage:
- S3-compatible object storage when required

AI:
- structured-output capable model

## Design rule

External platform adapters must be isolated from core order logic.

The core application should consume normalized internal events/messages instead of depending on one vendor's payload structure.

## Webhook rule

Webhook handlers should:

1. authenticate/verify the request
2. identify the tenant/platform connection
3. validate basic structure
4. persist the raw event safely
5. enforce idempotency
6. enqueue work
7. return promptly

Slow AI processing must not block the webhook request.
