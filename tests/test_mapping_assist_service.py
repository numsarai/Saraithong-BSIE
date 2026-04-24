import asyncio
from pathlib import Path

from services.mapping_assist_service import suggest_mapping_with_llm, suggest_mapping_with_vision_llm


def test_mapping_assist_parses_repairs_and_validates_llm_json(monkeypatch):
    async def fake_chat(*args, **kwargs):
        assert kwargs["auto_context"] is False
        assert kwargs["model"] == "gemma4:26b"
        assert kwargs["max_tokens"] > 0
        assert kwargs["think"] is False
        return {
            "model": kwargs["model"],
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
    assert result["model"] == "gemma4:26b"
    assert result["confidence"] == 0.82
    assert result["mapping"]["amount"] is None
    assert result["mapping"]["debit"] == "ถอนเงิน"
    assert result["mapping"]["credit"] == "เงินฝาก"
    assert result["mapping"]["counterparty_account"] == "บัญชีปลายทาง"
    assert result["mapping"]["channel"] is None
    assert result["validation"]["ok"] is True
    assert any("missing column" in warning for warning in result["warnings"])


def test_mapping_assist_preserves_direction_marker_amount_path(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {
            "model": kwargs["model"],
            "response": """
            {
              "mapping": {
                "date": "วันที่",
                "description": "รายการ",
                "amount": "จำนวนเงิน",
                "direction_marker": "ประเภทรายการ",
                "debit": "ประเภทรายการ",
                "balance": "ยอดคงเหลือ"
              },
              "confidence": 0.88,
              "reasons": ["DR/CR marker signs the unsigned amount"],
              "warnings": []
            }
            """,
        }

    monkeypatch.setattr("services.mapping_assist_service.chat", fake_chat)

    result = asyncio.run(
        suggest_mapping_with_llm(
            bank="bay",
            columns=["วันที่", "รายการ", "ประเภทรายการ", "จำนวนเงิน", "ยอดคงเหลือ"],
            sample_rows=[{"วันที่": "2026-01-08", "รายการ": "โอน", "ประเภทรายการ": "DR", "จำนวนเงิน": "500"}],
            current_mapping={},
        )
    )

    assert result["mapping"]["amount"] == "จำนวนเงิน"
    assert result["mapping"]["direction_marker"] == "ประเภทรายการ"
    assert result["mapping"]["debit"] is None
    assert result["validation"]["ok"] is True
    assert result["validation"]["amount_mode"] == "direction_marker"


def test_mapping_assist_repairs_ambiguous_balance_to_curated_alias(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {
            "model": kwargs["model"],
            "response": """
            {
              "mapping": {
                "date": "วันที่",
                "description": "คำอธิบายรายการ",
                "amount": "ยอดเงิน",
                "balance": "ยอดหลังรายการ",
                "channel": "ช่องทาง",
                "counterparty_account": "บัญชีปลายทาง"
              },
              "confidence": 0.86,
              "reasons": ["balance-like headers are present"],
              "warnings": []
            }
            """,
        }

    monkeypatch.setattr("services.mapping_assist_service.chat", fake_chat)

    result = asyncio.run(
        suggest_mapping_with_llm(
            bank="ttb",
            columns=["วันที่", "คำอธิบายรายการ", "ยอดเงิน", "ยอดคงเหลือ", "ยอดหลังรายการ", "ช่องทาง", "บัญชีปลายทาง"],
            sample_rows=[{"วันที่": "2026-01-10", "คำอธิบายรายการ": "TRANSFER TO", "ยอดเงิน": "-1,100.00", "ยอดคงเหลือ": "18,900.00", "ยอดหลังรายการ": "18,900.00"}],
            current_mapping={"balance": "ยอดหลังรายการ"},
        )
    )

    assert result["mapping"]["balance"] == "ยอดคงเหลือ"
    assert result["validation"]["ok"] is True


def test_mapping_assist_marks_selected_bank_as_authority(monkeypatch):
    async def fake_chat(message, *args, **kwargs):
        assert "analyst-selected bank authority" in message
        assert '"bank": "ktb"' in message
        assert '"detected_bank": "scb"' in message
        assert '"override_detected": true' in message
        return {
            "model": kwargs["model"],
            "response": """
            {
              "mapping": {
                "date": "วันที่",
                "description": "รายละเอียด",
                "amount": "จำนวนเงิน"
              },
              "confidence": 0.81,
              "reasons": ["selected bank is the authority"],
              "warnings": []
            }
            """,
        }

    monkeypatch.setattr("services.mapping_assist_service.chat", fake_chat)

    result = asyncio.run(
        suggest_mapping_with_llm(
            bank="ktb",
            detected_bank={"key": "scb", "bank": "SCB", "confidence": 0.95},
            columns=["วันที่", "รายละเอียด", "จำนวนเงิน"],
            sample_rows=[{"วันที่": "2026-01-10", "รายละเอียด": "TRANSFER", "จำนวนเงิน": "100.00"}],
            current_mapping={},
        )
    )

    assert result["bank_authority"] == {
        "selected_bank": "ktb",
        "detected_bank": "scb",
        "bank_override_detected": True,
        "authority": "analyst_selected",
    }
    assert any("differs from detected bank" in warning for warning in result["warnings"])


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


def test_vision_mapping_assist_uses_preview_and_validation(monkeypatch):
    async def fake_chat_with_file(message, file_bytes, file_type, **kwargs):
        assert file_bytes == b"preview"
        assert file_type == "image/png"
        assert "original PDF/image preview" in message
        assert kwargs["model"] == "gemma4:26b"
        assert kwargs["max_tokens"] > 0
        assert kwargs["think"] is False
        return {
            "model": kwargs.get("model") or "qwen2.5vl:7b",
            "response": """
            {
              "mapping": {
                "date": "วันที่",
                "description": "รายการ",
                "debit": "ถอน",
                "credit": "ฝาก",
                "balance": "ยอดคงเหลือ",
                "counterparty_account": "missing visual column"
              },
              "confidence": 0.77,
              "reasons": ["visual table labels match OCR columns"],
              "warnings": ["counterparty column is unclear"]
            }
            """,
        }

    monkeypatch.setattr(
        "services.mapping_assist_service._load_vision_preview",
        lambda path: (b"preview", "image/png", {"source_type": "pdf_vision", "page_count": 2, "preview_page": 1}),
    )
    monkeypatch.setattr("services.mapping_assist_service.chat_with_file", fake_chat_with_file)

    result = asyncio.run(
        suggest_mapping_with_vision_llm(
            file_path=Path("/tmp/source.pdf"),
            bank="scb",
            detected_bank={"key": "scb", "confidence": 0.8},
            columns=["วันที่", "รายการ", "ถอน", "ฝาก", "ยอดคงเหลือ"],
            sample_rows=[{"วันที่": "2026-01-01", "รายการ": "โอน", "ฝาก": "100"}],
            current_mapping={"date": "วันที่", "description": "รายการ"},
            sheet_name="PDF_OCR",
            header_row=0,
        )
    )

    assert result["source"] == "local_llm_vision_mapping_assist"
    assert result["suggestion_only"] is True
    assert result["auto_pass_eligible"] is False
    assert result["confidence"] == 0.77
    assert result["mapping"]["debit"] == "ถอน"
    assert result["mapping"]["credit"] == "ฝาก"
    assert result["mapping"]["counterparty_account"] is None
    assert result["file_context"]["source_type"] == "pdf_vision"
    assert result["validation"]["ok"] is True
    assert any("missing visual column" in warning for warning in result["warnings"])
