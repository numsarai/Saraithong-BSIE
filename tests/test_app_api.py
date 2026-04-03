"""Focused API regression tests for app.py."""
from contextlib import contextmanager
from io import BytesIO
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import app


client = TestClient(app.app)


@contextmanager
def _fake_db_session():
    class DummySession:
        def commit(self):
            return None

    yield DummySession()


def test_favicon_route_serves_built_asset(tmp_path, monkeypatch):
    """The root favicon path should serve a built favicon when one is available."""
    react_dist = tmp_path / "dist"
    react_dist.mkdir()
    (react_dist / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' />", encoding="utf-8")
    monkeypatch.setattr(app, "_REACT_DIST", react_dist)

    response = client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text


def test_bank_logo_route_serves_svg_badge():
    response = client.get("/api/bank-logos/scb.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "Siam Commercial Bank" in response.text


def test_banks_endpoint_includes_logo_metadata():
    response = client.get("/api/banks")

    assert response.status_code == 200
    payload = response.json()
    scb = next(item for item in payload if item["key"] == "scb")
    assert scb["logo_url"] == "/api/bank-logos/scb.svg"
    assert scb["has_template"] is True
    assert scb["template_status"] == "template_ready"


def test_bank_logo_catalog_includes_future_thai_banks():
    response = client.get("/api/bank-logo-catalog")

    assert response.status_code == 200
    payload = response.json()
    baac = next(item for item in payload if item["key"] == "baac")
    assert baac["logo_url"] == "/api/bank-logos/baac.svg"
    assert baac["has_template"] is False
    assert baac["template_status"] == "logo_ready"


def test_bank_create_allows_prepared_bank_key_without_builtin_template(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    builtin_dir = tmp_path / "builtin"
    config_dir.mkdir()
    builtin_dir.mkdir()
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "BUILTIN_CONFIG_DIR", builtin_dir)

    response = client.post(
        "/api/banks",
        json={
            "key": "baac",
            "bank_name": "BAAC",
            "sheet_index": 0,
            "header_row": 1,
            "format_type": "standard",
            "amount_mode": "signed",
            "column_mapping": {"date": ["วันที่"]},
        },
    )

    assert response.status_code == 200
    assert (config_dir / "baac.json").exists()
    assert response.json()["logo"]["key"] == "baac"


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
        account_number="",
    )
    reapply.assert_called_once_with("TXN-000001", account_number="")


def test_remove_override_endpoint_passes_account_scope():
    with patch.object(app, "remove_override", return_value=True) as remove_override:
        response = client.delete("/api/override/TXN-000001", params={"account_number": "1234567890"})

    assert response.status_code == 200
    assert response.json()["status"] == "removed"
    remove_override.assert_called_once_with("TXN-000001", account_number="1234567890")


def test_remove_override_endpoint_uses_operator_for_audit():
    with (
        patch.object(app, "remove_override", return_value=True),
        patch.object(app, "get_db_session", _fake_db_session),
        patch.object(app, "log_audit") as log_audit,
    ):
        response = client.delete(
            "/api/override/TXN-000001",
            params={"account_number": "1234567890", "operator": "Case Reviewer"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "removed"
    assert log_audit.call_args.kwargs["changed_by"] == "Case Reviewer"


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


def test_bulk_download_endpoint_uses_requested_download_name(tmp_path):
    run_dir = tmp_path / "bulk_runs" / "20260330_030000"
    run_dir.mkdir(parents=True)
    target = run_dir / "bulk_summary.csv"
    target.write_text("file,status\nsample.xlsx,processed\n", encoding="utf-8")

    with patch.object(app, "OUTPUT_DIR", tmp_path):
        response = client.get(
            "/api/download-bulk/20260330_030000/bulk_summary.csv",
            params={"download_name": "bsie_bulk_20260330_030000.csv"},
        )

    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert "bsie_bulk_20260330_030000.csv" in response.headers["content-disposition"]


def test_results_endpoint_includes_entities_and_links(tmp_path):
    account_dir = tmp_path / "1234567890"
    processed_dir = account_dir / "processed"
    processed_dir.mkdir(parents=True)
    (processed_dir / "transactions.csv").write_text("transaction_id,amount\nTXN-1,100\n", encoding="utf-8")
    (processed_dir / "entities.csv").write_text("entity_id,name\nE1,Alice\n", encoding="utf-8")
    (processed_dir / "links.csv").write_text("transaction_id,from_account,to_account\nTXN-1,111,222\n", encoding="utf-8")
    (account_dir / "meta.json").write_text(json.dumps({"bank": "SCB"}), encoding="utf-8")

    with patch.object(app, "OUTPUT_DIR", tmp_path):
        response = client.get("/api/results/1234567890")

    assert response.status_code == 200
    payload = response.json()
    assert payload["entities"][0]["entity_id"] == "E1"
    assert payload["links"][0]["transaction_id"] == "TXN-1"


def test_bulk_analytics_endpoint_returns_saved_artifact(tmp_path):
    run_dir = tmp_path / "bulk_runs" / "20260330_030000"
    run_dir.mkdir(parents=True)
    (run_dir / "case_analytics.json").write_text(
        json.dumps({"run_id": "20260330_030000", "overview": {"flagged_accounts": 1}}),
        encoding="utf-8",
    )

    with patch.object(app, "OUTPUT_DIR", tmp_path):
        response = client.get("/api/bulk/20260330_030000/analytics")

    assert response.status_code == 200
    assert response.json()["overview"]["flagged_accounts"] == 1


def test_graph_analysis_endpoint_returns_service_payload():
    with patch.object(app, "get_graph_analysis", return_value={"overview": {"business_node_count": 4}, "top_nodes_by_degree": []}) as mock_graph:
        response = client.get("/api/graph-analysis", params={"parser_run_id": "RUN-1"})

    assert response.status_code == 200
    assert response.json()["overview"]["business_node_count"] == 4
    mock_graph.assert_called_once()


def test_graph_nodes_endpoint_returns_items():
    with patch.object(app, "list_graph_nodes", return_value=[{"node_id": "ACCOUNT:1111111111"}]) as mock_nodes:
        response = client.get("/api/graph/nodes", params={"parser_run_id": "RUN-1"})

    assert response.status_code == 200
    assert response.json()["items"][0]["node_id"] == "ACCOUNT:1111111111"
    assert response.json()["meta"]["returned_count"] == 1
    mock_nodes.assert_called_once()


def test_graph_findings_endpoint_returns_items():
    with patch.object(app, "list_graph_findings", return_value=[{"finding_id": "FINDING:1", "severity": "high"}]) as mock_findings:
        response = client.get("/api/graph/findings", params={"parser_run_id": "RUN-1", "severity": "high"})

    assert response.status_code == 200
    assert response.json()["items"][0]["finding_id"] == "FINDING:1"
    assert response.json()["meta"]["severity"] == "high"
    mock_findings.assert_called_once()


def test_graph_neighborhood_endpoint_returns_payload():
    payload = {
        "center_node_id": "ACCOUNT:1111111111",
        "nodes": [],
        "edges": [],
        "suspicious_node_ids": [],
        "findings": [],
        "findings_by_node": {},
        "query_meta": {"effective_limit": 5000},
        "graph_meta": {"visible_node_count": 0, "requested_max_nodes": 14},
    }
    with patch.object(app, "get_graph_neighborhood", return_value=payload) as mock_neighborhood:
        response = client.get(
            "/api/graph/neighborhood/ACCOUNT:1111111111",
            params={"parser_run_id": "RUN-1", "max_nodes": 12, "max_edges": 20},
        )

    assert response.status_code == 200
    assert response.json()["center_node_id"] == "ACCOUNT:1111111111"
    assert response.json()["graph_meta"]["requested_max_nodes"] == 14
    mock_neighborhood.assert_called_once()


def test_graph_neo4j_status_endpoint_returns_payload():
    with patch.object(app, "get_neo4j_status", return_value={"enabled": False, "configured": False, "driver_available": False}) as mock_status:
        response = client.get("/api/graph/neo4j-status")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    mock_status.assert_called_once()


def test_graph_neo4j_sync_endpoint_returns_payload():
    with patch.object(app, "sync_graph_to_neo4j", return_value={"status": "ok", "node_count": 2}) as mock_sync:
        response = client.post("/api/graph/neo4j-sync", json={"include_findings": True, "limit": 100, "filters": {"parser_run_id": "RUN-1"}})

    assert response.status_code == 200
    assert response.json()["node_count"] == 2
    mock_sync.assert_called_once()


def test_upload_accepts_ofx_and_returns_identity_guess(tmp_path):
    ofx_content = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BANKID>SCB
<ACCTID>1234567890
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260301090000
<TRNAMT>100.00
<FITID>1
<NAME>Deposit
<MEMO>Cash deposit
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    response = client.post(
        "/api/upload",
        files={"file": ("sample.ofx", BytesIO(ofx_content.encode("utf-8")), "application/x-ofx")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_bank"]["config_key"] == "ofx"
    assert payload["account_guess"] == "1234567890"
    assert payload["sheet_name"] == "OFX"


def test_upload_uses_uploaded_by_form_field(tmp_path):
    stored_path = tmp_path / "original.ofx"
    stored_path.write_text("stub", encoding="utf-8")

    with (
        patch.object(
            app,
            "persist_upload",
            return_value={
                "file_id": "FILE-1",
                "stored_path": str(stored_path),
                "duplicate_file_status": "unique",
                "prior_ingestions": [],
            },
        ) as persist_upload,
        patch.object(app, "parse_ofx_file", return_value=app.pd.DataFrame([{"AMOUNT": "100.00"}])),
        patch.object(app, "infer_identity_from_ofx", return_value={"account": "1234567890", "name": "Case Name"}),
    ):
        response = client.post(
            "/api/upload",
            data={"uploaded_by": "Case Reviewer"},
            files={"file": ("sample.ofx", BytesIO(b"OFXHEADER:100"), "application/x-ofx")},
        )

    assert response.status_code == 200
    assert persist_upload.call_args.kwargs["uploaded_by"] == "Case Reviewer"


def test_process_folder_endpoint_passes_operator():
    with patch.object(app, "process_folder", return_value={"total_files": 0, "processed_files": 0, "skipped_files": 0, "error_files": 0, "files": []}) as process_folder:
        response = client.post(
            "/api/process-folder",
            json={"folder_path": "/cases/demo", "recursive": True, "operator": "Case Reviewer"},
        )

    assert response.status_code == 200
    process_folder.assert_called_once_with("/cases/demo", recursive=True, operator="Case Reviewer")


def test_upload_repairs_stale_profile_mapping_for_debit_credit_layout(tmp_path):
    workbook = tmp_path / "sample.xlsx"
    import pandas as pd

    pd.DataFrame(
        [
            ["วันที่", "รายการ", "ถอนเงิน", "เงินฝาก", "จำนวนเงินคงเหลือ"],
            ["2026-03-01", "โอน", "100", "", "900"],
        ]
    ).to_excel(workbook, header=False, index=False)

    fake_sheet_pick = {"header_row": 0, "sheet_name": "Sheet1"}
    fake_bank = {"bank": "SCB", "config_key": "scb", "key": "scb", "confidence": 1.0, "ambiguous": False}
    fake_columns = {
        "suggested_mapping": {
            "date": "วันที่",
            "description": "รายการ",
            "debit": "ถอนเงิน",
            "credit": "เงินฝาก",
            "amount": None,
            "balance": "จำนวนเงินคงเหลือ",
        },
        "confidence_scores": {"date": 1.0},
        "all_columns": ["วันที่", "รายการ", "ถอนเงิน", "เงินฝาก", "จำนวนเงินคงเหลือ"],
        "unmatched_columns": [],
        "required_found": True,
    }
    stale_profile = {
        "profile_id": "P1",
        "bank": "SCB",
        "usage_count": 5,
        "mapping": {
            "date": "วันที่",
            "description": "รายการ",
            "debit": "ถอนเงิน",
            "credit": "เงินฝาก",
            "amount": "จำนวนเงินคงเหลือ",
            "balance": None,
        },
    }

    with (
        patch.object(app, "find_best_sheet_and_header", return_value=fake_sheet_pick),
        patch.object(app, "detect_bank", return_value=fake_bank),
        patch.object(app, "detect_columns", return_value=fake_columns),
        patch.object(app, "find_matching_profile", return_value=stale_profile),
        patch.object(app, "find_matching_bank_fingerprint", return_value=None),
    ):
        with workbook.open("rb") as fh:
            response = client.post(
                "/api/upload",
                files={"file": ("sample.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_mapping"]["amount"] is None
    assert payload["suggested_mapping"]["balance"] == "จำนวนเงินคงเหลือ"


def test_account_remembered_name_endpoint_returns_match():
    with patch.object(app, "best_known_account_holder_name", return_value="Persisted Name") as lookup_name:
        response = client.get(
            "/api/accounts/remembered-name",
            params={"account": "123-456-7890", "bank_key": "scb"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "bank_key": "scb",
        "account": "123-456-7890",
        "normalized_account_number": "1234567890",
        "remembered_name": "Persisted Name",
        "matched": True,
    }
    lookup_name.assert_called_once()


def test_account_remembered_name_endpoint_returns_empty_payload_for_invalid_account():
    with patch.object(app, "best_known_account_holder_name") as lookup_name:
        response = client.get(
            "/api/accounts/remembered-name",
            params={"account": "abc123", "bank_key": "scb"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "bank_key": "scb",
        "account": "abc123",
        "normalized_account_number": "",
        "remembered_name": "",
        "matched": False,
    }
    lookup_name.assert_not_called()


def test_mapping_confirm_endpoint_weights_corrected_feedback_from_override_context():
    payload = {
        "bank": "ktb",
        "mapping": {
            "date": "วันที่",
            "description": "รายละเอียดใหม่",
        },
        "columns": ["วันที่", "รายละเอียด", "รายละเอียดใหม่"],
        "header_row": 1,
        "sheet_name": "Sheet1",
        "reviewer": "reviewer.one",
        "detected_bank": {"key": "scb", "bank": "SCB"},
        "suggested_mapping": {
            "date": "วันที่",
            "description": "รายละเอียด",
        },
    }

    with (
        patch("core.mapping_memory.save_profile", return_value={"profile_id": "PROFILE-1"}) as save_profile,
        patch.object(app, "save_bank_fingerprint", return_value={"fingerprint_id": "FINGERPRINT-1"}) as save_bank_fingerprint,
        patch.object(app, "record_learning_feedback") as record_learning_feedback,
        patch.object(app, "get_db_session", side_effect=_fake_db_session),
    ):
        response = client.post("/api/mapping/confirm", json=payload)

    assert response.status_code == 200
    assert response.json()["bank_feedback"] == "corrected"
    assert response.json()["mapping_feedback"] == "corrected"
    assert response.json()["feedback_mode"] == "corrected"
    assert "correction" in response.json()["message"].lower()
    assert response.json()["learning_feedback_count"] == 2
    save_profile.assert_called_once_with(
        "ktb",
        ["วันที่", "รายละเอียด", "รายละเอียดใหม่"],
        {"date": "วันที่", "description": "รายละเอียดใหม่"},
        usage_increment=2,
    )
    save_bank_fingerprint.assert_called_once_with(
        "ktb",
        ["วันที่", "รายละเอียด", "รายละเอียดใหม่"],
        header_row=1,
        sheet_name="Sheet1",
        usage_increment=2,
    )
    assert record_learning_feedback.call_count == 2
    mapping_call = record_learning_feedback.call_args_list[0].kwargs
    bank_call = record_learning_feedback.call_args_list[1].kwargs
    assert mapping_call["learning_domain"] == "mapping_memory"
    assert mapping_call["feedback_status"] == "corrected"
    assert mapping_call["changed_by"] == "reviewer.one"
    assert bank_call["learning_domain"] == "bank_memory"
    assert bank_call["feedback_status"] == "corrected"
    assert bank_call["changed_by"] == "reviewer.one"


def test_mapping_confirm_endpoint_keeps_confirmed_feedback_at_normal_weight():
    payload = {
        "bank": "scb",
        "mapping": {
            "date": "วันที่",
            "description": "รายละเอียด",
        },
        "columns": ["วันที่", "รายละเอียด"],
        "detected_bank": {"config_key": "scb", "bank": "SCB"},
        "suggested_mapping": {
            "date": "วันที่",
            "description": "รายละเอียด",
        },
    }

    with (
        patch("core.mapping_memory.save_profile", return_value={"profile_id": "PROFILE-2"}) as save_profile,
        patch.object(app, "save_bank_fingerprint", return_value={"fingerprint_id": "FINGERPRINT-2"}) as save_bank_fingerprint,
        patch.object(app, "record_learning_feedback") as record_learning_feedback,
        patch.object(app, "get_db_session", side_effect=_fake_db_session),
    ):
        response = client.post("/api/mapping/confirm", json=payload)

    assert response.status_code == 200
    assert response.json()["bank_feedback"] == "confirmed"
    assert response.json()["mapping_feedback"] == "confirmed"
    assert response.json()["feedback_mode"] == "confirmed"
    assert response.json()["learning_feedback_count"] == 2
    save_profile.assert_called_once_with(
        "scb",
        ["วันที่", "รายละเอียด"],
        {"date": "วันที่", "description": "รายละเอียด"},
        usage_increment=1,
    )
    save_bank_fingerprint.assert_called_once_with(
        "scb",
        ["วันที่", "รายละเอียด"],
        header_row=0,
        sheet_name="",
        usage_increment=1,
    )
    assert record_learning_feedback.call_count == 2


def test_learning_feedback_endpoint_uses_dedicated_query_helper():
    with patch.object(app, "list_learning_feedback_logs", return_value=[{"id": "LF-1"}]) as list_learning_feedback_logs:
        response = client.get("/api/learning-feedback", params={"object_id": "mapping_profile:PROFILE-1", "limit": 50, "offset": 10})

    assert response.status_code == 200
    assert response.json()["items"] == [{"id": "LF-1"}]
    list_learning_feedback_logs.assert_called_once()


def test_db_status_endpoint_reports_investigation_schema():
    response = client.get("/api/admin/db-status")

    assert response.status_code == 200
    payload = response.json()
    assert "database_backend" in payload
    assert "database_runtime_source" in payload
    assert "tables" in payload
    assert "key_record_counts" in payload


def test_admin_backup_endpoints_round_trip(tmp_path):
    with (
        patch.object(app, "BACKUPS_DIR", tmp_path),
        patch("services.admin_service.BACKUPS_DIR", tmp_path),
    ):
        create_response = client.post("/api/admin/backup", json={"operator": "tester", "note": "api backup"})

        assert create_response.status_code == 200
        created = create_response.json()
        assert (tmp_path / created["filename"]).exists()

        list_response = client.get("/api/admin/backups")
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["items"]
        assert payload["items"][0]["filename"] == created["filename"]

        preview_response = client.get(f"/api/admin/backups/{created['filename']}/preview")
        assert preview_response.status_code == 200
        assert preview_response.json()["filename"] == created["filename"]

        download_response = client.get(f"/api/download-backup/{created['filename']}")
        assert download_response.status_code == 200


def test_admin_backup_settings_endpoint_round_trip():
    get_response = client.get("/api/admin/backup-settings")
    assert get_response.status_code == 200

    update_response = client.post(
        "/api/admin/backup-settings",
        json={
            "enabled": True,
            "interval_hours": 12,
            "backup_format": "json",
            "retention_enabled": True,
            "retain_count": 7,
            "updated_by": "tester",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["enabled"] is True
    assert updated["interval_hours"] == 12
    assert updated["backup_format"] == "json"
    assert updated["retention_enabled"] is True
    assert updated["retain_count"] == 7


def test_results_endpoint_returns_rows_and_items_aliases():
    response = client.get("/api/results/7882476275?page=1&page_size=5")
    if response.status_code == 404:
        return
    assert response.status_code == 200
    payload = response.json()
    assert "rows" in payload
    assert "items" in payload
    assert payload["rows"] == payload["items"]
