from __future__ import annotations

from pathlib import Path


class SourceRootPolicyError(ValueError):
    pass


def validate_folder_source_root(
    root: Path,
    allowed_roots: list[Path],
    *,
    require_existing: bool,
) -> Path:
    if not root.is_absolute():
        raise SourceRootPolicyError("Folder source roots must be absolute paths")
    if not allowed_roots:
        raise SourceRootPolicyError("No folder source roots are configured")

    try:
        resolved_root = root.resolve(strict=require_existing)
    except OSError as exc:
        raise SourceRootPolicyError(f"Data-source root is unavailable: {root}") from exc

    resolved_allowed: list[Path] = []
    for allowed in allowed_roots:
        if not allowed.is_absolute():
            raise SourceRootPolicyError("Configured source roots must be absolute paths")
        try:
            resolved_allowed.append(allowed.resolve(strict=require_existing))
        except OSError:
            if require_existing:
                continue
            resolved_allowed.append(allowed.resolve(strict=False))

    if not any(resolved_root == allowed or resolved_root.is_relative_to(allowed) for allowed in resolved_allowed):
        raise SourceRootPolicyError("Folder source root is outside the configured SOURCE_ROOTS allowlist")
    if require_existing and not resolved_root.is_dir():
        raise SourceRootPolicyError(f"Data-source root is unavailable: {root}")
    return resolved_root
