"""Bounded GitHub metadata access; credentials stay in the Actions environment."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from typing import Any

from scripts.release.version_manifest import REVISION


class GitHubRepository:
    def __init__(self, name: str) -> None:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) is None:
            raise ValueError("Invalid GitHub repository")
        self.name = name

    def request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        args = ["gh", "api", f"repos/{self.name}/{path}"]
        body = None
        if payload is not None:
            args.extend(["--method", "POST", "--input", "-"])
            body = json.dumps(payload)
        result = subprocess.run(  # noqa: S603 -- fixed executable; no shell or token arguments
            args, input=body, text=True, capture_output=True, timeout=60, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(f"GitHub metadata request failed for {path}; no version is published by this request")
        return json.loads(result.stdout) if result.stdout.strip() else None

    def merged_prs(self, commits: Sequence[str]) -> tuple[int, ...]:
        found: set[int] = set()
        for commit in commits:
            if REVISION.fullmatch(commit) is None:
                raise ValueError("Invalid history revision")
            for page in range(1, 11):
                candidates = self.request(f"commits/{commit}/pulls?per_page=100&page={page}")
                if not isinstance(candidates, list):
                    raise ValueError("Invalid associated pull request response")
                for candidate in candidates:
                    if not isinstance(candidate, dict) or candidate.get("merge_commit_sha") != commit:
                        continue
                    number = candidate.get("number")
                    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                        raise ValueError("Invalid pull request number")
                    pr = self.request(f"pulls/{number}")
                    if not isinstance(pr, dict):
                        raise ValueError("Invalid merged pull request response")
                    base = pr.get("base", {})
                    if (
                        pr.get("merged") is True
                        and pr.get("number") == number
                        and pr.get("merge_commit_sha") == commit
                        and isinstance(base, dict)
                        and base.get("ref") == "main"
                        and isinstance(base.get("repo"), dict)
                        and base["repo"].get("full_name") == self.name
                    ):
                        found.add(number)
                if len(candidates) < 100:
                    break
            else:
                raise RuntimeError("Pull request pagination exceeded its bound; cursor not advanced")
        return tuple(sorted(found))

    def main_revision(self) -> str:
        ref = self.request("git/ref/heads/main")
        revision = ref.get("object", {}).get("sha") if isinstance(ref, dict) else None
        if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
            raise ValueError("Invalid GitHub main revision")
        return revision

    def ensure_ci(self, revision: str) -> None:
        if self.main_revision() != revision:
            raise RuntimeError("Main advanced before CI dispatch; the next version run must reconcile it")
        result = self.request(f"actions/workflows/ci.yml/runs?head_sha={revision}&per_page=100")
        runs = result.get("workflow_runs") if isinstance(result, dict) else None
        if not isinstance(runs, list):
            raise ValueError("Invalid CI runs response")
        if any(
            isinstance(run, dict)
            and run.get("head_sha") == revision
            and (
                run.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}
                or run.get("status") == "completed"
            )
            for run in runs
        ):
            # A terminal failure is evidence, not permission for unbounded scheduled CI retries.
            return
        # GITHUB_TOKEN pushes do not start push workflows. Explicit dispatch preserves all six original gates.
        self.request("actions/workflows/ci.yml/dispatches", {"ref": "main"})
