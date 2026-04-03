from core.config_registry import validate_registry


def test_config_registry_validates_built_in_samples():
    result = validate_registry()
    assert result["entry_count"] >= 5
    assert any(item["config_key"] == "bay" and item["normalized"] is True for item in result["results"])
