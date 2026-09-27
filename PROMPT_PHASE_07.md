# PI PROMPT — PHASE 07: AI ORDER EXTRACTION

You are executing exactly ONE development phase of the OrderFlow AI project.

## PRIMARY RULE

Execute ONLY Phase 07 — AI Order Extraction.

DO NOT start Phase 08.
DO NOT implement future-phase functionality.
DO NOT silently expand scope.

You MUST stop after the phase is verified and checkpointed.

## REQUIRED READING

Before changing code, read:

- AGENT_RULES.md
- PRODUCT.md
- REQUIREMENTS.md
- ARCHITECTURE.md
- DATA_MODEL.md
- INTEGRATIONS.md
- WEBHOOK_SPEC.md
- AI_POLICY.md
- TEST_STRATEGY.md
- PHASES.md
- PHASE_GATE.md
- PROJECT_STATUS.md
- PHASE_07_AI_ORDER_EXTRACTION.md
- all prior HANDOFF_*.md files that exist

Inspect the repository itself. Documentation is not proof of implementation.

## TRUTH RULE

Never invent:

- APIs
- endpoints
- permissions
- SDK behavior
- payloads
- environment variables
- database schema
- test results
- integration results

If something cannot be verified, write UNKNOWN.

Do not report a mock, stub, local simulation, or unit test as a real external integration.

## EXECUTION

### Step 1 — Inspect

Inspect:

- git status
- repository tree
- dependencies
- source
- tests
- configuration
- migrations
- existing integrations
- previous phase evidence

Identify what already exists.

### Step 2 — Plan

Before implementation, create a concise phase implementation plan.

Map every requirement to code and tests.

Do not plan future phases.

### Step 3 — Implement

Implement only the current phase.

Prefer small, testable components.

Preserve existing working behavior.

Do not rewrite unrelated code.

### Step 4 — Test continuously

Run relevant tests while implementing.

Do not wait until the end to discover basic failures.

### Step 5 — Failure testing

Test applicable negative paths:

- invalid input
- missing input
- unauthorized access
- forbidden access
- duplicate events/requests
- dependency failure
- timeout
- malformed payload
- invalid state
- retry behavior
- tenant isolation
- secret handling

### Step 6 — Full verification

Run all relevant:

- unit tests
- integration tests
- API/contract tests
- security tests
- build
- type checks
- lint/static checks
- migrations
- end-to-end tests where applicable

Fix failures.

Then rerun the relevant suite from a clean state.

### Step 7 — External verification

If this phase touches an external API:

1. Re-check current authoritative documentation.
2. Record exact verified behavior.
3. Perform a real sandbox/test integration when possible.
4. Clearly distinguish:
   - VERIFIED
   - PARTIALLY VERIFIED
   - NOT VERIFIED
   - UNKNOWN

Never claim production functionality from a local mock.

### Step 8 — Acceptance gate

Evaluate every acceptance criterion in the phase document.

For each criterion record:

- status
- test/evidence
- relevant file
- command used where applicable

If any mandatory criterion fails:

STATUS = BLOCKED

Do not continue.

### Step 9 — Documentation

Update:

- PROJECT_STATUS.md
- relevant architecture/data/integration docs
- DECISIONS.md if an architectural decision was made
- RISKS.md if risks changed

Create:

`HANDOFF_07.md`

The handoff must contain:

- completed work
- files changed
- tests run
- exact results
- external verification
- known limitations
- UNKNOWN items
- remaining work
- next phase prerequisites

### Step 10 — Security and git review

Before committing:

- inspect git diff
- inspect git status
- scan for secrets
- ensure no credentials are committed
- ensure no generated junk is committed
- ensure no future-phase implementation slipped in

### Step 11 — Checkpoint

If and ONLY IF all mandatory gates pass:

Commit:

`phase(07): complete ai order extraction`

Create tag:

`phase-07-complete`

Update PROJECT_STATUS.md with:

`STATUS: COMPLETE`

### Step 12 — Stop

After the checkpoint:

STOP.

Do not begin Phase 08.

## FINAL RESPONSE FORMAT

Return only a factual phase report containing:

1. Phase
2. Status: COMPLETE or BLOCKED
3. Implemented
4. Tests executed
5. Test results
6. Acceptance criteria evidence
7. External integration verification
8. Security checks
9. Files changed
10. Commit
11. Tag
12. Known limitations
13. UNKNOWN items
14. Next phase prerequisites

Never claim success without evidence.
