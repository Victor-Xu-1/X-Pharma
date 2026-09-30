from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from pharma_intel.runtime_layout import RuntimeLayoutError, relocate_runtime_paths


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    (repository / "backups").mkdir(parents=True)
    (repository / "backups" / "database.dump").write_bytes(b"database")
    (repository / "manifests" / "runtime").mkdir(parents=True)
    (repository / "manifests" / "runtime" / "acceptance.json").write_text("{}", encoding="utf-8")
    return repository


def test_runtime_relocation_dry_run_does_not_change_source(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    storage = tmp_path / "runtime"
    report = relocate_runtime_paths(repository, storage)
    assert report.applied is False
    assert {item.state for item in report.relocations} == {"would_relocate"}
    assert (repository / "backups" / "database.dump").is_file()
    assert not storage.exists()


def test_runtime_relocation_preserves_data_and_is_idempotent(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    storage = tmp_path / "runtime"
    first = relocate_runtime_paths(repository, storage, apply=True)
    second = relocate_runtime_paths(repository, storage, apply=True)
    assert first.applied is True
    assert {item.state for item in first.relocations} == {"relocated"}
    assert {item.state for item in second.relocations} == {"already_relocated"}
    assert (repository / "backups").is_symlink()
    assert (repository / "manifests" / "runtime").is_symlink()
    assert (repository / "backups" / "database.dump").read_bytes() == b"database"
    assert (repository / "manifests" / "runtime" / "acceptance.json").read_text(encoding="utf-8") == "{}"
    assert stat.S_IMODE((storage / "backups").stat().st_mode) == 0o700
    assert stat.S_IMODE((storage / "evidence").stat().st_mode) == 0o700
    manifest = storage / "runtime-layout.json"
    assert json.loads(manifest.read_text(encoding="utf-8"))["applied"] is True
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o600


def test_runtime_relocation_rejects_unsafe_or_ambiguous_targets(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    with pytest.raises(RuntimeLayoutError, match="outside"):
        relocate_runtime_paths(repository, repository / "runtime")
    storage = tmp_path / "runtime"
    (storage / "backups").mkdir(parents=True)
    with pytest.raises(RuntimeLayoutError, match="merge"):
        relocate_runtime_paths(repository, storage, apply=True)


def test_runtime_relocation_rejects_links_inside_runtime_tree(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "backups" / "unsafe").symlink_to(tmp_path)
    with pytest.raises(RuntimeLayoutError, match="symbolic link"):
        relocate_runtime_paths(repository, tmp_path / "runtime")
