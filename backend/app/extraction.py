"""AI order extraction layer (Phase 7).

Provides:

- Extraction schema (Pydantic models) for order candidates.
- Deterministic test double for the AI provider (SIMULATOR_ONLY for the AI
  layer; the real AI provider integration is intentionally left for a later
  phase and must never be faked).
- Validation, required-field validation and ambiguity detection.
- Status determination.

Hard rule (AI_POLICY.md): missing information remains missing. The double
NEVER invents products, quantities, prices, variants, customer identity or
addresses — fields the customer did not provide stay absent from the output.
Uncertainty (ambiguous references, contradictory quantities, unknown
products) yields a candidate missing the product key, which required-field
validation maps to NEEDS_REVIEW (human review). Non-order messages map to
the invalid fallback.
"""

from __future__ import annotations

import enum
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class ExtractionStatus(enum.StrEnum):
    """The extraction status after validation."""

    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    INVALID = "invalid"


class OrderItem(BaseModel):
    """A single item in an order candidate."""

    product: str = Field(
        ...,
        description="The product being ordered (e.g., 'shirt', 'pizza').",
        min_length=1,
    )
    quantity: int = Field(
        ...,
        description="The quantity of the product (must be a positive integer).",
        gt=0,
    )
    variant: str | None = Field(
        None,
        description="Variant of the product (e.g., 'organic', 'spicy').",
    )
    size: str | None = Field(
        None,
        description="Size of the product (e.g., 'large', 'medium').",
    )
    color: str | None = Field(
        None,
        description="Color of the product (e.g., 'blue', 'red').",
    )


class OrderCandidate(BaseModel):
    """Structured order candidate extracted from a message."""

    items: list[OrderItem] = Field(
        ...,
        description="List of ordered items (at least one item required).",
        min_length=1,
    )

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v: list[OrderItem]) -> list[OrderItem]:
        if len(v) < 1:
            raise ValueError("At least one item is required")
        return v


# --- SIMULATOR_ONLY AI stand-in vocabulary (deterministic; the real AI
# provider integration is a later phase and must never be faked) -------------

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
SIZES = ("large", "medium", "small")
COLORS = ("blue", "red", "green", "black", "white")
# The stand-in vocabulary: the double extracts products it can recognize
# deterministically; unknown words (typos, other languages) are never
# invented — they fall through to the invalid fallback.
PRODUCTS = ("shirt", "pizza", "shoes", "book", "cake", "bag", "charger", "mug")

# Correction/ambiguity markers: phrases that reference prior context the
# double cannot resolve (deterministic NEEDS_REVIEW).
_AMBIGUOUS_MARKERS = ("same one as before", "same as before", "make it", "actually", "instead")

_ITEM_PATTERN = (
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*"
    r"((?:large|medium|small)\s+)?"
    r"((?:blue|red|green|black|white)\s+)?"
    r"(shirt|pizza|shoes|book|cake|bag|charger|mug)s?\b"
)


def _extract_items(text_lower: str) -> list[dict[str, Any]] | None:
    """Deterministic item extraction from a lowercased phrase.

    Returns None when quantities are contradictory/ambiguous for the same
    product+variant (human review). Fields the customer did not provide
    stay absent (no invention).
    """
    items: list[dict[str, Any]] = []
    seen: dict[tuple[str, str | None, str | None], int] = {}
    for quantity_word, size, color, product in re.findall(_ITEM_PATTERN, text_lower):
        if not quantity_word:
            # The product is mentioned without a quantity: the quantity stays
            # missing (the key is absent) → required-field validation maps
            # this to NEEDS_REVIEW.
            items.append({"product": product})
            continue
        quantity = int(quantity_word) if quantity_word.isdigit() else WORD_NUMBERS[quantity_word]
        size_value = size.strip() if size else None
        color_value = color.strip() if color else None
        key = (product, size_value, color_value)
        if key in seen and seen[key] != quantity:
            # Contradictory quantities for the same product+variant
            # (e.g. "2 pizzas, no wait, 5 pizzas") → ambiguous → the product
            # key is omitted → NEEDS_REVIEW.
            return None
        seen[key] = quantity
        item: dict[str, Any] = {"product": product, "quantity": quantity}
        if size_value:
            item["size"] = size_value
        if color_value:
            item["color"] = color_value
        items.append(item)
    return items


