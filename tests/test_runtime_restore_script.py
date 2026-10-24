from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
POSTGRES_ID = "sha256:" + "1" * 64
API_ID = "sha256:" + "2" * 64
CANDIDATE_ID = "sha256:" + "3" * 64


def _run_restore(*arguments: str, script: str = "restore-smoke-linux.sh") -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603 - The executable and local script are controlled.
        [bash, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


@pytest.fixture
def restore_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    backup = tmp_path / "backup"
    backup.mkdir()
    names = [
        "postgres.dump",
        "postgres-globals.sql",
        "temporal.dump",
        "temporal-visibility.dump",
        "object-store.tar.gz",
        "markdown-wiki.tar.gz",
    ]
    checksums = []
    for name in names:
        payload = f"controlled preflight fixture: {name}\n".encode()
        (backup / name).write_bytes(payload)
        checksums.append(f"{hashlib.sha256(payload).hexdigest()}  {name}\n")
    (backup / "checksums.sha256").write_text("".join(checksums), encoding="utf-8")
    (backup / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "database": "pharma_intel",
                "authority": names,
                "rowCounts": {"public.alembic_version": 1},
                "alembicHead": "abc123",
                "postgresImage": "backup-postgres",
                "postgresImageId": POSTGRES_ID,
                "apiImage": "backup-api",
                "apiImageId": API_ID,
            }
        ),
        encoding="utf-8",
    )
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    docker = bin_directory / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >> "$RESTORE_DOCKER_TRACE"\n'
        'case "$1:$2:${3:-}" in\n'
        "  version:--format:*) exit 0 ;;\n"
        "  compose:*)\n"
        '    case "${RESTORE_CLEAN_TARGET_MODE:-normal}" in\n'
        "      compose-failure) exit 18 ;;\n"
        "      existing-containers) printf 'controlled-existing-container\\n' ;;\n"
        "    esac ;;\n"
        f"  image:inspect:backup-postgres) printf '%s\\n' '{POSTGRES_ID}' ;;\n"
        f"  image:inspect:backup-api) printf '%s\\n' '{API_ID}' ;;\n"
        f"  image:inspect:{POSTGRES_ID}) printf '%s\\n' '{POSTGRES_ID}' ;;\n"
        f"  image:inspect:{API_ID}) printf '%s\\n' '{API_ID}' ;;\n"
        "  image:inspect:busybox:*) exit 0 ;;\n"
        f"  image:inspect:{CANDIDATE_ID})\n"
        '    case "${RESTORE_CANDIDATE_MODE:-present}" in\n'
        "      missing) exit 1 ;;\n"
        f"      nonzero-with-match) printf '%s\\n' '{CANDIDATE_ID}'; exit 17 ;;\n"
        "      mismatch) printf 'sha256:%064d\\n' 4 ;;\n"
        f"      *) printf '%s\\n' '{CANDIDATE_ID}' ;;\n"
        "    esac ;;\n"
        "  volume:ls:*)\n"
        "    [[ ${RESTORE_CLEAN_TARGET_MODE:-normal} != volume-inventory-failure ]] || exit 19\n"
        "    if [[ ${RESTORE_CLEAN_TARGET_MODE:-normal} == existing-volume "
        '&& $* == *"name=^$RESTORE_CLEAN_VOLUME$"* ]]; then\n'
        '      printf "%s\\n" "$RESTORE_CLEAN_VOLUME"\n'
        "    fi ;;\n"
        "  volume:create:*) exit 86 ;;\n"
        "  create:*) exit 89 ;;\n"
        "  container:ls:*) exit 0 ;;\n"
        "  rm:-f:*|volume:rm:-f) exit 0 ;;\n"
        "  *) exit 87 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    trace = tmp_path / "docker-argv.txt"
    monkeypatch.setenv("RESTORE_DOCKER_TRACE", str(trace))
    monkeypatch.setenv("PATH", str(bin_directory) + os.pathsep + os.environ["PATH"])
    return backup, trace


@pytest.mark.parametrize("script", ["restore-smoke-linux.sh", "verify-local-backup-restore.sh"])
@pytest.mark.parametrize(
    "image", ["postgres:latest", "sha256:abc", "sha256:" + "A" * 64, "sha256:" + "1" * 64 + ";true"]
)
def test_rejects_mutable_or_malformed_target_before_docker(
    restore_preflight: tuple[Path, Path], script: str, image: str
) -> None:
    backup, trace = restore_preflight
    arguments = (str(backup),) if script == "restore-smoke-linux.sh" else ()
    result = _run_restore(*arguments, "--postgres-image-id", image, script=script)
    assert result.returncode == 2
    assert "immutable" in result.stderr
    assert not trace.exists()


