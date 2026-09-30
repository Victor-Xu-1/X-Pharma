from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

HASH_DOMAIN = b"pharma-intelligence-source-tree-v1\0"


class SourceTreeManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceTreeManifest:
    file_count: int
    sha256: str


def build_source_tree_manifest(root: Path) -> SourceTreeManifest:
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise SourceTreeManifestError("source tree does not exist") from exc
    if not resolved_root.is_dir():
        raise SourceTreeManifestError("source tree must be a directory")

    files: list[tuple[str, Path]] = []
    for path in resolved_root.rglob("*"):
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
    args = parser.parse_args()
    try:
        manifest = build_source_tree_manifest(args.root)
    except SourceTreeManifestError as exc:
        parser.error(str(exc))
    print(f"{manifest.file_count} {manifest.sha256}")


if __name__ == "__main__":
    run()