def extract_order_candidate_from_text(
    text: str,
) -> dict[str, Any]:
    """Deterministic test double for the AI extraction provider.

    SIMULATOR_ONLY: this stand-in implements deterministic phrase-pattern
    matching for the Phase 7 test corpus. In a real implementation this
    would call the external AI provider with structured output — that
    integration is a later phase and is never faked here.

    Behavior (deterministic; see the Phase 7 test corpus):

    - exact corpus phrases → their documented extraction
    - explicit product phrases (quantity/size/color + a known product) →
      EXTRACTED items; fields the customer did not provide stay absent
    - product without a quantity → the quantity key is absent →
      NEEDS_REVIEW (missing quantity)
    - contradictory quantities for the same product+variant →
      NEEDS_REVIEW (ambiguity)
    - correction/ambiguity markers referencing unresolvable context →
      NEEDS_REVIEW
    - everything else (unrelated chat, typos of unknown products,
      Malayalam/Manglish, cancellations, prompt injection) → the invalid
      fallback: the double does not invent an order. Prompt-injection
      instructions have no effect beyond the literal text.

    Returns:
        dict: The AI output as a dictionary.
    """
    text_lower = text.strip().lower()

    # 1. Exact corpus phrases (stable, documented).
    if text_lower == "i want two blue shirts":
        return {"items": [{"product": "shirt", "quantity": 2, "color": "blue"}]}
    if text_lower == "hello, i would like to order 2 pizzas":
        return {"items": [{"product": "pizza", "quantity": 2}]}
    if text_lower == "send me the same one as before":
        # Ambiguous reference: the product cannot be determined without
        # conversation context → missing product → NEEDS_REVIEW.
        return {"items": [{"quantity": 0}]}

    # 2. Correction/ambiguity markers referencing unresolvable context.
    if any(marker in text_lower for marker in _AMBIGUOUS_MARKERS):
        return {"items": [{"quantity": 0}]}

    # 3. Deterministic extraction from explicit product phrases.
    items = _extract_items(text_lower)
    if items is None:
        # Contradictory/ambiguous quantities → NEEDS_REVIEW.
        return {"items": [{"quantity": 0}]}
    if items:
        return {"items": items}

    # 4. Fallback: no order could be confidently extracted (unrelated chat,
    #    typos of unknown products, Malayalam/Manglish, cancellations, prompt
    #    injection). The double does not invent an order; the output fails
    #    required-field validation (deterministically INVALID).
    return {"items": [{"product": "", "quantity": 0}]}


def validate_and_determine_status(
    ai_output: dict[str, Any],
) -> tuple[OrderCandidate | None, ExtractionStatus]:
    """Validate the AI output against the OrderCandidate schema and determine
    the extraction status.

    Args:
        ai_output: The dictionary output from the AI provider.

    Returns:
        A tuple (candidate, status) where:
        - candidate is the validated OrderCandidate if status is EXTRACTED,
          otherwise None.
        - status is one of ExtractionStatus.
    """
    try:
        candidate = OrderCandidate(**ai_output)
        return candidate, ExtractionStatus.EXTRACTED
    except ValidationError as e:
        # Check if any of the errors are about missing required fields.
        missing_fields = False
        for error in e.errors():
            if error.get("type") == "missing":
                missing_fields = True
                break
        if missing_fields:
            return None, ExtractionStatus.NEEDS_REVIEW
        else:
            return None, ExtractionStatus.INVALID
