from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.release import version_workflow
from scripts.release.version_generation import VERSION_PATHS, command, unchanged_dependencies
from scripts.release.version_github import GitHubRepository
from scripts.release.version_manifest import read_state
from tests.test_product_versioning import manifest_fixture


class MetadataRepository(GitHubRepository):
    def __init__(self, answers: dict[str, Any]) -> None:
        super().__init__("example/X-Pharma")
        self.answers = answers
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, payload))
        return self.answers[path]


@pytest.mark.parametrize("merge_kind", ["merge", "squash", "rebase"])
def test_github_merge_receipt_counts_pr_once_not_its_commits(merge_kind: str) -> None:
    # GitHub defines merge_commit_sha as the merge, squash or final rebased main commit.
    sha = "a" * 40
    metadata = {
        "number": 12,
        "merged": True,
        "merge_commit_sha": sha,
        "base": {"ref": "main", "repo": {"full_name": "example/X-Pharma"}},
    }
    github = MetadataRepository(
        {
            f"commits/{sha}/pulls?per_page=100&page=1": [metadata, metadata],
            "pulls/12": metadata,
            f"commits/{'b' * 40}/pulls?per_page=100&page=1": [],
        }
    )
    assert merge_kind in {"merge", "squash", "rebase"}
    assert github.merged_prs(["b" * 40, sha]) == (12,)


@pytest.mark.parametrize(
    "change",
    [
        {"merged": False},
        {"merge_commit_sha": "b" * 40},
        {"base": {"ref": "development", "repo": {"full_name": "example/X-Pharma"}}},
        {"base": {"ref": "main", "repo": {"full_name": "other/X-Pharma"}}},
    ],
)
def test_unmerged_wrong_branch_or_other_repository_prs_are_not_counted(change: dict[str, Any]) -> None:
    sha = "a" * 40
    candidate = {"number": 3, "merge_commit_sha": sha}
    pr = {
        **candidate,
        "merged": True,
        "base": {"ref": "main", "repo": {"full_name": "example/X-Pharma"}},
        **change,
    }
    github = MetadataRepository({f"commits/{sha}/pulls?per_page=100&page=1": [candidate], "pulls/3": pr})
    assert github.merged_prs([sha]) == ()


@pytest.mark.parametrize("existing", ["in_progress", "queued", "success", "failure", "cancelled", "none"])
def test_bot_commit_explicitly_gets_original_ci_without_recursive_version_pr(existing: str) -> None:
    sha = "a" * 40
    runs = (
        []
        if existing == "none"
        else [
            {
                "head_sha": sha,
                "status": existing if existing in {"in_progress", "queued"} else "completed",
                "conclusion": existing,
            }
        ]
    )
    github = MetadataRepository(
        {
            "git/ref/heads/main": {"object": {"sha": sha}},
            f"actions/workflows/ci.yml/runs?head_sha={sha}&per_page=100": {"workflow_runs": runs},
            "actions/workflows/ci.yml/dispatches": None,
        }
    )
    github.ensure_ci(sha)
    dispatched = [payload for path, payload in github.calls if path.endswith("dispatches")]
    assert dispatched == ([{"ref": "main"}] if existing == "none" else [])


def test_ci_dispatch_rejects_concurrent_main_change() -> None:
    github = MetadataRepository({"git/ref/heads/main": {"object": {"sha": "b" * 40}}})
    with pytest.raises(RuntimeError, match="advanced"):
        github.ensure_ci("a" * 40)
    assert len(github.calls) == 1


def synthetic_git_repository(root: Path, origin: Path) -> str:
    root.mkdir()
    command(root, ["git", "init", "--initial-branch=main"])
    command(root, ["git", "config", "user.name", "Version test"])
    command(root, ["git", "config", "user.email", "version@example.invalid"])
    manifest_fixture(root)
    for name in VERSION_PATHS - {"pyproject.toml", "apps/web/package.json"}:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Generated mirror fixture\n")
    command(root, ["git", "add", "."])
    command(root, ["git", "commit", "-m", "Baseline"])
    baseline = command(root, ["git", "rev-parse", "HEAD"])
    manifest = root / "pyproject.toml"
    manifest.write_text(manifest.read_text().replace("a" * 40, baseline))
    command(root, ["git", "add", "."])
    command(root, ["git", "commit", "-m", "Prospective version rule"])
    command(root, ["git", "init", "--bare", str(origin)])
    command(root, ["git", "remote", "add", "origin", str(origin)])
    command(root, ["git", "push", "origin", "HEAD:refs/heads/main"])
    return baseline


class LocalGitHub(GitHubRepository):
    def __init__(self, root: Path, origin: Path, merges: dict[str, tuple[int, ...]]) -> None:
        super().__init__("example/X-Pharma")
        self.root, self.origin, self.merges = root, origin, merges
        self.checked: list[str] = []

    def main_revision(self) -> str:
        return command(self.root, ["git", "--git-dir", str(self.origin), "rev-parse", "refs/heads/main"])

    def merged_prs(self, commits: Sequence[str]) -> tuple[int, ...]:
        return tuple(sorted({number for commit in commits for number in self.merges.get(commit, ())}))

    def ensure_ci(self, revision: str) -> None:
        assert self.main_revision() == revision
        self.checked.append(revision)


