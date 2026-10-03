from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pharma_intel import __version__
from pharma_intel.config import Settings
from pharma_intel.platform.environment import environment_plan, read_host_report
from pharma_intel.platform.environment_host import command_output, workspace_path
from pharma_intel.platform.environment_recipes import create_plan, plan_digest, recipe_commands
from pharma_intel.schemas.environment import EnvironmentPlanCreate, EnvironmentProbeRead, HostEnvironmentRead


def host_report(at: datetime | None = None) -> HostEnvironmentRead:
    return HostEnvironmentRead(
        generated_at=at or datetime.now(UTC),
        product_version=__version__,
        revision="a" * 40,
        clean_source=True,
        manifest_sha256="b" * 64,
        probes=[
            EnvironmentProbeRead(
                id="pnpm",
                label="pnpm",
                scope="host",
                status="mismatch",
                observed="12.8.1",
                expected="pnpm@11.7.0",
                detail="Observed host version differs from the project declaration",
            )
        ],
        disk_free_bytes=4 * 1024**3,
        disk_total_bytes=8 * 1024**3,
    )


def test_plan_binds_source_and_uses_declared_pnpm_not_unpinned_host_default() -> None:
    plan = create_plan(host_report(), recipe_id="frontend-dependencies", offline=True, package_manager="pnpm@11.7.0")
    serialized = plan.model_dump(mode="json")
    assert plan.plan_id == plan_digest({key: value for key, value in serialized.items() if key != "plan_id"})
    assert plan.commands == [
        ["corepack", "pnpm@11.7.0", "--dir", "apps/web", "install", "--frozen-lockfile", "--offline"]
    ]
    assert plan.revision == "a" * 40 and plan.manifest_sha256 == "b" * 64
    assert plan.expires_at - plan.generated_at == timedelta(hours=24)


@pytest.mark.parametrize("manager", ["pnpm@latest", "pnpm@11.7.0;rm -rf /", "npm@11.7.0", "pnpm@11.7.0 --online"])
def test_untrusted_package_manager_is_rejected(manager: str) -> None:
    with pytest.raises(ValueError, match="authoritative"):
        recipe_commands("frontend-dependencies", offline=True, package_manager=manager)


def test_dirty_source_cannot_generate_an_executable_plan() -> None:
    with pytest.raises(ValueError, match="clean source"):
        create_plan(
            host_report().model_copy(update={"clean_source": False}),
            recipe_id="deployment-tools",
            offline=True,
            package_manager="pnpm@11.7.0",
        )


def test_missing_invalid_stale_and_current_reports_are_not_conflated(tmp_path: Path) -> None:
    assert read_host_report(None)[0] == "not_configured"
    assert read_host_report(tmp_path)[0] == "missing"
    report = tmp_path / "environment" / "host.json"
    report.parent.mkdir()
    report.write_text("not-json", encoding="utf-8")
    assert read_host_report(tmp_path)[0] == "invalid"
    report.write_text(host_report(datetime.now(UTC) - timedelta(days=2)).model_dump_json(), encoding="utf-8")
    assert read_host_report(tmp_path)[0] == "stale"
    report.write_text(host_report().model_dump_json(), encoding="utf-8")
    assert read_host_report(tmp_path)[0] == "current"
    settings = Settings(_env_file=None).model_copy(update={"platform_evidence_root": tmp_path})
    assert environment_plan(settings, EnvironmentPlanCreate(recipe_id="frontend-dependencies")).offline


def test_report_symlink_and_oversize_are_rejected(tmp_path: Path) -> None:
    folder = tmp_path / "environment"
    folder.mkdir()
    report = folder / "host.json"
    original = tmp_path / "private.json"
    original.write_text(host_report().model_dump_json(), encoding="utf-8")
    report.symlink_to(original)
    assert read_host_report(tmp_path)[0] == "invalid"
    report.unlink()
    report.write_bytes(b"x" * (256 * 1024 + 1))
    assert read_host_report(tmp_path)[0] == "invalid"


def test_version_mismatch_blocks_installation_plan(tmp_path: Path) -> None:
    target = tmp_path / "environment" / "host.json"
    target.parent.mkdir()
    target.write_text(host_report().model_copy(update={"product_version": "9.0.0"}).model_dump_json(), encoding="utf-8")
    settings = Settings(_env_file=None).model_copy(update={"platform_evidence_root": tmp_path})
    with pytest.raises(ValueError, match="有效主机"):
        environment_plan(settings, EnvironmentPlanCreate(recipe_id="python-dependencies"))


@pytest.mark.parametrize(
    "command",
    [["bash", "-c", "touch /tmp/not-allowed"], ["docker", "stop", "other-project"], ["git", "reset", "--hard"]],
)
def test_detection_never_executes_an_arbitrary_or_mutating_command(command: list[str]) -> None:
    with pytest.raises(ValueError, match="read-only"):
        command_output(command)


@pytest.mark.parametrize("path", ["/", "/mnt/c/project", "/home/user/project", "/srv/wsl"])
def test_environment_management_cannot_migrate_outside_approved_e_drive_workspace(path: str) -> None:
    with pytest.raises(ValueError, match="approved"):
        workspace_path(Path(path))
