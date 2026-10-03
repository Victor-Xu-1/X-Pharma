from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _remove(parent: Path, target: Path) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    helper = Path(__file__).parents[1] / "scripts/lib/security_staging.sh"
    return subprocess.run(  # noqa: S603 - fixed cleanup helper with explicit test-owned paths.
        [bash, "-c", 'source "$HELPER"; security_staging_remove "$1" "$2"', "test", str(parent), str(target)],
        env={**os.environ, "HELPER": str(helper)},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_security_staging_cleanup_respects_a_custom_temporary_parent(tmp_path: Path) -> None:
    parent = tmp_path / "custom temporary directory"
    parent.mkdir()
    staging = parent / "pharma-security.abc123"
    staging.mkdir()
    source = staging / "readonly-source"
    source.write_text("deliverable")
    source.chmod(0o400)
    preserved = parent / "unrelated-file"
    preserved.write_text("preserve")

    result = _remove(parent, staging)

    assert result.returncode == 0, result.stderr
    assert not staging.exists()
    assert preserved.read_text() == "preserve"


@pytest.mark.parametrize("kind", ["wrong-name", "outside-parent", "symlink", "traversal"])
def test_security_staging_cleanup_refuses_paths_outside_its_exact_boundary(tmp_path: Path, kind: str) -> None:
    parent = tmp_path / "temporary"
    parent.mkdir()
    if kind == "wrong-name":
        target = parent / "other-project"
        target.mkdir()
    elif kind == "outside-parent":
        target = tmp_path / "pharma-security.abc123"
        target.mkdir()
    elif kind == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        target = parent / "pharma-security.abc123"
        target.symlink_to(outside, target_is_directory=True)
    else:
        own = parent / "pharma-security.abc123"
        own.mkdir()
        target = own / ".." / ".."
    sentinel = target / "sentinel"
    sentinel.write_text("preserve")

    result = _remove(parent, target)

    assert result.returncode == 1
    assert "Refusing to remove" in result.stderr
    assert sentinel.read_text() == "preserve"
