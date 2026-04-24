"""Case tag API regression tests."""

from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app
from persistence.base import Base
from persistence.models import CaseTag, CaseTagLink


client = TestClient(app.app)


def test_case_tags_endpoint_includes_link_counts(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'case_tags.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            CaseTag(
                id="CASE-TAG-1",
                tag="CASE-ALPHA",
                description="Alpha evidence group",
                created_at=datetime(2026, 3, 31, 2, 0, tzinfo=timezone.utc),
            )
        )
        session.add_all(
            [
                CaseTagLink(id="LINK-1", case_tag_id="CASE-TAG-1", object_type="transaction", object_id="TXN-1"),
                CaseTagLink(id="LINK-2", case_tag_id="CASE-TAG-1", object_type="transaction", object_id="TXN-2"),
                CaseTagLink(id="LINK-3", case_tag_id="CASE-TAG-1", object_type="alert", object_id="ALERT-1"),
            ]
        )
        session.commit()

    @contextmanager
    def test_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr("routers.case_tags.get_db_session", test_session)

    response = client.get("/api/case-tags")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "id": "CASE-TAG-1",
            "tag": "CASE-ALPHA",
            "description": "Alpha evidence group",
            "created_at": "2026-03-31T02:00:00",
            "linked_object_count": 3,
            "linked_object_counts": {"alert": 1, "transaction": 2},
        }
    ]
