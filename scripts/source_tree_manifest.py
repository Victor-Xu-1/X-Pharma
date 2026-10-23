from __future__ import annotations

import argparse
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

HASH_DOMAIN = b"pharma-intelligence-source-tree-v1\0"
POSTGRES_BUILD_INPUTS = (
    "deploy/postgres-rdkit.Dockerfile",
    "deploy/security/debian13-runtime-packages.lock",
    "deploy/security/install-runtime-security-packages.sh",
)


class SourceTreeManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceTreeManifest:
    file_count: int
    sha256: str


def _selected_paths(root: Path, relative_paths: Sequence[str]) -> list[Path]:
    selected: list[Path] = []
    seen: set[str] = set()
    for name in relative_paths:
        relative = Path(name)
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise SourceTreeManifestError(f"invalid relative build input: {name}")
        normalized = relative.as_posix()
        if normalized in seen:
            raise SourceTreeManifestError(f"duplicate build input: {name}")
        seen.add(normalized)
        if any((root.joinpath(*relative.parts[:length])).is_symlink() for length in range(1, len(relative.parts) + 1)):
            raise SourceTreeManifestError(f"build input contains a symbolic link: {name}")
        path = root / relative
        if not path.is_file():
            raise SourceTreeManifestError(f"build input is not a regular file: {name}")
        selected.append(path)
    if not selected:
        raise SourceTreeManifestError("build input list must not be empty")
    return selected


def build_source_tree_manifest(root: Path, *, relative_paths: Sequence[str] | None = None) -> SourceTreeManifest:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise SourceTreeManifestError("source tree does not exist") from exc
    if not resolved_root.is_dir():
        raise SourceTreeManifestError("source tree must be a directory")

    files: list[tuple[str, Path]] = []
    paths: Iterable[Path] = (
        resolved_root.rglob("*") if relative_paths is None else _selected_paths(resolved_root, relative_paths)
    )
    for path in paths:
        if path.is_symlink():
            raise SourceTreeManifestError(f"source tree contains a symbolic link: {path.relative_to(resolved_root)}")
        if path.is_file():
            files.append((path.relative_to(resolved_root).as_posix(), path))

    tree_hash = hashlib.sha256(HASH_DOMAIN)
    for relative_path, path in sorted(files):
        path_bytes = relative_path.encode("utf-8")
        content_hash = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    content_hash.update(chunk)
        except OSError as exc:
            raise SourceTreeManifestError(f"cannot read source file: {relative_path}") from exc
        tree_hash.update(len(path_bytes).to_bytes(8, "big"))
        tree_hash.update(path_bytes)
        tree_hash.update(content_hash.digest())
    return SourceTreeManifest(file_count=len(files), sha256=tree_hash.hexdigest())


def run() -> None:
    parser = argparse.ArgumentParser(description="Hash a staged source tree by relative path and content")
    parser.add_argument("root", type=Path)
    parser.add_argument("--build-definition", choices=["postgres"])
    args = parser.parse_args()
    try:
        inputs = POSTGRES_BUILD_INPUTS if args.build_definition == "postgres" else None
        manifest = build_source_tree_manifest(args.root, relative_paths=inputs)
    except SourceTreeManifestError as exc:
        parser.error(str(exc))
    print(f"{manifest.file_count} {manifest.sha256}")


if __name__ == "__main__":
    run()
