import json
import logging
from pathlib import Path
from unittest.mock import patch

import tasks


def test_job_handler_filters_uvicorn_access_logs():
    handler = tasks._JobHandler("job-1", flush_every=1)
    ignored = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 10, "GET /api/job", (), None)
    captured = logging.LogRecord("pipeline.process_account", logging.INFO, __file__, 11, "Step 1", (), None)

    handler.emit(ignored)
    runtime = tasks.get_runtime_job("job-1")
    assert runtime is None or runtime["log"] == []

    handler.emit(captured)
    runtime = tasks.get_runtime_job("job-1")
    assert runtime is not None
    assert any("Step 1" in line for line in runtime["log"])


def test_run_pipeline_sync_stores_compact_result_summary(tmp_path, monkeypatch):
    input_file = tmp_path / "source.xlsx"
    input_file.write_bytes(b"fake")

    output_dir = tmp_path / "1111111111"
    processed_dir = output_dir / "processed"
    processed_dir.mkdir(parents=True)
    meta = {
        "bank": "KBANK",
        "report_filename": "subject_report.xlsx",
        "num_transactions": 2,
    }
    (output_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (processed_dir / "transactions.csv").write_text(
        "transaction_id,date,amount\nTXN-1,2026-04-01,100\nTXN-2,2026-04-02,200\n",
        encoding="utf-8-sig",
    )
    (processed_dir / "entities.csv").write_text(
        "entity_id,entity_type,value\nENT-1,person,Alice\n",
        encoding="utf-8-sig",
    )
    (processed_dir / "links.csv").write_text(
        "transaction_id,from_account,to_account\nTXN-1,111,222\n",
        encoding="utf-8-sig",
    )

    import pipeline.process_account as process_account_module

    monkeypatch.setattr(process_account_module, "process_account", lambda **kwargs: output_dir)

    updates: list[dict] = []
    inserted: list[tuple[str, str, dict]] = []

    def _capture_update(job_id: str, **kwargs):
        updates.append({"job_id": job_id, **kwargs})

    def _capture_meta(job_id: str, account_number: str, payload: dict):
        inserted.append((job_id, account_number, payload))

    monkeypatch.setattr(tasks, "db_update_job", _capture_update)
    monkeypatch.setattr(tasks, "insert_job_meta", _capture_meta)

    tasks.run_pipeline_sync(
        job_id="job-123",
        upload_path_str=str(input_file),
        bank_key="kbank",
        account="1883167399",
        name="นาย ศิระ ลิมปนันทพงศ์",
        confirmed_mapping={},
    )

    assert updates[0]["status"] == "running"
    done_update = updates[-1]
    assert done_update["status"] == "done"

    result = json.loads(done_update["result_json"])
    assert result["account"] == "1883167399"
    assert result["output_dir"] == str(output_dir)
    assert result["report_filename"] == "subject_report.xlsx"
    assert result["meta"]["bank"] == "KBANK"
    assert "transactions" not in result
    assert "entities" not in result
    assert "links" not in result

    runtime = tasks.get_runtime_job("job-123")
    assert runtime is not None
    assert runtime["result"]["transactions"][0]["transaction_id"] == "TXN-1"
    assert runtime["result"]["entities"][0]["entity_id"] == "ENT-1"
    assert runtime["result"]["links"][0]["transaction_id"] == "TXN-1"

    assert inserted == [("job-123", "1883167399", meta)]
