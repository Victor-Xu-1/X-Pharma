from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.source_tree_manifest import POSTGRES_BUILD_INPUTS, SourceTreeManifestError, build_source_tree_manifest

INPUTS = (
    "deploy/postgres-rdkit.Dockerfile",
    "deploy/security/debian13-runtime-packages.lock",
    "deploy/security/install-runtime-security-packages.sh",
)


def test_reviewed_util_linux_binary_pins_preserve_debian_epochs() -> None:
    lock = Path(__file__).parents[1] / INPUTS[1]
    pins = dict(line.split("=", 1) for line in lock.read_text().splitlines() if line and not line.startswith("#"))
    expected = dict.fromkeys(
        ["libblkid1", "liblastlog2-2", "libmount1", "libsmartcols1", "libuuid1", "mount", "util-linux"],
        "2.41.5-0+deb13u1",
    )
    expected.update(bsdutils="1:2.41.5-0+deb13u1", login="1:4.16.0-2+really2.41.5-0+deb13u1")
    assert {name: pins.get(name) for name in expected} == expected


@pytest.mark.parametrize("changed", INPUTS)
def test_postgres_fingerprint_binds_each_copied_build_input(tmp_path: Path, changed: str) -> None:
    for relative in INPUTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    first = build_source_tree_manifest(tmp_path, relative_paths=INPUTS)
    assert first.file_count == 3
    (tmp_path / changed).write_text("patched", encoding="utf-8")
    assert build_source_tree_manifest(tmp_path, relative_paths=INPUTS).sha256 != first.sha256


def test_postgres_fingerprint_ignores_unrelated_app_changes(tmp_path: Path) -> None:
    for relative in INPUTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    first = build_source_tree_manifest(tmp_path, relative_paths=INPUTS)
    (tmp_path / "unrelated.py").write_text("not a postgres build input", encoding="utf-8")
    assert build_source_tree_manifest(tmp_path, relative_paths=INPUTS) == first


@pytest.mark.parametrize("relative", ["../outside", "/outside", "missing"])
def test_selected_build_inputs_fail_closed(tmp_path: Path, relative: str) -> None:
    with pytest.raises(SourceTreeManifestError):
        build_source_tree_manifest(tmp_path, relative_paths=(relative,))


def test_postgres_build_definition_cli_uses_the_same_three_inputs() -> None:
    root = Path(__file__).parents[1]
    result = subprocess.run(  # noqa: S603 - Fixed repository module and build-definition choice only.
        [sys.executable, "-B", "-m", "scripts.source_tree_manifest", str(root), "--build-definition", "postgres"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    manifest = build_source_tree_manifest(root, relative_paths=INPUTS)
    assert result.stdout.strip() == f"3 {manifest.sha256}"


def test_postgres_definition_covers_every_non_stage_copy() -> None:
    root = Path(__file__).parents[1]
    copied = {
        line.split()[1]
        for line in (root / INPUTS[0]).read_text().splitlines()
        if line.startswith("COPY ") and not line.startswith("COPY --from=")
    }
    assert POSTGRES_BUILD_INPUTS == INPUTS
    assert copied == set(INPUTS[1:])


@pytest.mark.parametrize("paths", [(), ("input", "input")])
def test_selected_inputs_reject_empty_or_duplicate_sets(tmp_path: Path, paths: tuple[str, ...]) -> None:
    (tmp_path / "input").write_text("original", encoding="utf-8")
    with pytest.raises(SourceTreeManifestError):
        build_source_tree_manifest(tmp_path, relative_paths=paths)


@pytest.mark.parametrize("parent_link", [False, True])
def test_selected_inputs_reject_file_or_parent_symlinks(tmp_path: Path, parent_link: bool) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "input").write_text("original", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(real if parent_link else real / "input", target_is_directory=parent_link)
    relative = "linked/input" if parent_link else "linked"
    with pytest.raises(SourceTreeManifestError, match="symbolic link"):
        build_source_tree_manifest(tmp_path, relative_paths=(relative,))


def test_security_ci_binds_the_cached_postgres_image_to_canonical_inputs() -> None:
    root = Path(__file__).parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    job = workflow["jobs"]["security-supply-chain"]
    steps = job["steps"]
    identity = next((step for step in steps if step.get("id") == "postgres_definition"), None)
    assert identity is not None
    build = next(step for step in steps if step.get("name") == "Build PostgreSQL 18 / RDKit release image")
    gate = next(step for step in steps if step.get("name") == "Run source, dependency, SBOM and image security gates")

    assert steps.index(identity) < steps.index(build) < steps.index(gate)
    assert "uv run --locked python scripts/source_tree_manifest.py . --build-definition postgres" in identity["run"]
    assert '[[ "$input_count" == 3 && "$definition_sha256" =~ ^[0-9a-f]{64}$ ]]' in identity["run"]
    assert "printf " in identity["run"] and "sha256=%s" in identity["run"]
    assert '"$definition_sha256" >> "$GITHUB_OUTPUT"' in identity["run"]
    assert build["with"]["labels"] == (
        "io.pharma.build-definition-sha256=${{ steps.postgres_definition.outputs.sha256 }}"
    )
    assert build["with"]["tags"] == "pharma-postgres-rdkit:18.4-2026.03.3"
    assert gate["run"] == "./scripts/run-security-gates.sh"
    assert job["timeout-minutes"] == 60
