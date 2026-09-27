# OrderFlow AI — Pi Agent Development Pack

This repository must be developed strictly one phase at a time.

## Non-negotiable rule

Pi MUST NOT begin Phase N+1 until Phase N has:

1. Been implemented.
2. Passed required automated tests.
3. Passed required integration tests where applicable.
4. Passed build/type/lint/static checks where applicable.
5. Passed acceptance criteria.
6. Had failure and edge cases tested.
7. Been documented.
8. Had `PROJECT_STATUS.md` updated.
9. Had a `HANDOFF_NN.md` created.
10. Had git diff and secret checks completed.
11. Been committed.
12. Been tagged.
13. Been explicitly marked `COMPLETE`.

If any mandatory item is not verified, the phase is `BLOCKED`.

Pi MUST STOP after completing a phase. It must not continue automatically.

## Truth model

Every significant claim must be classified as:

- VERIFIED
- INFERRED
- UNKNOWN
- NOT IMPLEMENTED
- BLOCKED

Never replace UNKNOWN with an assumption.

A mock, stub, fixture, local simulation, or unit test MUST NOT be reported as a real external integration.

## Phase lifecycle

READ → INSPECT → PLAN → IMPLEMENT → TEST → VERIFY → FIX → RETEST → DOCUMENT → GIT CHECKPOINT → STOP

## Core files

- `AGENT_RULES.md`
- `PRODUCT.md`
- `REQUIREMENTS.md`
- `ARCHITECTURE.md`
- `DATA_MODEL.md`
- `INTEGRATIONS.md`
- `WEBHOOK_SPEC.md`
- `AI_POLICY.md`
- `TEST_STRATEGY.md`
- `PHASES.md`
- `PHASE_GATE.md`
- `DECISIONS.md`
- `RISKS.md`
- `PROJECT_STATUS.md`

## Phase documents

Each phase has a corresponding `PHASE_XX_*.md` specification and a `PROMPT_PHASE_XX.md` execution prompt.

The prompts are intentionally repetitive. This is deliberate: each phase must be independently executable and independently verifiable.
