from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.source_tree_manifest import SourceTreeManifestError, build_source_tree_manifest


def test_cpython_security_runtime_inputs_match_reviewed_digests() -> None:
    root = Path(__file__).parents[1]
    descriptor = json.loads((root / "deploy/cpython/downloads.json").read_text())
    download = descriptor["cpython-3.13.16-linux-x86_64-gnu"]
    assert download["sha256"] == "4595c5589fff7bf0cb158d9a88a797e0d791fa33830770fcb7bf3f4b104feeae"
    image = "python:3.13.16-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c"
    for filename in ("deploy/api.Dockerfile", "services/ocr/Dockerfile"):
        assert image in (root / filename).read_text()


def test_installed_tarfile_prevents_hardlink_symlink_relocation() -> None:
    directory = Path(__file__).parents[1] / "deploy" / "cpython"
    probe = runpy.run_path(str(directory.parents[1] / "scripts" / "verify_cpython_tarfile.py"))
    probe["verify_hardlink_relocation"]()


def test_source_tree_manifest_is_deterministic_and_binds_paths(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "nested").mkdir()
    (second / "nested").mkdir()
    (first / "b.txt").write_text("beta", encoding="utf-8")
    (first / "nested" / "a.txt").write_text("alpha", encoding="utf-8")
    (second / "nested" / "a.txt").write_text("alpha", encoding="utf-8")
    (second / "b.txt").write_text("beta", encoding="utf-8")

    first_manifest = build_source_tree_manifest(first)
    second_manifest = build_source_tree_manifest(second)

    assert first_manifest == second_manifest
    assert first_manifest.file_count == 2
    assert len(first_manifest.sha256) == 64

    (second / "b.txt").rename(second / "c.txt")
    assert build_source_tree_manifest(second).sha256 != first_manifest.sha256


def test_source_tree_manifest_binds_file_content(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    item = source / "item.txt"
    item.write_text("version-one", encoding="utf-8")
    first = build_source_tree_manifest(source)

    item.write_text("version-two", encoding="utf-8")
    second = build_source_tree_manifest(source)

    assert first.file_count == second.file_count == 1
    assert first.sha256 != second.sha256


def test_source_tree_manifest_rejects_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("outside", encoding="utf-8")
    (source / "linked.txt").symlink_to(target)

    with pytest.raises(SourceTreeManifestError, match="symbolic link"):
        build_source_tree_manifest(source)


def test_security_gate_is_executable_and_embedded_python_compiles() -> None:
    script = Path(__file__).parents[1] / "scripts" / "run-security-gates.sh"
    bash = shutil.which("bash")
    assert bash is not None
    assert os.access(script, os.X_OK)
    source = script.read_text(encoding="utf-8")
    embedded_blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", source, flags=re.DOTALL)

    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)], check=False, capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr

    assert embedded_blocks
    assert "semgrep scan --jobs 1 --error --timeout 30" in source
    assert "Semgrep report contains scan errors" in source
    assert '"$staging_root/deploy/api.Dockerfile"' in source
    assert '"$staging_root/services/ocr/Dockerfile"' in source
    assert '"$staging_root/deploy/postgres-rdkit.Dockerfile"' in source
    assert "ocr.openvex.json" in source
    assert source.index('checked "Application image build from staged source"') < source.index(
        'api_digest=$(docker_image_digest "$api_image")'
    )
    assert "io.pharma.source-tree-sha256" in source
    assert "io.pharma.build-definition-sha256" in source
    assert "OCR_PYPI_INDEX_URL must be a credential-free HTTPS package index URL" in source
    assert '--build-arg "OCR_PYPI_INDEX_URL=$OCR_PYPI_INDEX_URL"' in source
    assert '--build-arg "HTTP_PROXY=$APT_HTTP_PROXY"' in source
    assert '--build-arg "HTTPS_PROXY=$APT_HTTP_PROXY"' in source
    assert '"target_build_inputs"' in source
    assert 'checked_with_retry "Python dependency vulnerability audit" 3' in source
    assert '--proto "=https" --tlsv1.2 --http1.1' in source
    assert "pip-audit --timeout 60" in source
    assert "SYFT_CHECK_FOR_APP_UPDATE=false" in source
    assert "docker-archive:/scan/$target.tar" in source
    assert "timeout --signal=TERM --kill-after=15s 600s" in source
    assert "/var/run/docker.sock" not in source
    for index, embedded_source in enumerate(embedded_blocks):
        try:
            compile(embedded_source, f"run-security-gates.sh:heredoc:{index}", "exec")
        except SyntaxError as exc:
            pytest.fail(f"embedded Python heredoc {index} does not compile: {exc}")


