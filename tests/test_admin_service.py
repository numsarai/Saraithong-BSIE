from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.legacy_models import Job
from persistence.models import Account, AdminSetting, AuditLog, FileRecord, ParserRun
from services.admin_service import (
    RESET_CONFIRMATION_TEXT,
    RESTORE_CONFIRMATION_TEXT,
    create_database_backup,
    get_backup_settings,
    get_database_backup_preview,
    list_database_backups,
    maybe_run_scheduled_backup,
    reset_database,
    restore_database,
    update_backup_settings,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-service.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_sample_data(engine) -> None:
    with Session(engine) as session:
        file_row = FileRecord(
            id="file-1",
            original_filename="sample.xlsx",
            stored_path="/tmp/sample.xlsx",
            file_hash_sha256="abc123",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size_bytes=128,
            uploaded_by="tester",
            uploaded_at=utcnow(),
            import_status="uploaded",
        )
        account_row = Account(
            id="acct-1",
            bank_name="SCB",
            bank_code="SCB",
            raw_account_number="1234567890",
            normalized_account_number="1234567890",
            display_account_number="123-4-56789-0",
            account_holder_name="Admin Service Tester",
        )
        parser_run = ParserRun(
            id="run-1",
            file_id="file-1",
            parser_version="test",
            mapping_profile_version="v1",
            status="done",
            bank_detected="scb",
            started_at=utcnow(),
            finished_at=utcnow(),
        )
        job = Job(job_id="job-1", status="done", account="1234567890")
        session.add_all([file_row, account_row, parser_run, job])
        session.commit()


def test_backup_reset_restore_round_trip(tmp_path: Path):
    engine = _make_engine(tmp_path)
    backup_dir = tmp_path / "backups"
    _seed_sample_data(engine)

    backup = create_database_backup(
        operator="tester",
        note="round-trip backup",
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert (backup_dir / backup["filename"]).exists()

    items = list_database_backups(backup_dir=backup_dir)
    assert items and items[0]["filename"] == backup["filename"]

    reset_result = reset_database(
        confirm_text=RESET_CONFIRMATION_TEXT,
        operator="tester",
        note="round-trip reset",
        create_pre_reset_backup=False,
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert reset_result["table_counts"]["files"] == 0
    assert reset_result["table_counts"]["accounts"] == 0

    restore_result = restore_database(
        backup_filename=backup["filename"],
        confirm_text=RESTORE_CONFIRMATION_TEXT,
        operator="tester",
        note="round-trip restore",
        create_pre_restore_backup=False,
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert restore_result["table_counts"]["files"] == 1
    assert restore_result["table_counts"]["accounts"] == 1

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(FileRecord)) == 1
        assert session.scalar(select(func.count()).select_from(Account)) == 1
        assert session.scalar(select(func.count()).select_from(ParserRun)) == 1
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_reset_database_rejects_wrong_confirmation(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_sample_data(engine)

    try:
        reset_database(
            confirm_text="RESET",
            operator="tester",
            create_pre_reset_backup=False,
            bind_engine=engine,
            backup_dir=tmp_path / "backups",
        )
    except ValueError as exc:
        assert 'RESET BSIE DATABASE' in str(exc)
    else:
        raise AssertionError("reset_database should require the full confirmation phrase")


def test_backup_preview_and_scheduler(tmp_path: Path):
    engine = _make_engine(tmp_path)
    backup_dir = tmp_path / "backups"
    _seed_sample_data(engine)

    scheduled = maybe_run_scheduled_backup(
        interval_hours=24,
        operator="system",
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert scheduled is not None

    preview = get_database_backup_preview(
        scheduled["filename"],
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert preview["filename"] == scheduled["filename"]
    assert preview["backup_table_counts"]["files"] == 1
    assert preview["current_table_counts"]["files"] == 1
    assert preview["delta_table_counts"]["files"] == 0

    skipped = maybe_run_scheduled_backup(
        operator="system",
        bind_engine=engine,
        backup_dir=backup_dir,
    )
    assert skipped is None


def test_backup_settings_round_trip(tmp_path: Path):
    engine = _make_engine(tmp_path)

    defaults = get_backup_settings(bind_engine=engine)
    assert defaults["enabled"] is False

    updated = update_backup_settings(
        enabled=True,
        interval_hours=6,
        backup_format="json",
        retention_enabled=True,
        retain_count=5,
        updated_by="tester",
        bind_engine=engine,
    )
    assert updated["enabled"] is True
    assert updated["interval_hours"] == 6
    assert updated["backup_format"] == "json"
    assert updated["retention_enabled"] is True
    assert updated["retain_count"] == 5
    assert updated["source"] == "database"

    with Session(engine) as session:
        row = session.get(AdminSetting, "database_backup")
        assert row is not None
        assert row.updated_by == "tester"


def test_postgres_dump_backup_and_restore_uses_system_tools(tmp_path: Path):
    engine = _make_engine(tmp_path)
    engine.dialect.name = "postgresql"  # type: ignore[attr-defined]
    backup_dir = tmp_path / "backups"
    _seed_sample_data(engine)

    def fake_run(cmd, check, env, capture_output, text):
        if "pg_dump" in cmd[0]:
            output_flag = next(part for part in cmd if part.startswith("--file="))
            Path(output_flag.split("=", 1)[1]).write_bytes(b"fake dump")
        elif "pg_restore" in cmd[0]:
            assert "--exit-on-error" in cmd
        return None

    with (
        patch("services.admin_service.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
        patch("services.admin_service.subprocess.run", side_effect=fake_run) as run_mock,
    ):
        backup = create_database_backup(
            operator="tester",
            note="pg dump",
            backup_format="pg_dump",
            bind_engine=engine,
            backup_dir=backup_dir,
        )
        assert backup["backup_format"] == "pg_dump"
        assert (backup_dir / backup["filename"]).exists()
        manifest = backup_dir / f"{backup['filename']}.manifest.json"
        assert manifest.exists()

        restore_database(
            backup_filename=backup["filename"],
            confirm_text=RESTORE_CONFIRMATION_TEXT,
            operator="tester",
            note="pg restore",
            create_pre_restore_backup=False,
            bind_engine=engine,
            backup_dir=backup_dir,
        )

        commands = [call.args[0][0] for call in run_mock.call_args_list]
        assert "/usr/bin/pg_dump" in commands
        assert "/usr/bin/pg_restore" in commands


def test_backup_retention_prunes_old_files(tmp_path: Path):
    engine = _make_engine(tmp_path)
    backup_dir = tmp_path / "backups"
    _seed_sample_data(engine)
    update_backup_settings(
        enabled=True,
        interval_hours=24,
        backup_format="json",
        retention_enabled=True,
        retain_count=2,
        updated_by="tester",
        bind_engine=engine,
    )

    first = create_database_backup(operator="tester", note="one", bind_engine=engine, backup_dir=backup_dir)
    second = create_database_backup(operator="tester", note="two", bind_engine=engine, backup_dir=backup_dir)
    third = create_database_backup(operator="tester", note="three", bind_engine=engine, backup_dir=backup_dir)

    items = list_database_backups(backup_dir=backup_dir)
    filenames = [item["filename"] for item in items]
    assert third["filename"] in filenames
    assert second["filename"] in filenames
    assert first["filename"] not in filenames
    assert third["pruned_backups"]
