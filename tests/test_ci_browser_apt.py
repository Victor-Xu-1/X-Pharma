from pathlib import Path

import pytest

from scripts.ci_browser_apt import ARCHIVE, canonical_mirrors, configure_ci_archive

RUNNER = {"GITHUB_ACTIONS": "true", "RUNNER_OS": "Linux"}
UBUNTU = 'ID=ubuntu\nVERSION_ID="24.04"\n'


def test_browser_clients_prepare_explicit_official_https_transport() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    preparation = workflow.index("python3 scripts/ci_browser_apt.py")
    installation = workflow.index("playwright install-deps chrome")
    assert preparation < installation
    font_install = 'sudo apt-get install --yes --no-install-recommends "$BROWSER_FONT_PACKAGE=$BROWSER_FONT_VERSION"'
    assert font_install in workflow
    assert "verify_browser_fonts" in workflow
    assert "inputs.refresh_visual_baselines && 60 || 45" in workflow


def test_selects_the_official_archive_without_altering_other_mirrors_or_priorities() -> None:
    original = (
        "# Controlled mirror list\n"
        "http://azure.archive.ubuntu.com/ubuntu/\tpriority:1\n"
        "https://security.ubuntu.com/ubuntu\tpriority:2\n"
    )
    assert canonical_mirrors(original) == original.replace("http://azure.archive.ubuntu.com/ubuntu", ARCHIVE)


def test_official_transport_is_idempotent() -> None:
    original = f"{ARCHIVE}\tpriority:1\n"
    assert canonical_mirrors(original) == original


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "# http://azure.archive.ubuntu.com/ubuntu\n",
        "http://other.example/ubuntu\n",
        "http://azure.archive.ubuntu.com/ubuntu.evil\n",
    ],
)
def test_unreviewed_mirror_profiles_fail_closed(contents: str) -> None:
    with pytest.raises(ValueError, match="explicit review"):
        canonical_mirrors(contents)


@pytest.mark.parametrize(
    "environment",
    [{}, {"GITHUB_ACTIONS": "false", "RUNNER_OS": "Linux"}, {"GITHUB_ACTIONS": "true", "RUNNER_OS": "Windows"}],
)
def test_cannot_modify_a_local_or_non_linux_host(tmp_path: Path, environment: dict[str, str]) -> None:
    missing = tmp_path / "not-created"
    with pytest.raises(ValueError, match="restricted"):
        configure_ci_archive(missing, environment, UBUNTU)
    assert not missing.exists()


@pytest.mark.parametrize("release", ['ID=ubuntu\nVERSION_ID="22.04"\n', 'ID=debian\nVERSION_ID="24.04"\n'])
def test_runner_distribution_drift_requires_review(tmp_path: Path, release: str) -> None:
    with pytest.raises(ValueError, match="reviewed Ubuntu"):
        configure_ci_archive(tmp_path / "missing", RUNNER, release)


def test_atomically_updates_only_the_owned_list_and_preserves_mode(tmp_path: Path) -> None:
    mirrors = tmp_path / "apt-mirrors.txt"
    mirrors.write_text("http://azure.archive.ubuntu.com/ubuntu\tpriority:1\n")
    mirrors.chmod(0o644)
    unrelated = tmp_path / "preserved.txt"
    unrelated.write_text("unrelated")
    assert configure_ci_archive(mirrors, RUNNER, UBUNTU)
    assert mirrors.read_text() == f"{ARCHIVE}\tpriority:1\n"
    assert mirrors.stat().st_mode & 0o777 == 0o644
    assert unrelated.read_text() == "unrelated"
    assert not configure_ci_archive(mirrors, RUNNER, UBUNTU)
    assert not list(tmp_path.glob(".x-pharma-browser-mirror-*"))


def test_does_not_follow_a_mirror_list_symlink(tmp_path: Path) -> None:
    original = tmp_path / "original"
    original.write_text("http://azure.archive.ubuntu.com/ubuntu\n")
    linked = tmp_path / "linked"
    linked.symlink_to(original)
    with pytest.raises(ValueError, match="regular file"):
        configure_ci_archive(linked, RUNNER, UBUNTU)
    assert original.read_text() == "http://azure.archive.ubuntu.com/ubuntu\n"
