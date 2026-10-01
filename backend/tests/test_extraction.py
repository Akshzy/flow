"""Tests for the AI order extraction layer (Phase 7)."""

import pytest
import uuid
from datetime import UTC, datetime
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.extraction import ExtractionStatus, OrderCandidate, OrderItem, extract_order_candidate_from_text, validate_and_determine_status
from app.models import Message
from app.extraction_service import extract_and_save_candidate
from app.order_service import get_order_by_id
from app.models import OrderStatus


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
    return {
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


@pytest.mark.anyio
async def test_extraction_saves_candidate_and_order():
    """Test that a valid message creates a candidate and an order."""
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:55433/floww_test"
    )
    engine = create_async_engine(database_url)
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as db:
        # Create a message
        message = Message(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-00000000a001"),
            customer_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            source_event_id=uuid.uuid4(),
            external_event_id="wamid.test",
            message_type="text",
            body="I want two blue shirts",
            external_timestamp=datetime.now(UTC),
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        candidate = await extract_and_save_candidate(db, message)

        assert candidate is not None
        assert candidate.tenant_id == message.tenant_id
        assert candidate.customer_id is not None
        assert candidate.total_amount == 100.00
        assert candidate.currency == "USD"
        assert len(candidate.items) == 2
        assert candidate.status == OrderStatusCandidate.VALID

        # Check that an order was created
        order = await get_order_by_id(db, candidate.id)
        assert order is not None
        assert order.tenant_id == message.tenant_id
        assert order.customer_id == message.customer_id
        assert order.status == OrderStatus.NEW
        assert order.total_amount == candidate.total_amount