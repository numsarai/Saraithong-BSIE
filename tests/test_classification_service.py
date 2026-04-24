from __future__ import annotations

import pandas as pd

from services.classification_service import apply_ai_classification_enrichment


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "TXN-1",
                "date": "2026-04-24",
                "direction": "OUT",
                "amount": -500.0,
                "description_raw": "ATM WDL 1234567890",
                "channel": "ATM",
                "transaction_type": "OUT_TRANSFER",
                "confidence": 0.8,
                "counterparty_name": "Old Name",
            }
        ]
    )


def test_apply_ai_classification_enrichment_defaults_to_heuristic(monkeypatch):
    monkeypatch.delenv("BSIE_ENABLE_LLM_CLASSIFICATION", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    result = apply_ai_classification_enrichment(_sample_df())

    assert result.loc[0, "classification_source"] == "heuristic"
    assert result.loc[0, "classification_model"] == "heuristic-only"
    assert result.loc[0, "heuristic_transaction_type"] == "OUT_TRANSFER"


def test_apply_ai_classification_enrichment_merges_high_confidence_ai(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_LLM_CLASSIFICATION", "true")
    monkeypatch.setenv("BSIE_CLASSIFICATION_LLM_PROVIDER", "legacy_openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("BSIE_LLM_MIN_CONFIDENCE", "0.85")

    from services import classification_service

    monkeypatch.setattr(
        classification_service,
        "run_llm_pipeline",
        lambda df: {
            "TXN-1": {
                "transaction_type": "WITHDRAW",
                "counterparty_name": "ATM Withdrawal",
                "confidence": 0.93,
                "nlp_promptpay": False,
                "nlp_accounts": "",
            }
        },
    )

    result = apply_ai_classification_enrichment(_sample_df())

    assert result.loc[0, "transaction_type"] == "WITHDRAW"
    assert result.loc[0, "classification_source"] == "heuristic+ai"
    assert bool(result.loc[0, "classification_review_flag"]) is True
    assert result.loc[0, "ai_transaction_type"] == "WITHDRAW"
    assert result.loc[0, "counterparty_name"] == "ATM Withdrawal"


def test_apply_ai_classification_enrichment_keeps_heuristic_below_threshold(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_LLM_CLASSIFICATION", "true")
    monkeypatch.setenv("BSIE_CLASSIFICATION_LLM_PROVIDER", "legacy_openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("BSIE_LLM_MIN_CONFIDENCE", "0.95")

    from services import classification_service

    monkeypatch.setattr(
        classification_service,
        "run_llm_pipeline",
        lambda df: {
            "TXN-1": {
                "transaction_type": "WITHDRAW",
                "counterparty_name": "ATM Withdrawal",
                "confidence": 0.70,
                "nlp_promptpay": False,
                "nlp_accounts": "",
            }
        },
    )

    result = apply_ai_classification_enrichment(_sample_df())

    assert result.loc[0, "transaction_type"] == "OUT_TRANSFER"
    assert result.loc[0, "classification_source"] == "heuristic"
    assert result.loc[0, "classification_reason"] == "rule_nlp_hybrid|llm_below_threshold"


def test_apply_ai_classification_enrichment_uses_local_provider_without_api_key(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_LLM_CLASSIFICATION", "true")
    monkeypatch.setenv("BSIE_CLASSIFICATION_LLM_PROVIDER", "local")
    monkeypatch.setenv("OLLAMA_CLASSIFICATION_MODEL", "test-local:model")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from services import classification_service

    captured = {}

    def fake_post(prompt, settings):
        captured["prompt"] = prompt
        captured["settings"] = settings
        return """
        {
          "results": [
            {
              "transaction_id": "TXN-1",
              "transaction_type": "WITHDRAW",
              "counterparty_name": "ATM Withdrawal",
              "confidence": 0.91,
              "nlp_promptpay": false,
              "nlp_accounts": "1234567890"
            }
          ]
        }
        """

    monkeypatch.setattr(classification_service, "_post_ollama_classification_chat", fake_post)

    result = apply_ai_classification_enrichment(_sample_df())

    assert captured["settings"].llm_provider == "local"
    assert captured["settings"].llm_model_name == "test-local:model"
    assert "TXN-1" in captured["prompt"]
    assert result.loc[0, "transaction_type"] == "WITHDRAW"
    assert result.loc[0, "classification_source"] == "heuristic+ai"
    assert result.loc[0, "classification_model"] == "test-local:model"
    assert result.loc[0, "nlp_accounts"] == "1234567890"


def test_apply_ai_classification_enrichment_drops_invalid_local_results(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_LLM_CLASSIFICATION", "true")
    monkeypatch.setenv("BSIE_CLASSIFICATION_LLM_PROVIDER", "local")

    from services import classification_service

    monkeypatch.setattr(
        classification_service,
        "_post_ollama_classification_chat",
        lambda prompt, settings: """
        {
          "results": [
            {
              "transaction_id": "TXN-1",
              "transaction_type": "INVENTED_TYPE",
              "counterparty_name": "Invented",
              "confidence": 1,
              "nlp_promptpay": false,
              "nlp_accounts": ""
            }
          ]
        }
        """,
    )

    result = apply_ai_classification_enrichment(_sample_df())

    assert result.loc[0, "transaction_type"] == "OUT_TRANSFER"
    assert result.loc[0, "classification_source"] == "heuristic"
    assert result.loc[0, "classification_reason"] == "rule_nlp_hybrid|llm_empty"
    assert result.loc[0, "classification_model"] == "heuristic-only"
