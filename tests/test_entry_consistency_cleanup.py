from __future__ import annotations

import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _remove_entry_staging(parent: Path, target: Path) -> subprocess.CompletedProcess[str]:
    library = ROOT / "scripts/lib/entry_staging.sh"
    assert library.is_file()
    return subprocess.run(  # noqa: S603 - fixed owned script; fixture paths are positional arguments, not shell source.
        [
            "/usr/bin/bash",
            "-c",
            'source "$1" && entry_staging_remove "$2" "$3"',
            "bash",
            str(library),
            str(parent),
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_entry_projection_cleanup_uses_the_scoped_bounded_opensearch_client() -> None:
    source = (ROOT / "scripts/verify-entry-consistency.sh").read_text(encoding="utf-8")
    assert 'source "$root/scripts/lib/mcp_fixture_http.sh"' in source
    assert "mcp_fixture_opensearch none --request DELETE" in source
    assert "http://127.0.0.1:9200/" not in source


def test_entry_fixture_cleanup_preserves_other_accounts_and_obeys_membership_foreign_keys() -> None:
    source = (ROOT / "scripts/verify-entry-consistency.sh").read_text(encoding="utf-8")
    statements = re.findall(r"^DELETE FROM (?:user_sessions|organization_memberships|users) WHERE .*?;$", source, re.M)
    assert statements, "Account cleanup SQL is missing"
    with sqlite3.connect(":memory:") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(
            "CREATE TABLE users(id TEXT PRIMARY KEY, normalized_email TEXT);"
            "CREATE TABLE organization_memberships(user_id TEXT REFERENCES users(id));"
            "CREATE TABLE user_sessions(user_id TEXT REFERENCES users(id));"
            "INSERT INTO users VALUES('fixture','entry-1@example.test'),('other','other@example.test');"
            "INSERT INTO organization_memberships VALUES('fixture'),('other');"
            "INSERT INTO user_sessions VALUES('fixture'),('other');"
        )
        for statement in statements:
            connection.execute(statement.replace("'$email'", "'entry-1@example.test'"))
        assert connection.execute("SELECT id FROM users").fetchall() == [("other",)]
        assert connection.execute("SELECT user_id FROM organization_memberships").fetchall() == [("other",)]
        assert connection.execute("SELECT user_id FROM user_sessions").fetchall() == [("other",)]


def test_entry_staging_cleanup_accepts_an_explicit_parent_not_only_tmp(tmp_path: Path) -> None:
    parent = tmp_path / "e-drive-staging"
    parent.mkdir()
    fixture = parent / "pharma-entry-consistency.case"
    fixture.mkdir()
    (fixture / "report.json").write_text("{}", encoding="utf-8")
    result = _remove_entry_staging(parent, fixture)
    assert result.returncode == 0, result.stderr
    assert not fixture.exists()


def test_entry_staging_cleanup_rejects_paths_outside_its_verified_parent(tmp_path: Path) -> None:
    parent = tmp_path / "owned"
    parent.mkdir()
    outside = tmp_path / "pharma-entry-consistency.outside"
    outside.mkdir()
    marker = outside / "keep"
    marker.touch()
    result = _remove_entry_staging(parent, outside)
    assert result.returncode != 0 and marker.exists()


@pytest.mark.parametrize("kind", ["wrong_prefix", "symlink"])
def test_entry_staging_cleanup_rejects_unowned_names_and_symlinks(tmp_path: Path, kind: str) -> None:
    parent = tmp_path / "owned"
    parent.mkdir()
    protected = parent / "must-keep"
    protected.mkdir()
    marker = protected / "keep"
    marker.touch()
    target = protected
    if kind == "symlink":
        target = parent / "pharma-entry-consistency.link"
        target.symlink_to(protected, target_is_directory=True)
    result = _remove_entry_staging(parent, target)
    assert result.returncode != 0 and marker.exists()
