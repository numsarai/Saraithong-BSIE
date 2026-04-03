from pathlib import Path

import pytest

from core.config_registry import REGISTRY_PATH, load_registry, validate_registry


def test_config_registry_validates_built_in_samples():
    registry = load_registry(REGISTRY_PATH)
    project_root = REGISTRY_PATH.parent.parent
    missing = [
        entry["sample_path"]
        for entry in registry.get("entries", [])
        if not (project_root / Path(entry["sample_path"])).exists()
    ]
    if missing:
        pytest.skip(f"registry sample files not available in this checkout: {', '.join(missing)}")

    result = validate_registry()
    assert result["entry_count"] >= 5
    assert any(item["config_key"] == "bay" and item["normalized"] is True for item in result["results"])
