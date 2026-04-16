"""Tests for SPNI integration endpoints (routers/spni.py + services/spni_service.py)."""
from contextlib import contextmanager
from datetime import datetime, timezone, date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
import app

client = TestClient(app.app)


# ── Fixtures / helpers ──────────────────────────────────────────────────


def _make_account(**overrides):
    defaults = {
        "id": "acct-001",
        "bank_name": "SCB",
        "bank_code": "scb",
        "normalized_account_number": "1234567890",
        "account_holder_name": "Test User",
        "account_type": "savings",
        "first_seen_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_seen_at": datetime(2024, 6, 30, tzinfo=timezone.utc),
        "confidence_score": Decimal("0.9500"),
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_transaction(**overrides):
    defaults = {
        "id": "txn-001",
        "account_id": "acct-001",
        "parser_run_id": "run-001",
        "transaction_datetime": datetime(2024, 3, 15, 10, 0, tzinfo=timezone.utc),
        "posted_date": date(2024, 3, 15),
        "amount": Decimal("50000.00"),
        "direction": "OUT",
        "description_raw": "Transfer to 9876543210",
        "description_normalized": "transfer",
        "reference_no": "REF-001",
        "transaction_type": "OUT_TRANSFER",
        "counterparty_account_normalized": "9876543210",
        "counterparty_name_raw": "Counterparty A",
        "counterparty_name_normalized": "counterparty a",
        "parse_confidence": Decimal("0.8500"),
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_entity(**overrides):
    defaults = {
        "id": "ent-001",
        "entity_type": "PERSON",
        "full_name": "Test Entity",
        "normalized_name": "test entity",
        "alias_json": ["TE", "Test E."],
        "identifier_value": "1234567890123",
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ── Health endpoint ─────────────────────────────────────────────────────


def test_spni_health_returns_ok():
    response = client.get("/api/spni/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert "db_ready" in payload


def test_spni_health_includes_version():
    response = client.get("/api/spni/health")
    payload = response.json()
    assert payload["version"] == "4.0.0"


# ── Runs endpoint ───────────────────────────────────────────────────────


def test_spni_runs_returns_items_key():
    with patch("routers.spni.list_completed_runs", return_value={"items": [], "total": 0}):
        response = client.get("/api/spni/runs")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload


def test_spni_runs_passes_pagination():
    with patch("routers.spni.list_completed_runs", return_value={"items": [], "total": 0}) as mock_fn:
        client.get("/api/spni/runs?limit=10&offset=5")
    _, kwargs = mock_fn.call_args
    assert kwargs.get("limit") == 10 or mock_fn.call_args[0][1] == 10


# ── Preview endpoint ────────────────────────────────────────────────────


def test_spni_preview_404_for_nonexistent_run():
    with patch("routers.spni.get_run_preview", return_value=None):
        response = client.get("/api/spni/runs/nonexistent/preview")
    assert response.status_code == 404


def test_spni_preview_returns_expected_shape():
    preview_data = {
        "run_id": "run-001",
        "file_name": "statement.xlsx",
        "bank": "scb",
        "status": "done",
        "account_count": 2,
        "transaction_count": 150,
        "entity_count": 3,
        "date_range": {"from": "2024-01-01T00:00:00+00:00", "to": "2024-06-30T00:00:00+00:00"},
        "accounts": [
            {"id": "acct-001", "name": "Test", "number": "1234567890", "bank": "SCB", "transaction_count": 100},
        ],
    }
    with patch("routers.spni.get_run_preview", return_value=preview_data):
        response = client.get("/api/spni/runs/run-001/preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-001"
    assert payload["account_count"] == 2
    assert payload["transaction_count"] == 150
    assert payload["entity_count"] == 3
    assert "date_range" in payload
    assert len(payload["accounts"]) == 1


# ── Export endpoint ─────────────────────────────────────────────────────


def test_spni_export_requires_run_id():
    response = client.get("/api/spni/export")
    assert response.status_code == 400


def test_spni_export_returns_expected_shape():
    export_result = {
        "meta": {
            "exported_at": "2024-06-01T00:00:00",
            "source": "bsie",
            "version": "4.0.0",
            "run_id": "run-001",
            "total_accounts": 1,
            "total_transactions": 2,
            "total_entities": 1,
            "limit": 5000,
            "offset": 0,
        },
        "accounts": [
            {
                "id": "acct-001",
                "normalized_account_number": "1234567890",
                "bank_code": "scb",
                "bank_name": "SCB",
                "account_holder_name": "Test",
                "account_type": "savings",
                "confidence_score": 0.95,
                "first_seen_at": "2024-01-01T00:00:00+00:00",
                "last_seen_at": "2024-06-30T00:00:00+00:00",
            }
        ],
        "transactions": [
            {
                "id": "txn-001",
                "account_id": "acct-001",
                "from_account": "1234567890",
                "to_account": "9876543210",
                "amount": 50000.0,
                "direction": "OUT",
                "transaction_datetime": "2024-03-15T10:00:00+00:00",
                "posted_date": "2024-03-15",
                "description": "Transfer",
                "reference_no": "REF-001",
                "transaction_type": "OUT_TRANSFER",
                "counterparty_name": "Counterparty A",
                "parse_confidence": 0.85,
            }
        ],
        "entities": [
            {
                "id": "ent-001",
                "entity_type": "PERSON",
                "full_name": "Test Entity",
                "normalized_name": "test entity",
                "aliases": ["TE"],
                "identifier_value": "1234567890123",
            }
        ],
    }
    with patch("routers.spni.export_data", return_value=export_result):
        response = client.get("/api/spni/export?run_id=run-001")

    assert response.status_code == 200
    payload = response.json()
    assert "meta" in payload
    assert "accounts" in payload
    assert "transactions" in payload
    assert "entities" in payload
    assert payload["meta"]["source"] == "bsie"
    assert len(payload["accounts"]) == 1
    assert len(payload["transactions"]) == 1
    assert len(payload["entities"]) == 1


def test_spni_export_passes_filters():
    with patch("routers.spni.export_data", return_value={"meta": {}, "accounts": [], "transactions": [], "entities": []}) as mock_fn:
        client.get("/api/spni/export?run_id=run-001&accounts=1111,2222&date_from=2024-01-01T00:00:00&amount_min=100")

    call_kwargs = mock_fn.call_args.kwargs
    assert call_kwargs["run_id"] == "run-001"
    assert call_kwargs["account_filter"] == ["1111", "2222"]
    assert call_kwargs["date_from"] == datetime(2024, 1, 1)
    assert call_kwargs["amount_min"] == 100.0


def test_spni_export_rejects_invalid_date():
    response = client.get("/api/spni/export?run_id=run-001&date_from=not-a-date")
    assert response.status_code == 422  # FastAPI validation


def test_spni_export_rejects_limit_over_max():
    response = client.get("/api/spni/export?run_id=run-001&limit=99999")
    assert response.status_code == 422  # Query(le=10000) rejects


# ── Serialization unit tests ────────────────────────────────────────────


def test_serialize_account():
    from services.spni_service import _serialize_account

    acct = _make_account()
    result = _serialize_account(acct)

    assert result["id"] == "acct-001"
    assert result["normalized_account_number"] == "1234567890"
    assert result["bank_code"] == "scb"
    assert result["confidence_score"] == 0.95
    assert result["first_seen_at"] is not None


def test_serialize_transaction_out_direction():
    from services.spni_service import _serialize_transaction

    tx = _make_transaction(direction="OUT")
    result = _serialize_transaction(tx, subject_account_number="1234567890")

    assert result["from_account"] == "1234567890"
    assert result["to_account"] == "9876543210"
    assert result["amount"] == 50000.0
    assert result["direction"] == "OUT"


def test_serialize_transaction_in_direction():
    from services.spni_service import _serialize_transaction

    tx = _make_transaction(direction="IN", counterparty_account_normalized="5555555555")
    result = _serialize_transaction(tx, subject_account_number="1234567890")

    assert result["from_account"] == "5555555555"
    assert result["to_account"] == "1234567890"
    assert result["direction"] == "IN"


def test_serialize_account_null_confidence():
    from services.spni_service import _serialize_account

    acct = _make_account(confidence_score=None)
    result = _serialize_account(acct)
    assert result["confidence_score"] == 0.0


def test_serialize_entity():
    from services.spni_service import _serialize_entity

    ent = _make_entity()
    result = _serialize_entity(ent)

    assert result["id"] == "ent-001"
    assert result["entity_type"] == "PERSON"
    assert result["aliases"] == ["TE", "Test E."]
    assert result["identifier_value"] == "1234567890123"
