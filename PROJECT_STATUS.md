# PROJECT STATUS

## Current phase

Phase 03 — Meta Developer Infrastructure (overnight run: privacy policy +
Meta preparation)

## Status

Phase 02 COMPLETE. Phase 03 overnight run: implementation and local
verification COMPLETE; PUBLIC PRIVACY URL = NOT AVAILABLE (manual action:
deploy frontend + configure Meta). See HANDOFF_03.md.

## Completed phases

- Phase 00 — Discovery & Reality Check: documents provided in the repository
  (product, requirements, architecture, data model, integrations, webhook
  spec, AI policy, test strategy, phases, phase gate, decisions, risks).
  No HANDOFF_00.md exists; the provided documents were treated as the Phase 00
  baseline input (see DECISIONS.md ADR-006).
- Phase 01 — Technical Foundation: COMPLETE — commit `ab14529`, tag
  `phase-01-complete`, pushed to origin and verified remotely
  (`git ls-remote origin` / `git ls-remote --tags origin`).
- Phase 02 — Authentication and Multi-Tenancy: implemented and verified
  (see HANDOFF_02.md).
- Phase 03 (overnight run) — Privacy Policy page + Meta preparation:
  implemented and locally verified (see HANDOFF_03.md). Public privacy URL
  NOT AVAILABLE until deployment (manual action recorded).

## Current objective

Phase 3 overnight run is complete. Do not start Phase 4 until the
phase-03-complete handoff is reviewed.

## Last verified commit

The phase-03 commit (see `git log` after the Phase 3 checkpoint).

## Last verified tag

`phase-01-complete` and `phase-02-complete` (both pushed + verified
remotely). The `phase-03-complete` tag is created at the Phase 3 checkpoint.

## Phase 2 evidence summary

- Backend: email+password authentication with argon2id hashes; opaque
  server-side sessions (SHA-256 token hashes, TTL, logout invalidation);
  users/tenants/tenant_members/auth_sessions schema (migration 0002);
  authorization via server-side membership checks; tenant-scoped queries;
  OWNER/MEMBER roles with a DB CHECK constraint; CORS with explicit origins.
- Frontend: register/login pages, authenticated shell with tenant
  list/creation/selection and logout (Next.js + TypeScript + Tailwind).
- Tests: 109/109 backend (`python -m pytest`, exit 0 — includes the 40
  Phase 1 tests, no regressions); 18/18 frontend (`npm run test`, exit 0).
- Checks: ruff check / ruff format --check / mypy — all exit 0;
  frontend tsc --noEmit / eslint / next build — all exit 0.
- Tenant isolation: cross-tenant GET/PATCH/DELETE → 403, forged UUID → 404,
  list scoping, data-layer IDOR checks — tested AND verified against the
  live running application (A→A 200; A→B 403; B→A 403; no token 401).

## Phase 3 (overnight run) evidence summary

- `/privacy` page: server component rendering the complete policy from
  `FLOWW_PRIVACY_POLICY.md` (17 sections, 7 [TO BE COMPLETED] placeholders
  preserved verbatim and styled distinctly); footer link added to the app
  layout (additive only).
- Verified: /privacy → HTTP 200 without authentication (live); build
  prerenders it (7/7 pages); tsc + eslint exit 0; backend 109/109 and
  frontend 18/18 tests pass (no regressions).
- Meta: existing app is owner-attested only (NOT technically verified);
  official docs site reachable but detailed requirements UNKNOWN
  (client-rendered content); real Meta API verification BLOCKED (no
  credentials in this environment; owner unavailable — not requested).
- No Meta secrets or speculative Meta configuration were added (none
  required by an implemented Phase 3 component); only NEXT_PUBLIC_API_URL
  exists client-side (a URL, not a secret).

## Known unknowns

- The GitHub Actions CI workflow has not been executed (no runner in this
  environment); it runs the same commands that were verified locally.
- The Windows event-loop policy for psycopg async is deprecated in Python
  3.14 (removal slated for 3.16); revisit when targeting a newer Python or
  Linux-only hosting (see DECISIONS.md ADR-005).
- External integrations (Meta/WhatsApp/Instagram/AI) are NOT implemented and
  NOT verified — future phases.

## Rules

This file records actual repository state. Do not write aspirational claims here.
