import asyncio

from services.mapping_assist_service import suggest_mapping_with_llm


def test_mapping_assist_parses_repairs_and_validates_llm_json(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {
            "model": "qwen2.5:14b",
            "response": """
            ```json
            {
              "mapping": {
                "date": "วันที่",
                "description": "รายการ",
                "debit": "ถอนเงิน",
                "credit": "เงินฝาก",
                "balance": "ยอดคงเหลือ",
                "counterparty_account": "บัญชีปลายทาง",
                "channel": "missing column"
              },
              "confidence": 0.82,
              "reasons": ["debit and credit columns are explicit"],
              "warnings": ["channel was not visible"]
            }
            ```
            """,
        }

    monkeypatch.setattr("services.mapping_assist_service.chat", fake_chat)

    result = asyncio.run(
        suggest_mapping_with_llm(
            bank="scb",
            detected_bank={"key": "scb", "confidence": 0.91},
            columns=["วันที่", "รายการ", "ถอนเงิน", "เงินฝาก", "ยอดคงเหลือ", "บัญชีปลายทาง"],
            sample_rows=[{"วันที่": "2026-03-01", "รายการ": "โอน", "เงินฝาก": "100"}],
            current_mapping={"date": "วันที่", "description": "รายการ", "amount": "ยอดคงเหลือ"},
            sheet_name="Sheet1",
            header_row=0,
        )
    )

    assert result["status"] == "ok"
    assert result["source"] == "local_llm_mapping_assist"
    assert result["suggestion_only"] is True
    assert result["auto_pass_eligible"] is False
    assert result["model"] == "qwen2.5:14b"
    assert result["confidence"] == 0.82
    assert result["mapping"]["amount"] is None
    assert result["mapping"]["debit"] == "ถอนเงิน"
    assert result["mapping"]["credit"] == "เงินฝาก"
    assert result["mapping"]["counterparty_account"] == "บัญชีปลายทาง"
    assert result["mapping"]["channel"] is None
    assert result["validation"]["ok"] is True
    assert any("missing column" in warning for warning in result["warnings"])


def test_mapping_assist_rejects_non_json_llm_response(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"model": "qwen2.5:14b", "response": "not json"}

    monkeypatch.setattr("services.mapping_assist_service.chat", fake_chat)

    try:
        asyncio.run(
            suggest_mapping_with_llm(
                bank="scb",
                columns=["date", "description", "amount"],
                current_mapping={},
            )
        )
    except RuntimeError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("non-JSON LLM response should fail closed")
