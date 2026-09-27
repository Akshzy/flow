# AI POLICY

## Principle

AI is an extraction and reasoning component, not the source of truth.

## Extraction

The model should return structured output.

Every field should support:

- value
- confidence/uncertainty where useful
- source message/reference
- missing/unknown state

## No invention

If the customer did not provide:

- phone
- address
- product
- size
- quantity
- payment method

the model must not invent it.

## Deterministic validation

After model output:

1. schema validation
2. normalization
3. required-field validation
4. business-rule validation
5. ambiguity detection
6. human-review decision

## Adversarial cases

Test:

- incomplete orders
- contradictory messages
- corrections
- cancellations
- typos
- multilingual text
- Manglish
- unrelated chat
- prompt injection
- fake product information
- ambiguous quantity
- missing address
- missing phone
- multiple orders in one conversation

## Autonomous actions

AI must not directly:

- change authoritative order state
- issue refunds
- send customer messages
- create shipping labels
- access another tenant

unless a later phase explicitly implements and tests a controlled workflow.
