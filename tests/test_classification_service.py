from __future__ import annotations

import pandas as pd

from services.classification_service import (
    apply_ai_classification_enrichment,
    build_classification_preview,
    build_scoped_classification_preview,
)


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


def test_build_classification_preview_is_read_only_and_forces_local(monkeypatch):
    monkeypatch.delenv("BSIE_ENABLE_LLM_CLASSIFICATION", raising=False)
    monkeypatch.setenv("OLLAMA_CLASSIFICATION_MODEL", "test-preview:model")

    from services import classification_service

    captured = {}

    def fake_local_pipeline(df, settings):
        captured["settings"] = settings
        captured["rows"] = df.to_dict(orient="records")
        return {
            "TXN-1": {
                "transaction_type": "WITHDRAW",
                "counterparty_name": "ATM Withdrawal",
                "confidence": 0.92,
                "nlp_promptpay": False,
                "nlp_accounts": "",
            }
        }

    monkeypatch.setattr(classification_service, "_run_local_llm_pipeline", fake_local_pipeline)

    result = build_classification_preview(_sample_df().to_dict(orient="records"))

    assert captured["settings"].llm_provider == "local"
    assert captured["settings"].llm_enabled is True
    assert captured["settings"].llm_model_name == "test-preview:model"
    assert result["source"] == "local_llm_classification_preview"
    assert result["read_only"] is True
    assert result["mutations_allowed"] is False
    assert result["suggestion_count"] == 1
    assert result["review_count"] == 1
    assert result["items"][0]["current"]["transaction_type"] == "OUT_TRANSFER"
    assert result["items"][0]["ai"]["transaction_type"] == "WITHDRAW"
    assert result["items"][0]["suggested"]["transaction_type"] == "WITHDRAW"
    assert result["items"][0]["action"] == "review_divergence"


def test_build_classification_preview_keeps_low_confidence_as_review_only(monkeypatch):
    from services import classification_service

    monkeypatch.setattr(
        classification_service,
        "_run_local_llm_pipeline",
        lambda df, settings: {
            "TXN-1": {
                "transaction_type": "WITHDRAW",
                "counterparty_name": "ATM Withdrawal",
                "confidence": 0.40,
                "nlp_promptpay": False,
                "nlp_accounts": "",
            }
        },
    )

    result = build_classification_preview(_sample_df().to_dict(orient="records"))

    assert result["items"][0]["action"] == "below_threshold"
    assert result["items"][0]["review_required"] is True
    assert result["items"][0]["would_apply"] is False
    assert result["items"][0]["suggested"]["transaction_type"] == "OUT_TRANSFER"


def test_build_scoped_classification_preview_queries_scope_rows(monkeypatch):
    from services import classification_service

    captured = {}

    def fake_search_transactions(session, **kwargs):
        captured["session"] = session
        captured["kwargs"] = kwargs
        return [
            {
                "id": "TXN-SCOPE-1",
                "parser_run_id": "RUN-1",
                "file_id": "FILE-1",
                "transaction_datetime": "2026-04-24T10:30:00Z",
                "amount": -500.0,
                "direction": "OUT",
                "description_normalized": "ATM WDL",
                "channel": "ATM",
                "transaction_type": "OUT_TRANSFER",
                "counterparty_name_normalized": "",
                "counterparty_account_normalized": "",
            }
        ]

    monkeypatch.setattr(classification_service, "search_transactions", fake_search_transactions)
    monkeypatch.setattr(
        classification_service,
        "_run_local_llm_pipeline",
        lambda df, settings: {
            "TXN-SCOPE-1": {
                "transaction_type": "WITHDRAW",
                "counterparty_name": "ATM Withdrawal",
                "confidence": 0.91,
                "nlp_promptpay": False,
                "nlp_accounts": "",
            }
        },
    )

    dummy_session = object()
    result = build_scoped_classification_preview(
        dummy_session,
        {"parser_run_id": "RUN-1", "file_id": "FILE-1", "account": "123-456-7890"},
        max_transactions=3,
    )

    assert captured["session"] is dummy_session
    assert captured["kwargs"]["parser_run_id"] == "RUN-1"
    assert captured["kwargs"]["file_id"] == "FILE-1"
    assert captured["kwargs"]["account"] == "1234567890"
    assert captured["kwargs"]["limit"] == 3
    assert result["preview_input"] == "scope"
    assert result["scope"]["account_digits"] == "1234567890"
    assert result["items"][0]["transaction_id"] == "TXN-SCOPE-1"
    assert result["items"][0]["ai"]["transaction_type"] == "WITHDRAW"


def test_build_scoped_classification_preview_returns_empty_scope_result(monkeypatch):
    from services import classification_service

    monkeypatch.setattr(classification_service, "search_transactions", lambda session, **kwargs: [])

    result = build_scoped_classification_preview(object(), {"parser_run_id": "RUN-EMPTY"})

    assert result["status"] == "no_transactions"
    assert result["read_only"] is True
    assert result["mutations_allowed"] is False
    assert result["items"] == []
    assert "no_transactions_matched_scope" in result["warnings"]
