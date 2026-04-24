from scripts.benchmark_mapping_models import FIXTURES, build_markdown, parse_models, score_mapping, summarize_runs


def test_fixtures_cover_supported_bank_keys_with_unique_ids():
    fixture_ids = [fixture["id"] for fixture in FIXTURES]
    banks = {fixture["bank"] for fixture in FIXTURES}

    assert len(fixture_ids) == len(set(fixture_ids))
    assert banks == {"scb", "kbank", "bbl", "ktb", "bay", "ttb", "gsb", "baac"}


def test_parse_models_trims_and_rejects_empty_values():
    assert parse_models(" gemma4:26b, gemma4:e4b ,, ") == ["gemma4:26b", "gemma4:e4b"]

    try:
        parse_models(" , ")
    except ValueError as exc:
        assert "At least one model" in str(exc)
    else:
        raise AssertionError("empty model list should be rejected")


def test_score_mapping_reports_misses():
    result = score_mapping(
        {"date": "วันที่", "amount": "ยอด", "balance": None},
        {"date": "วันที่", "amount": "จำนวนเงิน", "balance": "คงเหลือ"},
    )

    assert result["correct"] == 1
    assert result["total"] == 3
    assert result["score"] == 0.3333
    assert [item["field"] for item in result["misses"]] == ["amount", "balance"]


def test_summarize_runs_and_markdown_output():
    fixtures = [
        {
            "fixture": "a",
            "text": {"correct": 2, "total": 3, "duration_ms": 100, "status": "ok", "validation_ok": True, "misses": []},
            "vision": {"correct": 1, "total": 3, "duration_ms": 200, "status": "ok", "validation_ok": False, "misses": []},
        },
        {
            "fixture": "b",
            "text": {"correct": 3, "total": 3, "duration_ms": 300, "status": "ok", "validation_ok": True, "misses": []},
            "vision": {"correct": 2, "total": 3, "duration_ms": 400, "status": "ok", "validation_ok": True, "misses": []},
        },
    ]

    assert summarize_runs(fixtures, "text") == {
        "score": 0.8333,
        "correct": 5,
        "total": 6,
        "average_duration_ms": 200.0,
    }

    markdown = build_markdown({
        "generated_at": "2026-04-24T00:00:00+00:00",
        "local_only": True,
        "mode": "both",
        "models": ["gemma4:26b"],
        "fixtures": [{"id": "a"}, {"id": "b"}],
        "results": [
            {
                "model": "gemma4:26b",
                "fixtures": fixtures,
                "text_summary": summarize_runs(fixtures, "text"),
                "vision_summary": summarize_runs(fixtures, "vision"),
            }
        ],
    })

    assert "# Mapping Model Benchmark" in markdown
    assert "`gemma4:26b`" in markdown
    assert "5/6" in markdown
