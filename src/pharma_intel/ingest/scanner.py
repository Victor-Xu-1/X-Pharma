from __future__ import annotations

import fnmatch
import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PARSEABLE_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".txt",
    ".md",
    ".html",
    ".htm",
    ".json",
    ".sdf",
    ".mol",
    ".pdb",
    ".cif",
    ".mmcif",
    ".xml",
    ".nxml",
}
ASSET_ONLY_EXTENSIONS = {".cdx", ".moe", ".mdb"}
EXCLUDED_DIRECTORY_NAMES = {
    "$recycle.bin",
    "system volume information",
    "software",
    "system",
    "invoice",
    "attendance",
    "administration",
    "node_modules",
    ".git",
    "\u8f6f\u4ef6",
    "\u7cfb\u7edf",
    "\u53d1\u7968",
    "\u8003\u52e4",
    "\u884c\u653f",
}
EXCLUDED_EXTENSIONS = {
    ".exe",
    ".msi",
    ".iso",
    ".zip",
    ".7z",
    ".rar",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
}


@dataclass(frozen=True)
class DiscoveredFile:
    root: Path
    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    modified_at: datetime
    mode: str
    dataset_key: str


@dataclass(frozen=True)
class DiscoveryError:
    path: str
    message: str


@dataclass(frozen=True)
class FolderScanResult:
    files: list[DiscoveredFile]
    errors: list[DiscoveryError]
    excluded_count: int


def classify_path(path: Path) -> str:
    extension = path.suffix.casefold()
    if extension in PARSEABLE_EXTENSIONS:
        return "parse"
    if extension in ASSET_ONLY_EXTENSIONS:
        return "asset"
    return "exclude"


def route_dataset(relative_path: str) -> str:
    normalized = relative_path.casefold()
    if "\u4e13\u5229" in normalized or "patent" in normalized:
        return "patents"
    if "\u6587\u732e" in normalized or "paper" in normalized or "literature" in normalized:
        return "literature"
    if "poster" in normalized or "\u516c\u53f8" in normalized:
        return "corporate"
    if "bd" in normalized or "ai\u62a5\u544a" in normalized or "\u62a5\u544a" in normalized:
        return "bd_reports"
    return "projects"


def scan_folder(
    root: Path,
    max_file_bytes: int,
    dataset_key: str,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> FolderScanResult:
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(f"Data-source root is unavailable: {root}")
    includes = include_globs or ["*", "**/*"]
    excludes = exclude_globs or []
    files: list[DiscoveredFile] = []
    errors: list[DiscoveryError] = []
    excluded_count = 0

    def on_error(error: OSError) -> None:
        errors.append(DiscoveryError(error.filename or str(root), str(error)))

    for current, directories, filenames in os.walk(resolved_root, followlinks=False, onerror=on_error):
        current_path = Path(current)
        safe_directories: list[str] = []
        for name in directories:
            candidate = current_path / name
            relative = candidate.relative_to(resolved_root).as_posix()
            if candidate.is_symlink() or name.casefold() in EXCLUDED_DIRECTORY_NAMES or _matches(relative, excludes):
                excluded_count += 1
                continue
            safe_directories.append(name)
        directories[:] = safe_directories

        for filename in filenames:
            path = current_path / filename
            try:
                if path.is_symlink():
                    excluded_count += 1
                    continue
                resolved_path = path.resolve(strict=True)
                if not resolved_path.is_relative_to(resolved_root):
                    errors.append(DiscoveryError(str(path), "Resolved path escapes the configured data-source root"))
                    continue
                relative = resolved_path.relative_to(resolved_root).as_posix()
                mode = classify_path(resolved_path)
                stat = resolved_path.stat()
            except OSError as exc:
                errors.append(DiscoveryError(str(path), str(exc)))
                continue
            if (
                mode == "exclude"
                or resolved_path.suffix.casefold() in EXCLUDED_EXTENSIONS
                or stat.st_size > max_file_bytes
                or not _matches(relative, includes)
                or _matches(relative, excludes)
            ):
                excluded_count += 1
                continue
            files.append(
                DiscoveredFile(
                    root=resolved_root,
                    path=resolved_path,
                    relative_path=relative,
                    extension=resolved_path.suffix.casefold(),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                    mode=mode,
                    dataset_key=dataset_key,
                )
            )
    files.sort(key=lambda item: item.relative_path.casefold())
    return FolderScanResult(files, errors, excluded_count)


def _matches(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.casefold()
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/").casefold()) for pattern in patterns)


def discover(root: Path, max_file_bytes: int) -> Iterable[DiscoveredFile]:
    """Compatibility wrapper for one-shot local scans; registered sources use scan_folder."""
    result = scan_folder(root, max_file_bytes, dataset_key="projects")
    for item in result.files:
        yield DiscoveredFile(
            root=item.root,
            path=item.path,
            relative_path=item.relative_path,
            extension=item.extension,
            size_bytes=item.size_bytes,
            modified_at=item.modified_at,
            mode=item.mode,
            dataset_key=route_dataset(item.relative_path),
        )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
