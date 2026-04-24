from services.llm_service import get_llm_model_config, resolve_model


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
