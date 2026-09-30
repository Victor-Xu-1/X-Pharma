from __future__ import annotations

import importlib.util
import stat
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]


def configuration_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "development_configuration", ROOT / "scripts/configure-development.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configuration_creates_independent_secrets_and_consistent_database_urls(tmp_path: Path) -> None:
    module = configuration_module()
    (tmp_path / ".env.example").write_bytes((ROOT / ".env.example").read_bytes())
    target = module.configure(tmp_path)
    values = dict(line.split("=", 1) for line in target.read_text().splitlines() if line and not line.startswith("#"))
    secret_values = [values[key] for key in module.SECRET_FIELDS]
    assert len(set(secret_values)) == len(secret_values)
    assert all(len(value) >= 32 and "replace-" not in value for value in secret_values)
    assert values["POSTGRES_RUNTIME_PASSWORD"] in values["RUNTIME_DATABASE_URL"]
    assert values["DATABASE_URL"] == values["RUNTIME_DATABASE_URL"]
    assert values["AI_GOVERNANCE_ENABLED"] == "false"
    assert values["AI_API_KEY"] == ""
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    Fernet(values["LLM_CREDENTIALS_ENCRYPTION_KEY"].encode())


def test_configuration_preserves_existing_environment(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("existing configuration\n")
    with pytest.raises(FileExistsError, match="preserved"):
        configuration_module().configure(tmp_path)
    assert target.read_text() == "existing configuration\n"


def test_configuration_rejects_incomplete_or_production_templates() -> None:
    module = configuration_module()
    with pytest.raises(ValueError, match="missing required"):
        module.render_environment("APP_ENV=development\n")
    template = (ROOT / ".env.example").read_text()
    with pytest.raises(ValueError, match="only creates development"):
        module.render_environment(template.replace("APP_ENV=development", "APP_ENV=production"))
