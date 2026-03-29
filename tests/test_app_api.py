"""Focused API regression tests for app.py."""
from unittest.mock import patch

from fastapi.testclient import TestClient

import app


client = TestClient(app.app)


def test_favicon_route_serves_built_asset():
    """The root favicon path should serve the built frontend asset."""
    response = client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text


def test_override_endpoint_accepts_react_payload_keys():
    """React clients send override_* keys; the API should accept them."""
    with (
        patch.object(app, "add_override", return_value={"transaction_id": "TXN-000001"}) as add_override,
        patch.object(app, "_reapply_overrides_to_csv") as reapply,
    ):
        response = client.post(
            "/api/override",
            json={
                "transaction_id": "TXN-000001",
                "override_from_account": "1234567890",
                "override_to_account": "0987654321",
                "override_reason": "Analyst correction",
                "override_by": "analyst",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    add_override.assert_called_once_with(
        "TXN-000001",
        "1234567890",
        "0987654321",
        "Analyst correction",
        "analyst",
    )
    reapply.assert_called_once_with("TXN-000001")


def test_download_endpoint_uses_requested_download_name(tmp_path):
    account_dir = tmp_path / "1234567890"
    processed_dir = account_dir / "processed"
    processed_dir.mkdir(parents=True)
    target = processed_dir / "transactions.csv"
    target.write_text("id\n1\n", encoding="utf-8")

    with patch.object(app, "OUTPUT_DIR", tmp_path):
        response = client.get(
            "/api/download/1234567890/processed/transactions.csv",
            params={"download_name": "bsie_1234567890_transactions.csv"},
        )

    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert "bsie_1234567890_transactions.csv" in response.headers["content-disposition"]
