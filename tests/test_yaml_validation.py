from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_yaml import validate_yaml


def test_repository_yaml_is_duplicate_key_free() -> None:
    root = Path(__file__).parents[1]

    result = validate_yaml(
        [
            root / "compose.yaml",
            root / "compose.dev.yaml",
            root / "compose.telemetry.yaml",
            root / "deploy" / "kubernetes",
        ]
    )

    assert result["file_count"] >= 18
    assert result["document_count"] >= result["file_count"]


def test_yaml_validator_rejects_nested_duplicate_keys_with_location(tmp_path: Path) -> None:
    document = tmp_path / "duplicate.yaml"
    document.write_text("service:\n  port: 8080\n  port: 8090\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate key 'port'") as captured:
        validate_yaml([document])
    assert "line 3" in str(captured.value)


def test_yaml_validator_rejects_missing_or_unsupported_inputs(tmp_path: Path) -> None:
    unsupported = tmp_path / "manifest.json"
    unsupported.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported extension"):
        validate_yaml([unsupported])
