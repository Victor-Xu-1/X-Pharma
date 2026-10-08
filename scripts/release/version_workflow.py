"""Reconcile every newly merged main PR once, then request exact-head CI."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from scripts.release.version_generation import VERSION_PATHS, command, generate_mirrors
from scripts.release.version_github import GitHubRepository
from scripts.release.version_manifest import REVISION, read_state, update_manifests


def pending_history(root: Path, cursor: str, head: str) -> tuple[str, ...]:
    for revision in (cursor, head):
        if REVISION.fullmatch(revision) is None:
            raise ValueError("Invalid history revision")
    command(root, ["git", "merge-base", "--is-ancestor", cursor, head])
    ancestry = command(root, ["git", "rev-list", "--first-parent", "--max-count=1001", head]).splitlines()
    if cursor not in ancestry:
        raise ValueError("Version cursor is not in the bounded first-parent main history")
    commits = tuple(reversed(ancestry[: ancestry.index(cursor)]))
    if len(commits) > 1000:
        raise ValueError("Pending history exceeds its bound; no partial increment is allowed")
    return commits


def reconcile(root: Path, github: GitHubRepository) -> dict[str, object]:
    if command(root, ["git", "status", "--porcelain=v1", "--untracked-files=all"]):
        raise ValueError("Automatic versioning requires a clean owned checkout")
    head = command(root, ["git", "rev-parse", "HEAD"])
    if github.main_revision() != head:
        raise ValueError("Automatic versioning must start from current GitHub main")
    state = read_state(root)
    numbers = github.merged_prs(pending_history(root, state.processed_through, head))
    updated = update_manifests(root, head, len(numbers))
    if numbers:
        generate_mirrors(root)
        command(root, ["git", "add", "--", *sorted(VERSION_PATHS)])
        command(root, ["git", "diff", "--cached", "--check"])
        summary = ", ".join(f"#{number}" for number in numbers)
        command(root, ["git", "commit", "-m", f"chore(version): v{updated} after merged PRs {summary}"])
        # Non-fast-forward rejection is intentional. Never force, reset or overwrite a concurrent merge.
        command(root, ["git", "push", "origin", "HEAD:refs/heads/main"])
        head = command(root, ["git", "rev-parse", "HEAD"])
    github.ensure_ci(head)
    return {"version": updated, "increment": len(numbers), "merged_prs": numbers, "revision": head}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    arguments = parser.parse_args()
    try:
        result = reconcile(Path(__file__).resolve().parents[2], GitHubRepository(arguments.repository))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"Version reconciliation failed: {exc}\n")
    except (OSError, subprocess.SubprocessError) as exc:
        # Do not print subprocess arguments, environment or credential-bearing Git configuration.
        parser.exit(1, f"Version reconciliation failed ({type(exc).__name__}); no forced recovery attempted\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
