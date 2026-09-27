# PHASE 02 — AUTHENTICATION AND MULTI-TENANCY

## Objective

Create a secure tenant boundary.

## Required work

- user model
- tenant model
- memberships/roles
- authentication
- authorization
- tenant-scoped service/repository access
- basic account/tenant UI or API

## Mandatory tests

- signup/login
- invalid credentials
- expired/invalid session
- unauthorized endpoint
- authorized endpoint
- tenant A isolation
- tenant B isolation
- cross-tenant access attempts
- role restrictions
- direct-object-ID access attempts
- database query tenant scoping

## Completion

Cross-tenant tests must pass. Create handoff, status evidence, commit and tag `phase-02-complete`, then STOP.
