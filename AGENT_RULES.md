# AGENT RULES

## 1. Phase isolation

Work ONLY on the current requested phase.

Do not implement future-phase features, even if they seem useful.

Do not silently expand scope.

## 2. Repository first

Before editing:

- inspect repository structure
- inspect package manifests
- inspect configuration
- inspect database/migrations
- inspect tests
- inspect existing documentation
- inspect git status
- inspect existing branches/tags where relevant

Do not assume the repository is empty or matches the documentation.

## 3. Evidence over assumptions

For every important implementation decision, use evidence from:

1. Existing repository
2. Tests
3. Official vendor documentation
4. Explicit project requirements
5. Documented architectural decisions

If evidence is unavailable:

`UNKNOWN`

Do not invent.

## 4. External APIs

For Meta, payment providers, hosting APIs, LLM providers, or any external platform:

- verify current documentation before implementation
- record API/version/permission facts
- distinguish documented behavior from inference
- never invent endpoint names, scopes, payloads, webhook fields, or OAuth behavior

Current external-platform behavior must be rechecked when the phase requires it.

## 5. Testing

A phase is not complete because the code compiles.

Use the applicable layers:

- unit tests
- integration tests
- API/contract tests
- database tests
- security tests
- failure-path tests
- end-to-end tests
- manual verification
- external sandbox/production verification where required

## 6. AI safety

AI output is untrusted data.

AI must not:

- invent missing order information
- silently change authoritative state
- bypass validation
- bypass authorization
- execute arbitrary tools
- send customer-facing messages without an approved workflow
- be treated as proof that an external integration works

## 7. Multi-tenancy

Never allow one tenant to access another tenant's:

- users
- customers
- conversations
- messages
- orders
- credentials
- files
- analytics

Cross-tenant tests are mandatory whenever tenant-aware functionality exists.

## 8. Secrets

Never commit:

- access tokens
- client secrets
- API keys
- database passwords
- webhook secrets
- private keys
- production credentials

Use environment variables or a proper secret-management mechanism.

## 9. Completion

Never mark a phase complete if:

- mandatory tests fail
- acceptance criteria are unverified
- a required external dependency is unknown
- the implementation is only mocked
- a security boundary is untested
- documentation is stale
- git checkpoint is missing

## 10. Stop rule

After completing the current phase:

- update status
- create handoff
- commit
- tag
- print final evidence report
- STOP

Do not begin the next phase.
