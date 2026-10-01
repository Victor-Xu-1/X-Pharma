from __future__ import annotations

import shutil
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from scripts.release.contracts.core import COMMIT_PATTERN
from scripts.release.records import ReleaseEvidenceError, RepositorySubject
from scripts.source_tree_manifest import build_source_tree_manifest


def _git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("git")
    if executable is None:
        raise ReleaseEvidenceError("git executable is unavailable")
    try:
        return subprocess.run(  # noqa: S603 - executable is resolved and arguments are never passed to a shell.
            [executable, "-C", str(repo), *arguments],
            check=check,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            detail = exc.stderr.decode(errors="replace").strip()
        raise ReleaseEvidenceError(f"git command failed{f': {detail}' if detail else ''}") from exc


def repository_subject(repo: Path) -> RepositorySubject:
    try:
        resolved_repo = repo.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("repository does not exist") from exc
    if not resolved_repo.is_dir():
        raise ReleaseEvidenceError("repository must be a directory")

    root = Path(_git(resolved_repo, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if root != resolved_repo:
        raise ReleaseEvidenceError(f"repository argument must be the Git root: {root}")
    status_output = _git(root, "-c", "core.quotepath=false", "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status_output:
        raise ReleaseEvidenceError("release evidence requires a clean Git worktree")
    commit = _git(root, "rev-parse", "--verify", "HEAD").stdout.decode().strip()
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ReleaseEvidenceError("repository HEAD is not a valid immutable commit")

    tracked = [item for item in _git(root, "ls-files", "-z").stdout.split(b"\0") if item]
    with tempfile.TemporaryDirectory(prefix="pharma-release-source-") as temporary:
        staging = Path(temporary)
        for raw_path in tracked:
            try:
                relative_text = raw_path.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ReleaseEvidenceError("tracked file path is not UTF-8") from exc
            relative = PurePosixPath(relative_text)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ReleaseEvidenceError(f"unsafe tracked file path: {relative_text}")
            source = root.joinpath(*relative.parts)
            try:
                mode = source.lstat().st_mode
            except OSError as exc:
                raise ReleaseEvidenceError(f"cannot inspect tracked file: {relative_text}") from exc
            if stat.S_ISLNK(mode):
                raise ReleaseEvidenceError(f"release source does not accept symbolic links: {relative_text}")
            if not stat.S_ISREG(mode):
                raise ReleaseEvidenceError(f"tracked path is not a regular file: {relative_text}")
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        tree = build_source_tree_manifest(staging)
    tags = tuple(sorted(_git(root, "tag", "--points-at", "HEAD").stdout.decode().splitlines()))
    return RepositorySubject(commit, tree.file_count, tree.sha256, tags)


def _check_release_tag(repo: Path, subject: RepositorySubject, release_tag: str | None, required: bool) -> str | None:
    if release_tag is not None:
        valid_reference = _git(repo, "check-ref-format", f"refs/tags/{release_tag}", check=False)
        if valid_reference.returncode != 0:
            raise ReleaseEvidenceError("release tag is not a valid Git reference")
    if not required:
        if release_tag is not None and release_tag not in subject.tags:
            raise ReleaseEvidenceError("release tag does not point at the current commit")
        return release_tag
    if not release_tag or release_tag not in subject.tags:
        raise ReleaseEvidenceError("production evidence requires a release tag at the current commit")
    tag_type = _git(repo, "cat-file", "-t", f"refs/tags/{release_tag}").stdout.decode().strip()
    if tag_type != "tag":
        raise ReleaseEvidenceError("production evidence requires an annotated signed Git tag")
    verification = _git(repo, "verify-tag", "--", release_tag, check=False)
    if verification.returncode != 0:
        raise ReleaseEvidenceError("production evidence requires a cryptographically verified Git tag")
    return release_tag
