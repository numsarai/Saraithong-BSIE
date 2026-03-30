from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pandas as pd

from database import init_db
from persistence.base import get_db_session
from persistence.models import AuditLog, ExportJob, FileRecord, ParserRun, StatementBatch, Transaction
from pipeline.process_account import process_account
from services.export_service import create_export_job, run_export_job
from services.file_ingestion_service import persist_upload
from services.persistence_pipeline_service import create_parser_run
from services.review_service import update_transaction_fields
from services.search_service import search_transactions


def _sample_ofx(account: str, amount: str = "100.00") -> str:
    return f"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKACCTFROM>
<BANKID>SCB
<ACCTID>{account}
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260301090000
<TRNAMT>{amount}
<FITID>1
<NAME>Deposit
<MEMO>Cash deposit
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260301100000
<TRNAMT>-50.00
<FITID>2
<NAME>Transfer
<MEMO>Transfer to 1234567890
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


def test_persist_upload_creates_file_record_and_duplicate_hint():
    init_db()
    unique_account = f"{uuid4().int % 10**10:010d}"
    payload = _sample_ofx(unique_account).encode("utf-8")

    first = persist_upload(content=payload, original_filename="dup-sample.ofx", uploaded_by="tester")
    second = persist_upload(content=payload, original_filename="dup-sample.ofx", uploaded_by="tester")

    assert first["duplicate_file_status"] == "unique"
    assert second["duplicate_file_status"] == "exact_duplicate"

    with get_db_session() as session:
        rows = session.query(FileRecord).filter(FileRecord.file_hash_sha256 == first["file_hash_sha256"]).all()
        assert len(rows) >= 2


def test_ofx_pipeline_persists_parser_run_batch_and_transactions(tmp_path: Path):
    init_db()
    account = "1234500012"
    ofx_path = tmp_path / "persisted.ofx"
    ofx_path.write_text(_sample_ofx(account), encoding="utf-8")

    upload_meta = persist_upload(
        content=ofx_path.read_bytes(),
        original_filename=ofx_path.name,
        uploaded_by="tester",
    )
    parser_run = create_parser_run(
        file_id=upload_meta["file_id"],
        bank_detected="ofx",
        confirmed_mapping={},
        operator="tester",
    )

    process_account(
        input_file=ofx_path,
        subject_account=account,
        subject_name="Persist Tester",
        bank_key="ofx",
        confirmed_mapping={},
        file_id=upload_meta["file_id"],
        parser_run_id=parser_run["parser_run_id"],
        operator="tester",
    )

    with get_db_session() as session:
        run = session.get(ParserRun, parser_run["parser_run_id"])
        assert run is not None
        assert run.status == "done"

        batch = session.query(StatementBatch).filter(StatementBatch.parser_run_id == run.id).one()
        assert batch.transaction_count == 2

        transactions = session.query(Transaction).filter(Transaction.parser_run_id == run.id).all()
        assert len(transactions) == 2
        assert all(tx.lineage_json.get("file_id") == upload_meta["file_id"] for tx in transactions)


