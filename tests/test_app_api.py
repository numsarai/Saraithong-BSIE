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