def test_postgres_rdkit_build_pins_transitive_source_archives() -> None:
    dockerfile = (Path(__file__).parents[1] / "deploy" / "postgres-rdkit.Dockerfile").read_text(encoding="utf-8")

    assert "CATCH2_SOURCE_SHA256=" in dockerfile
    assert "BETTER_ENUMS_SOURCE_SHA256=" in dockerfile
    assert "sha256sum --check --strict" in dockerfile
    assert "FETCHCONTENT_SOURCE_DIR_CATCH2=/tmp/deps/catch2" in dockerfile
    assert "FETCHCONTENT_SOURCE_DIR_BETTER_ENUMS=/tmp/deps/better-enums" in dockerfile
    assert "GIT_REPOSITORY" not in dockerfile


def test_wsl_tool_bootstrap_is_executable_and_shell_valid() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "bootstrap-wsl-tools.sh"
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    completed = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled test inputs.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_local_runtime_startup_is_sequential_and_shell_valid() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "up-local.sh"
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)], cwd=root, check=False, capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(  # noqa: S603 - Bash path and help arguments are controlled.
        [bash, str(script), "--help"], cwd=root, check=False, capture_output=True, text=True
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "without triggering Compose parallel builds" in help_result.stdout
    source = script.read_text(encoding="utf-8")
    assert "FORCE_POSTGRES_BUILD:-false" in source
    assert 'docker image inspect "${postgres_image}"' in source


def test_browser_acceptance_script_is_executable_and_help_is_side_effect_free() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "run-browser-acceptance.sh"
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)], cwd=root, check=False, capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(  # noqa: S603 - Bash path and help arguments are controlled.
        [bash, str(script), "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "optional report never contains test credentials" in help_result.stdout
    source = script.read_text(encoding="utf-8")
    assert "DELETE FROM entities" in source
    assert "opensearch-delete-" in source
    assert '"temporary_entities_after": 0' in source
    embedded_blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", source, flags=re.DOTALL)
    assert embedded_blocks
    for index, embedded_source in enumerate(embedded_blocks):
        compile(embedded_source, f"run-browser-acceptance.sh:heredoc:{index}", "exec")


def test_database_acceptance_script_is_executable_and_help_is_side_effect_free() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-local-database.sh"
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(  # noqa: S603 - Bash path and help arguments are controlled.
        [bash, str(script), "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "report contains no credentials" in help_result.stdout
    embedded_blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", script.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert len(embedded_blocks) == 1
    compile(embedded_blocks[0], "verify-local-database.sh:heredoc", "exec")


def test_enterprise_database_acceptance_requires_explicit_tenant_signing_secret() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-enterprise-postgres.sh"
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    preflight = script.read_text(encoding="utf-8").split("compose=(", maxsplit=1)[0]
    assert "TENANT_CONTEXT_SIGNING_SECRET" in preflight


@pytest.mark.parametrize(
    ("name", "help_fragment", "embedded_python_blocks"),
    [
        ("verify-automatic-ingestion.sh", "never invokes a manual ingest command", 1),
        ("verify-local-ingestion.sh", "never creates source files", 1),
        ("verify-local-malware.sh", "only temporary source content", 1),
        ("verify-local-parser.sh", "real format parsers", 2),
        ("verify-local-backup-restore.sh", "never copied into release evidence", 1),
        ("verify-pilot-ingestion.sh", "unattended Temporal ingestion first", 0),
        ("run-sftp-source-acceptance.sh", "never records private credentials", 2),
        ("run-smb-source-acceptance.sh", "never records the generated account password", 2),
        ("validate-kubernetes.sh", "ClamAV failover", 7),
    ],
)
def test_pilot_acceptance_scripts_are_executable_and_help_is_side_effect_free(
    name: str, help_fragment: str, embedded_python_blocks: int
) -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / name
    bash = shutil.which("bash")

    assert bash is not None
    assert os.access(script, os.X_OK)
    syntax = subprocess.run(  # noqa: S603 - Bash path and syntax-check arguments are controlled.
        [bash, "-n", str(script)], cwd=root, check=False, capture_output=True, text=True
    )
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(  # noqa: S603 - Bash path and help arguments are controlled.
        [bash, str(script), "--help"], cwd=root, check=False, capture_output=True, text=True
    )
    assert help_result.returncode == 0, help_result.stderr
    assert help_fragment in " ".join(help_result.stdout.split())
    embedded = re.findall(r"<<'PY'\n(.*?)\nPY\n", script.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert len(embedded) == embedded_python_blocks
    for index, source in enumerate(embedded):
        compile(source, f"{name}:heredoc:{index}", "exec")
