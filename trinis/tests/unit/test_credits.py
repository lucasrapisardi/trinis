import pytest
import uuid
from unittest.mock import MagicMock, patch
from app.services.credits import debit_credits, add_credits, get_balance, CREDIT_COSTS


def test_credit_costs_defined():
    assert "product_enrich" in CREDIT_COSTS
    assert "bulk_enhance" in CREDIT_COSTS
    assert CREDIT_COSTS["product_enrich"] == 1
    assert CREDIT_COSTS["bulk_enhance"] == 5


def test_debit_credits_insufficient(mocker):
    db = MagicMock()
    # Simulate no rows returned (insufficient balance)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    db.execute.return_value = mock_result

    tenant_id = uuid.uuid4()
    result = debit_credits(db, tenant_id, "product_enrich", quantity=1)
    assert result is False


def test_debit_credits_success(mocker):
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (99,)  # new balance
    db.execute.return_value = mock_result

    tenant_id = uuid.uuid4()
    result = debit_credits(db, tenant_id, "product_enrich", quantity=1)
    assert result is True
    db.commit.assert_called_once()


def test_add_credits(mocker):
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (150,)  # new balance
    db.execute.return_value = mock_result

    tenant_id = uuid.uuid4()
    new_balance = add_credits(db, tenant_id, 50, reference_id="pi_test")
    assert new_balance == 150
    db.commit.assert_called_once()
