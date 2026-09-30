from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

_RUNTIME_PATHS = {
    Path("backups"): Path("backups"),
    Path("manifests/runtime"): Path("evidence"),
}


class RuntimeLayoutError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimePathRelocation:
    source: str
    target: str
    state: str
    file_count: int
    byte_count: int


@dataclass(frozen=True)
class RuntimeLayoutReport:
    schema_version: int
    applied: bool
    repository: str
    storage_root: str
    relocations: list[RuntimePathRelocation]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _inventory(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    file_count = 0
    byte_count = 0
    for root, directories, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in (*directories, *files):
            candidate = root_path / name
            if candidate.is_symlink():
                raise RuntimeLayoutError(f"Runtime tree contains a symbolic link: {candidate}")
        for name in files:
            candidate = root_path / name
            file_count += 1
            byte_count += candidate.stat().st_size
    return file_count, byte_count


def _write_manifest(storage_root: Path, report: RuntimeLayoutReport) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".runtime-layout-", dir=storage_root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report.as_dict(), handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, storage_root / "runtime-layout.json")
    finally:
        temporary.unlink(missing_ok=True)


def relocate_runtime_paths(repository: Path, storage_root: Path, *, apply: bool = False) -> RuntimeLayoutReport:
    if not repository.is_absolute() or not storage_root.is_absolute():
        raise RuntimeLayoutError("Repository and storage root must be absolute paths")
    repository = repository.resolve(strict=True)
    storage_root = storage_root.resolve(strict=False)
    if _is_within(storage_root, repository) or storage_root == repository:
        raise RuntimeLayoutError("Runtime storage root must be outside the repository")

    relocations: list[RuntimePathRelocation] = []
    operations: list[tuple[Path, Path, bool]] = []
    for relative_source, relative_target in _RUNTIME_PATHS.items():
        source = repository / relative_source
        target = storage_root / relative_target
        if source.is_symlink():
            if source.resolve(strict=False) != target:
                raise RuntimeLayoutError(f"Unexpected symbolic-link target for {source}")
            file_count, byte_count = _inventory(target)
            relocations.append(
                RuntimePathRelocation(str(source), str(target), "already_relocated", file_count, byte_count)
            )
            continue
        if source.exists() and not source.is_dir():
            raise RuntimeLayoutError(f"Runtime source is not a directory: {source}")
        if target.exists():
            raise RuntimeLayoutError(f"Refusing to merge with existing runtime target: {target}")
        file_count, byte_count = _inventory(source)
        state = "relocated" if apply else "would_relocate"
        relocations.append(RuntimePathRelocation(str(source), str(target), state, file_count, byte_count))
        operations.append((source, target, source.exists()))

    if apply:
        storage_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        storage_root.chmod(0o700)
        for source, target, source_existed in operations:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source_existed:
                shutil.move(str(source), str(target))
            else:
                target.mkdir()
            source.parent.mkdir(parents=True, exist_ok=True)
            try:
                source.symlink_to(target, target_is_directory=True)
            except Exception:
                if source.exists() or source.is_symlink():
                    source.unlink()
                if source_existed:
                    shutil.move(str(target), str(source))
                else:
                    target.rmdir()
                raise
        for relative_target in _RUNTIME_PATHS.values():
            (storage_root / relative_target).chmod(0o700)

    report = RuntimeLayoutReport(
        schema_version=1,
        applied=apply,
        repository=str(repository),
        storage_root=str(storage_root),
        relocations=relocations,
    )
    if apply:
        _write_manifest(storage_root, report)
    return report


def run() -> None:
    parser = argparse.ArgumentParser(description="Relocate local runtime artifacts outside the source repository")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Perform the relocation; the default is a dry run")
    arguments = parser.parse_args()
    report = relocate_runtime_paths(arguments.repository, arguments.storage_root, apply=arguments.apply)
    print(json.dumps(report.as_dict(), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    run()