def test_real_git_reconcile_rerun_and_batched_merges_are_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, origin = tmp_path / "owned", tmp_path / "origin.git"
    synthetic_git_repository(root, origin)
    head = command(root, ["git", "rev-parse", "HEAD"])
    github = LocalGitHub(root, origin, {head: (1, 2)})
    monkeypatch.setattr(version_workflow, "generate_mirrors", lambda _root: None)
    first = version_workflow.reconcile(root, github)
    assert first["version"] == "0.2.1" and first["increment"] == 2
    second = version_workflow.reconcile(root, github)
    assert second["increment"] == 0 and second["revision"] == first["revision"]
    assert read_state(root).processed_through == head
    assert not command(root, ["git", "status", "--porcelain"])


def test_real_git_concurrent_push_is_rejected_without_overwriting_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, origin = tmp_path / "owned", tmp_path / "origin.git"
    synthetic_git_repository(root, origin)
    head = command(root, ["git", "rev-parse", "HEAD"])
    github = LocalGitHub(root, origin, {head: (1,)})
    other = tmp_path / "other"
    command(tmp_path, ["git", "clone", "--branch=main", str(origin), str(other)])
    command(other, ["git", "config", "user.name", "Concurrent test"])
    command(other, ["git", "config", "user.email", "concurrent@example.invalid"])

    def concurrent_merge(_root: Path) -> None:
        (other / "accepted.txt").write_text("Concurrent main change\n")
        command(other, ["git", "add", "."])
        command(other, ["git", "commit", "-m", "Another accepted PR"])
        command(other, ["git", "push", "origin", "main"])

    monkeypatch.setattr(version_workflow, "generate_mirrors", concurrent_merge)
    with pytest.raises(subprocess.CalledProcessError) as error:
        version_workflow.reconcile(root, github)
    assert "rejected" in error.value.stderr
    assert github.main_revision() == command(other, ["git", "rev-parse", "HEAD"])
    assert not github.checked


@pytest.mark.parametrize("method", ["merge", "squash", "rebase"])
def test_real_first_parent_history_counts_one_pr_for_two_feature_commits(tmp_path: Path, method: str) -> None:
    root, origin = tmp_path / "owned", tmp_path / "origin.git"
    synthetic_git_repository(root, origin)
    cursor = command(root, ["git", "rev-parse", "HEAD"])
    command(root, ["git", "switch", "-c", "feature"])
    for number in (1, 2):
        (root / "feature.txt").write_text(f"Feature step {number}\n")
        command(root, ["git", "add", "feature.txt"])
        command(root, ["git", "commit", "-m", f"Feature step {number}"])
    command(root, ["git", "switch", "main"])
    if method == "merge":
        command(root, ["git", "merge", "--no-ff", "feature", "-m", "Merge accepted PR"])
    elif method == "squash":
        command(root, ["git", "merge", "--squash", "feature"])
        command(root, ["git", "commit", "-m", "Squash accepted PR"])
    else:
        command(root, ["git", "rebase", "feature"])
    head = command(root, ["git", "rev-parse", "HEAD"])
    commits = version_workflow.pending_history(root, cursor, head)
    assert len(commits) == (2 if method == "rebase" else 1)
    github = LocalGitHub(root, origin, {head: (7,)})
    assert github.merged_prs(commits) == (7,)


def test_dirty_checkout_is_never_modified_by_automation(tmp_path: Path) -> None:
    root, origin = tmp_path / "owned", tmp_path / "origin.git"
    synthetic_git_repository(root, origin)
    manifest = root / "pyproject.toml"
    before = manifest.read_text()
    (root / "unfinished.txt").write_text("User work\n")
    with pytest.raises(ValueError, match="clean"):
        version_workflow.reconcile(root, LocalGitHub(root, origin, {}))
    assert manifest.read_text() == before
    assert (root / "unfinished.txt").read_text() == "User work\n"


def test_dependency_versions_are_not_product_versions() -> None:
    before = {"package": [{"name": "x-pharma", "version": "0.1.0", "source": {"editable": "."}}]}
    after = {"package": [{"name": "x-pharma", "version": "0.1.1", "source": {"editable": "."}}]}
    unchanged_dependencies(before, after)
    with pytest.raises(ValueError, match="dependency"):
        unchanged_dependencies(before, {**after, "dependency-resolution": "changed"})


def test_version_workflow_is_trusted_main_only_and_preserves_six_original_gates() -> None:
    root = Path(__file__).parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/product-version.yml").read_text())
    events = workflow.get("on", workflow.get(True))  # PyYAML implements YAML 1.1's `on` boolean spelling.
    assert events["push"]["branches"] == ["main"]
    assert events["schedule"] == [{"cron": "7,22,37,52 * * * *"}]
    assert "pull_request_target" not in events
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["reconcile"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["permissions"] == {"contents": "write", "pull-requests": "read", "actions": "write"}
    assert job["steps"][0]["with"] == {"ref": "main", "fetch-depth": 0}
    ci = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    assert set(ci["jobs"]) == {
        "backend",
        "frontend",
        "postgres-contract",
        "deployment-contract",
        "two-entry-smoke",
        "security-supply-chain",
    }
