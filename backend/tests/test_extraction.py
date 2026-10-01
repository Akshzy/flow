"""Tests for the AI order extraction layer (Phase 7)."""

from app.extraction import ExtractionStatus, OrderCandidate, OrderItem, extract_order_candidate_from_text, validate_and_determine_status


def test_order_item_valid():
    """Valid order item creation."""
    item = OrderItem(product="shirt", quantity=2, color="blue")
    assert item.product == "shirt"
    assert item.quantity == 2
    assert item.color == "blue"


def test_order_item_missing_product():
    """Missing product should raise validation error."""
    try:
        OrderItem(product="", quantity=2)
        assert False, "Expected validation error"
    except Exception as e:
        assert "product" in str(e)


def test_order_item_non_positive_quantity():
    """Non-positive quantity should raise validation error."""
    try:
        OrderItem(product="shirt", quantity=0)
        assert False, "Expected validation error"
    except Exception as e:
        assert "quantity" in str(e)


def test_order_candidate_valid():
    """Valid order candidate with one item."""
    candidate = OrderCandidate(items=[OrderItem(product="shirt", quantity=2)])
    assert len(candidate.items) == 1
    assert candidate.items[0].product == "shirt"
    assert candidate.items[0].quantity == 2


def test_order_candidate_empty_items():
    """Empty items list should raise validation error."""
    try:
        OrderCandidate(items=[])
        assert False, "Expected validation error"
    except Exception as e:
        assert "items" in str(e)


def test_extract_order_candidate_from_text_known_phrases():
    """Deterministic test double returns expected output for known phrases."""
    # Known phrase 1
    output = extract_order_candidate_from_text("I want two blue shirts")
    assert output == {
        "items": [
            {
                "product": "shirt",
                "quantity": 2,
                "color": "blue",
            }
        ]
    }

    # Known phrase 2
    output = extract_order_candidate_from_text("Hello, I would like to order 2 pizzas")
    assert output == {
        "items": [
            {
                "product": "pizza",
                "quantity": 2,
            }
        ]
    }

    # Ambiguous phrase: we return a dict missing the product field.
    output = extract_order_candidate_from_text("Send me the same one as before")
    assert output == {
        "items": [
            {
                "quantity": 0,
            }
        ]
    }

    # Unknown phrase
    output = extract_order_candidate_from_text("Hello world")
    assert output == {
        "items": [
            {
                "product": "",
                "quantity": 0,
            }
        ]
    }


def test_validate_and_determine_status():
    """Validation and status determination works correctly."""
    # Valid output
    valid_output = {
        "items": [
            {
                "product": "shirt",
                "quantity": 2,
                "color": "blue",
            }
        ]
    }
    candidate, status = validate_and_determine_status(valid_output)
    assert isinstance(candidate, OrderCandidate)
    assert status == ExtractionStatus.EXTRACTED
    assert candidate.items[0].product == "shirt"
    assert candidate.items[0].quantity == 2

    # Missing required field (product) -> NEEDS_REVIEW
    missing_output = {
        "items": [
            {
                "quantity": 2,  # product missing
            }
        ]
    }
    candidate, status = validate_and_determine_status(missing_output)
    assert candidate is None
    assert status == ExtractionStatus.NEEDS_REVIEW

    # Invalid quantity (negative) -> INVALID
    invalid_output = {
        "items": [
            {
                "product": "shirt",
                "quantity": -1,  # invalid
            }
        ]
    }
    candidate, status = validate_and_determine_status(invalid_output)
    assert candidate is None
    assert status == ExtractionStatus.INVALID

    # Both missing product and invalid quantity -> we still check missing first? Our function checks for any missing.
    # If there is a missing field, we return NEEDS_REVIEW.
    mixed_output = {
        "items": [
            {
                "quantity": -1,  # product missing, quantity invalid
            }
        ]
    }
    candidate, status = validate_and_determine_status(mixed_output)
    assert candidate is None
    assert status == ExtractionStatus.NEEDS_REVIEW  # because product is missing