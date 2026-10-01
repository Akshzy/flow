"""AI order extraction layer (Phase 7).

Provides:

- Extraction schema (Pydantic models) for order candidates.
- Deterministic test double for AI provider (returns a dictionary representing
  the AI output).
- Validation and ambiguity detection.
- Persistence of extraction candidates.

The real AI provider integration is intentionally left as a stub; the
deterministic test double must be used for testing and development.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, validator


class ExtractionStatus(str, Enum):
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
    variant: Optional[str] = Field(
        None,
        description="Variant of the product (e.g., 'organic', 'spicy').",
    )
    size: Optional[str] = Field(
        None,
        description="Size of the product (e.g., 'large', 'medium').",
    )
    color: Optional[str] = Field(
        None,
        description="Color of the product (e.g., 'blue', 'red').",
    )


class OrderCandidate(BaseModel):
    """Structured order candidate extracted from a message."""

    items: List[OrderItem] = Field(
        ...,
        description="List of ordered items (at least one item required).",
        min_length=1,
    )

    @validator("items")
    def at_least_one_item(cls, v):
        if len(v) < 1:
            raise ValueError("At least one item is required")
        return v


def extract_order_candidate_from_text(
    text: str,
) -> Dict[str, Any]:
    """Deterministic test double for AI extraction.

    This function simulates an AI provider that returns a dictionary
    representing the AI output for known test phrases. For any other input,
    it returns a dictionary that will fail validation (to simulate an
    invalid extraction).

    In a real implementation, this would call an external AI provider and
    return the parsed JSON output.

    Returns:
        dict: The AI output as a dictionary.
    """
    # Deterministic test double: only recognize a few specific phrases.
    # This is for testing purposes only.
    text_lower = text.strip().lower()
    if text_lower == "i want two blue shirts":
        return {
            "items": [
                {
                    "product": "shirt",
                    "quantity": 2,
                    "color": "blue",
                }
            ]
        }
    elif text_lower == "hello, i would like to order 2 pizzas":
        return {
            "items": [
                {
                    "product": "pizza",
                    "quantity": 2,
                }
            ]
        }
    elif text_lower == "send me the same one as before":
        # Ambiguous: we don't have context, so we cannot determine what "same one" is.
        # We return a dictionary that is missing the product field to trigger NEEDS_REVIEW.
        return {
            "items": [
                {
                    "quantity": 0,  # This will also be invalid (value error) but we already have a missing field.
                }
            ]
        }
    else:
        # For any other text, we return a dictionary that will fail validation.
        return {
            "items": [
                {
                    "product": "",  # missing
                    "quantity": 0,  # invalid
                }
            ]
        }


def validate_and_determine_status(
    ai_output: Dict[str, Any],
) -> Tuple[Optional[OrderCandidate], ExtractionStatus]:
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