def test_default_restore_keeps_both_original_manifest_identity_checks(restore_preflight: tuple[Path, Path]) -> None:
    backup, trace = restore_preflight
    result = _run_restore(str(backup))
    assert result.returncode == 86
    calls = trace.read_text(encoding="utf-8").splitlines()
    assert calls[0].startswith("image inspect backup-postgres ")
    assert calls[1].startswith("image inspect backup-api ")
    assert calls[2].startswith("volume create pharma-restore-smoke-postgres-")


def test_target_is_inspected_locally_before_creating_restore_resources(restore_preflight: tuple[Path, Path]) -> None:
    backup, trace = restore_preflight
    result = _run_restore(str(backup), "--postgres-image-id", CANDIDATE_ID)
    assert result.returncode == 86
    calls = trace.read_text(encoding="utf-8").splitlines()
    assert calls[0].startswith("image inspect backup-postgres ")
    assert calls[1].startswith("image inspect backup-api ")
    assert calls[2].startswith(f"image inspect {CANDIDATE_ID} ")
    assert calls[3].startswith("volume create pharma-restore-smoke-postgres-")
    assert not any(call.startswith("pull ") for call in calls)


@pytest.mark.parametrize("mode", ["missing", "mismatch"])
def test_missing_or_wrong_target_never_creates_resources(
    restore_preflight: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    backup, trace = restore_preflight
    monkeypatch.setenv("RESTORE_CANDIDATE_MODE", mode)
    result = _run_restore(str(backup), "--postgres-image-id", CANDIDATE_ID)
    assert result.returncode != 0
    calls = trace.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 3
    assert all(call.startswith("image inspect ") for call in calls)


def test_restore_runs_only_exact_local_images_and_probes_the_actual_cartridge() -> None:
    source = (ROOT / "scripts" / "restore-smoke-linux.sh").read_text(encoding="utf-8")
    runs = [line for line in source.splitlines() if "docker run " in line]
    assert len(runs) == 2
    assert all("--pull=never" in line for line in runs)
    assert '"$restored_postgres_image_id" >/dev/null' in runs[0]
    assert '"$api_image_id" pharma-verify-rls' in runs[1]
    assert '--name "$probe_container"' in runs[1] and "--rm" not in runs[1]
    archive_runs = [line for line in source.splitlines() if "run_runtime_archive " in line]
    assert len(archive_runs) == 2
    library = (ROOT / "scripts/lib/runtime_archive_container.sh").read_text()
    assert "--pull=never --network none --read-only" in library
    assert "busybox:1.36.1@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662" in library
    assert "--rm" not in library
    assert "SELECT mol_to_smiles(mol_from_smiles('CCO'))" in source
    assert '[[ "$rdkit_probe" == CCO ]]' in source
    assert '"backup_postgres_image_id": backup_postgres' in source
    assert '"restored_postgres_image_id": restored_postgres' in source


def test_release_backup_verifies_target_before_quiescing_and_preserves_restore_identity() -> None:
    source = (ROOT / "scripts" / "verify-local-backup-restore.sh").read_text(encoding="utf-8")
    assert source.index('runtime_backup_docker 5 image inspect "$postgres_image_id"') < source.index(
        'runtime_backup_quiesce "$project_name"'
    )
    assert 'restore_arguments+=(--postgres-image-id "$postgres_image_id")' in source
    assert 'python3 "$root/scripts/lib/runtime_backup_report.py"' in source
    report_source = (ROOT / "scripts/lib/runtime_backup_report.py").read_text(encoding="utf-8")
    assert '"rdkit_function_probe": restore["rdkit_function_probe"]' in report_source
    assert '"restored_postgres_image_id": restore["restored_postgres_image_id"]' in report_source
    assert '"rdkit_function_probe": restore["rdkit_function_probe"]' not in source
    probe = source.index('run_runtime_archive "pharma-backup-archive-$started_epoch-$$-object-probe"')
    assert source.index('runtime_backup_docker 5 image inspect "$postgres_image_id"') < probe
    assert (
        probe < source.index("runtime_backup_lifecycle_init") < source.index('runtime_backup_quiesce "$project_name"')
    )
    owner = (ROOT / "scripts/lib/runtime_backup_lifecycle.sh").read_text(encoding="utf-8")
    assert owner.index("systemd-run --user") < owner.index(
        'runtime_backup_docker 15 pause "${backup_lifecycle_ids[@]}"'
    )
    assert '"$(command -v timeout)" --kill-after=2s 30s "$(command -v docker)" unpause' in owner


def test_failed_target_inspection_cannot_accept_matching_stdout(
    restore_preflight: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, trace = restore_preflight
    monkeypatch.setenv("RESTORE_CANDIDATE_MODE", "nonzero-with-match")
    result = _run_restore("--postgres-image-id", CANDIDATE_ID, script="verify-local-backup-restore.sh")
    assert result.returncode != 0
    assert trace.read_text().splitlines() == [f"image inspect {CANDIDATE_ID} --format {{{{.Id}}}}"]


def test_unhealthy_archive_infrastructure_rejects_fresh_backup_before_any_writer_pause(
    restore_preflight: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    backup, trace = restore_preflight
    monkeypatch.setenv("TMPDIR", str(backup.parent))
    report = backup.parent / "unpublished-report.json"
    result = _run_restore(
        "--project-name",
        "x-pharma-architecture",
        "--quiesce-runtime",
        "--postgres-image-id",
        CANDIDATE_ID,
        "--output",
        str(report),
        script="verify-local-backup-restore.sh",
    )
    assert result.returncode == 89
    calls = trace.read_text().splitlines()
    assert calls[0].startswith(f"image inspect {CANDIDATE_ID}")
    assert calls[1].startswith("create --pull=never --network none --read-only")
    assert not any(call.startswith("pause ") or call.startswith("compose ") for call in calls)
    assert not report.exists()
    assert not list(backup.parent.glob("pharma-archive.*"))


def test_restore_requires_bounded_explicit_resource_cleanup_before_reporting_success() -> None:
    source = (ROOT / "scripts" / "restore-smoke-linux.sh").read_text(encoding="utf-8")
    assert 'probe_container="$container-rls"' in source
    assert 'timeout --kill-after=10s 120s docker run --pull=never --name "$probe_container"' in source
    assert source.index("cleanup || {") < source.index('python3 - "$backup" "$tables_verified"')
    assert 'source "$root/scripts/lib/restore_smoke_resources.sh"' in source


def test_restore_workspace_follows_the_explicit_temp_parent_without_a_tmp_only_cleanup() -> None:
    source = (ROOT / "scripts" / "restore-smoke-linux.sh").read_text(encoding="utf-8")
    assert 'temp_parent=$(realpath -e -- "${TMPDIR:-/tmp}")' in source
    assert 'work_dir=$(mktemp -d "$temp_parent/pharma-restore-smoke.XXXXXX")' in source
    assert 'case "$work_dir" in' not in source


def test_clean_target_restore_verifies_owned_cleanup_before_publishing_success() -> None:
    source = (ROOT / "scripts" / "restore-runtime-linux.sh").read_text(encoding="utf-8")
    assert 'source "$root/scripts/lib/runtime_restore_resources.sh"' in source
    assert "runtime_restore_cleanup preserve" in source
    assert source.index("runtime_restore_cleanup preserve") < source.index('"status": "passed"')
    assert "docker volume rm -f" not in source
    assert "docker run --rm" not in source
    assert '"cleanup_verified": True' in source


@pytest.mark.parametrize(
    ("mode", "status"), [("compose-failure", 18), ("volume-inventory-failure", 19), ("existing-containers", 1)]
)
def test_clean_target_inventory_failure_cannot_be_treated_as_an_empty_target(
    restore_preflight: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str, status: int
) -> None:
    backup, trace = restore_preflight
    monkeypatch.setenv("RESTORE_CLEAN_TARGET_MODE", mode)
    monkeypatch.setenv("TMPDIR", str(backup.parent))
    result = _run_restore("--project-name", "restore-fixture", str(backup), script="restore-runtime-linux.sh")
    assert result.returncode == status, result.stderr
    calls = trace.read_text().splitlines()
    assert not any(call.startswith("volume create ") or call.startswith("create ") for call in calls)
    assert "restore_status=passed" not in result.stdout


@pytest.mark.parametrize(
    "volume_key",
    [
        "pharma_postgres18_data",
        "pharma_object_store",
        "pharma_markdown_wiki",
        "pharma_redis_data",
        "pharma_opensearch_data",
    ],
)
def test_clean_target_preserves_every_preexisting_authority_or_projection_volume(
    restore_preflight: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, volume_key: str
) -> None:
    backup, trace = restore_preflight
    volume = "restore-fixture_" + volume_key
    monkeypatch.setenv("RESTORE_CLEAN_TARGET_MODE", "existing-volume")
    monkeypatch.setenv("RESTORE_CLEAN_VOLUME", volume)
    monkeypatch.setenv("TMPDIR", str(backup.parent))
    result = _run_restore("--project-name", "restore-fixture", str(backup), script="restore-runtime-linux.sh")
    assert result.returncode == 1 and "refusing to overwrite" in result.stderr
    calls = trace.read_text().splitlines()
    assert not any(
        call.startswith("volume create ") or call.startswith("create ") or call.startswith("volume rm ")
        for call in calls
    )
    assert "restore_status=passed" not in result.stdout
