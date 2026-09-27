# PHASE ROADMAP

## Phase 00 — Discovery & Reality Check

Establish repository baseline, requirements, architecture, current external API facts, risks, and acceptance criteria.

## Phase 01 — Technical Foundation

Backend/frontend foundation, configuration, database, migrations, logging, health checks, test infrastructure.

## Phase 02 — Authentication & Multi-Tenancy

Users, tenants, membership, authorization, tenant isolation.

## Phase 03 — Meta Developer Infrastructure

Meta app integration foundation, connection model, OAuth/Embedded Signup foundations, secure credential abstraction.

## Phase 04 — WhatsApp Connection

Official WhatsApp onboarding/connection flow and connection lifecycle.

## Phase 05 — Webhook Gateway

Verified webhook, event persistence, tenant resolution, idempotency, queueing.

## Phase 06 — Message Pipeline

Normalize WhatsApp messages into internal conversations/messages/customer structures.

## Phase 07 — AI Order Extraction

Structured extraction, deterministic validation, ambiguity handling, human-review candidate creation.

## Phase 08 — Order Management

Review UI/API, order state machine, audit trail, confirmation, lifecycle.

## Phase 09 — Instagram Integration

Official Instagram authorization and messaging integration into the same normalized pipeline.

## Phase 10 — Controlled Seller Responses

Inbound intent handling and controlled customer responses, only after safety/policy validation.

## Phase 11 — Excel/CSV Export

Reliable export of confirmed orders.

## Phase 12 — Billing

Plans, usage, subscription state, billing events and limits.

## Phase 13 — Security & Production Hardening

Security audit, tenant isolation audit, dependency audit, observability, backups, recovery, rate limits.

## Phase 14 — Production Release

Production deployment, real end-to-end smoke tests, monitoring, operational runbook, release evidence.