def test_transaction_review_and_export_job_create_audit_and_artifacts(tmp_path: Path):
    init_db()
    account = "1234500099"
    ofx_path = tmp_path / "reviewable.ofx"
    ofx_path.write_text(_sample_ofx(account, amount="250.00"), encoding="utf-8")

    upload_meta = persist_upload(
        content=ofx_path.read_bytes(),
        original_filename=ofx_path.name,
        uploaded_by="tester",
    )
    parser_run = create_parser_run(
        file_id=upload_meta["file_id"],
        bank_detected="ofx",
        confirmed_mapping={},
        operator="tester",
    )

    process_account(
        input_file=ofx_path,
        subject_account=account,
        subject_name="Audit Tester",
        bank_key="ofx",
        confirmed_mapping={},
        file_id=upload_meta["file_id"],
        parser_run_id=parser_run["parser_run_id"],
        operator="tester",
    )

    with get_db_session() as session:
        transaction = session.query(Transaction).filter(Transaction.parser_run_id == parser_run["parser_run_id"]).first()
        assert transaction is not None

        update_transaction_fields(
            session,
            transaction_id=transaction.id,
            changes={"transaction_type": "REVIEWED_TRANSFER"},
            reviewer="tester",
            reason="manual correction",
        )
        export_job = create_export_job(session, export_type="transactions", filters={"parser_run_id": parser_run["parser_run_id"]}, created_by="tester")
        run_export_job(session, export_job)
        session.commit()

        audit_rows = session.query(AuditLog).filter(AuditLog.object_type == "transaction", AuditLog.object_id == transaction.id).all()
        assert audit_rows

        stored_job = session.get(ExportJob, export_job.id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.output_path
        assert Path(stored_job.output_path).exists()


def test_graph_export_job_writes_graph_csvs_and_anx(tmp_path: Path):
    init_db()
    account = "1234500088"
    ofx_path = tmp_path / "graphable.ofx"
    ofx_path.write_text(_sample_ofx(account, amount="175.00"), encoding="utf-8")

    upload_meta = persist_upload(
        content=ofx_path.read_bytes(),
        original_filename=ofx_path.name,
        uploaded_by="tester",
    )
    parser_run = create_parser_run(
        file_id=upload_meta["file_id"],
        bank_detected="ofx",
        confirmed_mapping={},
        operator="tester",
    )

    process_account(
        input_file=ofx_path,
        subject_account=account,
        subject_name="Graph Tester",
        bank_key="ofx",
        confirmed_mapping={},
        file_id=upload_meta["file_id"],
        parser_run_id=parser_run["parser_run_id"],
        operator="tester",
    )

    with get_db_session() as session:
        export_job = create_export_job(
            session,
            export_type="graph",
            filters={"parser_run_id": parser_run["parser_run_id"]},
            created_by="tester",
        )
        run_export_job(session, export_job)
        session.commit()

        stored_job = session.get(ExportJob, export_job.id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.summary_json["files"] == [
            "nodes.csv",
            "nodes.json",
            "edges.csv",
            "edges.json",
            "aggregated_edges.csv",
            "aggregated_edges.json",
            "derived_account_edges.csv",
            "derived_account_edges.json",
            "graph_manifest.json",
            "graph_analysis.json",
            "graph_analysis.xlsx",
            "suspicious_findings.csv",
            "suspicious_findings.json",
            "i2_chart.anx",
        ]

        export_dir = Path(stored_job.output_path).parent
        nodes_path = export_dir / "nodes.csv"
        nodes_json_path = export_dir / "nodes.json"
        edges_path = export_dir / "edges.csv"
        edges_json_path = export_dir / "edges.json"
        aggregated_path = export_dir / "aggregated_edges.csv"
        aggregated_json_path = export_dir / "aggregated_edges.json"
        derived_path = export_dir / "derived_account_edges.csv"
        derived_json_path = export_dir / "derived_account_edges.json"
        analysis_json_path = export_dir / "graph_analysis.json"
        analysis_xlsx_path = export_dir / "graph_analysis.xlsx"
        suspicious_csv_path = export_dir / "suspicious_findings.csv"
        suspicious_json_path = export_dir / "suspicious_findings.json"
        anx_path = export_dir / "i2_chart.anx"

        assert nodes_path.exists()
        assert nodes_json_path.exists()
        assert edges_path.exists()
        assert edges_json_path.exists()
        assert aggregated_path.exists()
        assert aggregated_json_path.exists()
        assert derived_path.exists()
        assert derived_json_path.exists()
        assert analysis_json_path.exists()
        assert analysis_xlsx_path.exists()
        assert suspicious_csv_path.exists()
        assert suspicious_json_path.exists()
        assert anx_path.exists()

        nodes_df = pd.read_csv(nodes_path, dtype=str).fillna("")
        edges_df = pd.read_csv(edges_path, dtype=str).fillna("")
        assert "node_type" in nodes_df.columns
        assert "edge_type" in edges_df.columns
        assert set(edges_df["source"]).issubset(set(nodes_df["node_id"]))
        assert set(edges_df["target"]).issubset(set(nodes_df["node_id"]))


def test_search_transactions_supports_normalized_account_number(tmp_path: Path):
    init_db()
    account = "1234500077"
    ofx_path = tmp_path / "searchable.ofx"
    ofx_path.write_text(_sample_ofx(account, amount="300.00"), encoding="utf-8")

    upload_meta = persist_upload(
        content=ofx_path.read_bytes(),
        original_filename=ofx_path.name,
        uploaded_by="tester",
    )
    parser_run = create_parser_run(
        file_id=upload_meta["file_id"],
        bank_detected="ofx",
        confirmed_mapping={},
        operator="tester",
    )

    process_account(
        input_file=ofx_path,
        subject_account=account,
        subject_name="Search Tester",
        bank_key="ofx",
        confirmed_mapping={},
        file_id=upload_meta["file_id"],
        parser_run_id=parser_run["parser_run_id"],
        operator="tester",
    )

    with get_db_session() as session:
        rows = search_transactions(
            session,
            account=account,
            parser_run_id=parser_run["parser_run_id"],
            limit=20,
        )
        assert len(rows) == 2
        assert all(row["account_id"] for row in rows)
