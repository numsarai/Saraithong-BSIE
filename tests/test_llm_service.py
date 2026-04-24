import asyncio

from services.llm_service import benchmark_llm_roles, chat, get_llm_model_config, resolve_model


def test_llm_model_config_exposes_role_defaults():
    config = get_llm_model_config()

    assert config["base_url"].startswith("http")
    assert config["default_model"]
    assert config["roles"]["text"]
    assert config["roles"]["vision"]
    assert config["roles"]["fast"]


def test_resolve_model_uses_explicit_model_before_role_default():
    config = get_llm_model_config()

    assert resolve_model(" custom:model ", "text") == "custom:model"
    assert resolve_model("", "text") == config["roles"]["text"]
    assert resolve_model("", "vision") == config["roles"]["vision"]
    assert resolve_model("", "fast") == config["roles"]["fast"]
    assert resolve_model("", "unknown") == config["default_model"]


def test_benchmark_llm_roles_runs_text_and_fast_without_database_context(monkeypatch):
    calls = []

    async def fake_chat(message, **kwargs):
        calls.append({"message": message, **kwargs})
        return {
            "model": kwargs["model"],
            "response": '{"status":"ok","language":"th"}',
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }

    monkeypatch.setattr("services.llm_service.chat", fake_chat)

    result = asyncio.run(benchmark_llm_roles(iterations=1))

    assert result["status"] == "ok"
    assert result["source"] == "local_llm_benchmark"
    assert result["local_only"] is True
    assert [item["role"] for item in result["results"]] == ["text", "fast"]
    assert all(item["ok_count"] == 1 for item in result["results"])
    assert all(call["auto_context"] is False for call in calls)
    assert all(call["think"] is False for call in calls)
    assert all(call["max_tokens"] > 0 for call in calls)


def test_benchmark_llm_roles_marks_invalid_json_as_partial(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"model": kwargs["model"], "response": "plain text"}

    monkeypatch.setattr("services.llm_service.chat", fake_chat)

    result = asyncio.run(benchmark_llm_roles(roles=["text"], iterations=1))

    assert result["status"] == "partial"
    assert result["results"][0]["status"] == "partial"
    assert result["results"][0]["runs"][0]["status"] == "invalid_json"


def test_benchmark_llm_roles_can_include_vision(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {"model": kwargs["model"], "response": '{"status":"ok"}'}

    async def fake_chat_with_file(message, file_bytes, file_type, **kwargs):
        assert file_bytes
        assert file_type == "image/png"
        assert kwargs["think"] is False
        assert kwargs["max_tokens"] > 0
        return {"model": kwargs["model"], "response": '{"status":"ok"}'}

    monkeypatch.setattr("services.llm_service.chat", fake_chat)
    monkeypatch.setattr("services.llm_service.chat_with_file", fake_chat_with_file)

    result = asyncio.run(benchmark_llm_roles(include_vision=True, iterations=1))

    assert result["status"] == "ok"
    assert [item["role"] for item in result["results"]] == ["text", "fast", "vision"]


def test_benchmark_llm_roles_rejects_unknown_roles():
    try:
        asyncio.run(benchmark_llm_roles(roles=["text", "unknown"], iterations=1))
    except ValueError as exc:
        assert "Unsupported benchmark role" in str(exc)
    else:
        raise AssertionError("unknown benchmark roles should be rejected")


def test_project_chat_system_prompt_is_scoped_to_bsie(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "test:model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }

    class DummyClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            captured["payload"] = json
            return DummyResponse()

    monkeypatch.setattr("services.llm_service.httpx.AsyncClient", DummyClient)

    result = asyncio.run(chat("Who won a sports game?", auto_context=False, model="test:model"))

    assert result["response"] == "ok"
    system_prompt = captured["payload"]["messages"][0]["content"]
    assert "Project Scope Guardrail" in system_prompt
    assert "answer only about BSIE" in system_prompt
