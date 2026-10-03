from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.browser_visual_profile import verify_profile
from scripts.reference_visual_pair import ReferenceVisualPairError

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "apps/web/e2e/visual-baselines/manifest.json"


def test_matching_chrome_is_only_a_profile_check_not_release_evidence() -> None:
    browser = json.loads(MANIFEST.read_text(encoding="utf-8"))["browser"]
    result = verify_profile(ROOT, browser=browser)
    assert result["status"] == "ready"
    assert result["scope"] == "browser-visual-profile-only"
    assert result["is_release_evidence"] is False
    assert result["review_update"] is False


def test_chrome_patch_drift_fails_unless_reference_review_is_explicit() -> None:
    with pytest.raises(ReferenceVisualPairError, match="Chrome/reference version drift"):
        verify_profile(ROOT, browser="Google Chrome 0.0.0.0")
    result = verify_profile(ROOT, browser="Google Chrome 0.0.0.0", review_update=True)
    assert result["review_update"] is True
    assert result["is_release_evidence"] is False


@pytest.mark.parametrize("target", ["edge-current", "edge-previous"])
def test_edge_compares_with_chrome_references_but_cannot_review_them(target: str) -> None:
    assert verify_profile(ROOT, browser="Microsoft Edge 1.2.3.4", target=target)["status"] == "ready"
    with pytest.raises(ReferenceVisualPairError, match="Only Google Chrome"):
        verify_profile(ROOT, browser="Microsoft Edge 1.2.3.4", target=target, review_update=True)


@pytest.mark.parametrize("browser", ["Google Chrome 154", "Chromium 154.0.0.0", "Google Chrome 1.2.3.4; bad"])
def test_profile_rejects_invalid_or_wrong_product_versions(browser: str) -> None:
    with pytest.raises(ReferenceVisualPairError, match="invalid product/version"):
        verify_profile(ROOT, browser=browser)


def test_review_does_not_bypass_unsafe_manifest_metadata(tmp_path: Path) -> None:
    directory = tmp_path / "apps/web/e2e/visual-baselines"
    directory.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["contains_production_data"] = True
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ReferenceVisualPairError, match="unsupported or unsafe contract"):
        verify_profile(tmp_path, browser=manifest["browser"], review_update=True)


def _invoke_runner(
    tmp_path: Path,
    runner: Path,
    browser: str,
    *,
    extra_args: tuple[str, ...] = (),
    tenant_slug: str | None = "browser-profile-test",
) -> subprocess.CompletedProcess[str]:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    scripts = {
        "fc-match": '#!/usr/bin/env bash\nprintf "%s" "$2"\n',
        "docker": '#!/usr/bin/env bash\nprintf "owned Docker boundary reached\\n" >&2\nexit 73\n',
        "test-chrome": f'#!/usr/bin/env bash\nprintf "%s\\n" "{browser}"\n',
    }
    for name, body in scripts.items():
        executable = binaries / name
        executable.write_text(body, encoding="utf-8")
        executable.chmod(0o700)
    bash = shutil.which("bash")
    assert bash is not None
    environment = {
        **os.environ,
        "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
        "COMPOSE_FILE": "owned-fixture",
        "E2E_BROWSER_EXECUTABLE": str(binaries / "test-chrome"),
    }
    environment.pop("PHARMA_BROWSER_TENANT_SLUG", None)
    if tenant_slug is not None:
        environment["PHARMA_BROWSER_TENANT_SLUG"] = tenant_slug
    return subprocess.run(  # noqa: S603 - fixed runner; controlled font/browser/Docker boundary fixtures.
        [bash, str(runner), *extra_args],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("tenant_slug", [None, "", "unsafe/organization"])
def test_runner_rejects_missing_or_unsafe_test_organization_before_docker(
    tmp_path: Path, tenant_slug: str | None
) -> None:
    browser = json.loads(MANIFEST.read_text(encoding="utf-8"))["browser"]
    result = _invoke_runner(tmp_path, ROOT / "scripts/run-browser-acceptance.sh", browser, tenant_slug=tenant_slug)
    assert result.returncode == 2, result.stderr
    assert "PHARMA_BROWSER_TENANT_SLUG must explicitly name an active test organization" in result.stderr
    assert "owned Docker boundary reached" not in result.stderr


def test_real_runner_rejects_version_drift_before_any_docker_fixture(tmp_path: Path) -> None:
    result = _invoke_runner(tmp_path, ROOT / "scripts/run-browser-acceptance.sh", "Google Chrome 0.0.0.0")
    assert result.returncode == 2, result.stderr
    assert "Chrome/reference version drift" in result.stderr
    assert "owned Docker boundary reached" not in result.stderr


def test_matching_runtime_in_a_spaced_path_reaches_the_expected_docker_boundary(tmp_path: Path) -> None:
    spaced = tmp_path / "runtime with spaces"
    spaced.mkdir()
    browser = json.loads(MANIFEST.read_text(encoding="utf-8"))["browser"]
    result = _invoke_runner(spaced, ROOT / "scripts/run-browser-acceptance.sh", browser)
    assert result.returncode == 73, result.stderr
    assert "owned Docker boundary reached" in result.stderr


def test_explicit_fixture_recovery_does_not_require_a_matching_browser(tmp_path: Path) -> None:
    result = _invoke_runner(
        tmp_path,
        ROOT / "scripts/run-browser-acceptance.sh",
        "Google Chrome 0.0.0.0",
        extra_args=("--recover-interrupted-run",),
    )
    assert result.returncode == 73, result.stderr
    assert "owned Docker boundary reached" in result.stderr
    assert "Chrome/reference version drift" not in result.stderr


def test_cli_rejects_drift_with_an_actionable_error() -> None:
    result = subprocess.run(  # noqa: S603 - fixed Python CLI with a deliberately mismatched version.
        [sys.executable, "-m", "scripts.browser_visual_profile", "--browser", "Google Chrome 0.0.0.0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "references are never updated automatically" in result.stderr


def test_ci_and_local_runner_share_the_same_preflight_owner() -> None:
    runner = (ROOT / "scripts/run-browser-acceptance.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    helper = (ROOT / "scripts/lib/browser_runtime.sh").read_text(encoding="utf-8")
    assert "scripts.browser_visual_profile" in helper
    assert "scripts.browser_visual_profile" in workflow
    assert runner.count("resolve_browser_runtime\n") == 1
    assert runner.index("verify_browser_visual_profile\n") < runner.index("api_container_id=$(")
    assert 'browser_product="Google Chrome"' not in runner
