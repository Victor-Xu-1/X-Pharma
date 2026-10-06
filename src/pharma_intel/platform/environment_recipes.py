from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pharma_intel import __version__
from pharma_intel.schemas.environment import (
    EnvironmentInstallPlanRead,
    EnvironmentRecipeRead,
    HostEnvironmentRead,
    RecipeId,
)

MANIFEST_FILES = (
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "apps/web/package.json",
    "apps/web/pnpm-lock.yaml",
    "deploy/kubernetes/platform/versions.env",
    "scripts/bootstrap-wsl-tools.sh",
    "deploy/api.Dockerfile",
)
RECIPES = (
    EnvironmentRecipeRead(
        id="python-dependencies",
        label="Python 依赖",
        description="按 uv.lock 安装到当前项目的 .venv，不修改系统 Python。",
        offline_supported=True,
        prerequisites=["uv", "Python 3.13"],
    ),
    EnvironmentRecipeRead(
        id="frontend-dependencies",
        label="前端依赖",
        description="使用项目声明的 pnpm 和冻结锁文件，不升级依赖。",
        offline_supported=True,
        prerequisites=["Node.js", "Corepack"],
    ),
    EnvironmentRecipeRead(
        id="deployment-tools",
        label="部署工具",
        description="通过项目唯一安装器校验并安装固定摘要的 kubectl。",
        offline_supported=True,
        prerequisites=["Linux x86-64", "curl", "python3"],
    ),
)


def manifest_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for name in MANIFEST_FILES:
        target = root / name
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"Missing or unsafe locked manifest: {name}")
        digest.update(name.encode() + b"\0" + target.read_bytes() + b"\0")
    return digest.hexdigest()


def pnpm_release(root: Path) -> str:
    value = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8")).get("packageManager", "")
    if not isinstance(value, str) or not re.fullmatch(r"pnpm@\d+\.\d+\.\d+", value):
        raise ValueError("The authoritative frontend package manager is invalid")
    return value


def recipe_commands(recipe_id: RecipeId, *, offline: bool, package_manager: str) -> list[list[str]]:
    if not re.fullmatch(r"pnpm@\d+\.\d+\.\d+", package_manager):
        raise ValueError("Only the authoritative pinned pnpm release is accepted")
    if recipe_id == "python-dependencies":
        return [["uv", "sync", "--locked", "--no-dev", *(["--offline"] if offline else [])]]
    if recipe_id == "frontend-dependencies":
        return [
            [
                "corepack",
                package_manager,
                "--dir",
                "apps/web",
                "install",
                "--frozen-lockfile",
                *(["--offline"] if offline else []),
            ]
        ]
    if recipe_id == "deployment-tools":
        return [["bash", "scripts/bootstrap-wsl-tools.sh"]]
    raise ValueError("Unsupported installation recipe")


def plan_digest(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def create_plan(
    host: HostEnvironmentRead, *, recipe_id: RecipeId, offline: bool, package_manager: str, now: datetime | None = None
) -> EnvironmentInstallPlanRead:
    at = now or datetime.now(UTC)
    if not host.clean_source or host.product_version != __version__:
        raise ValueError("A clean source matching this product version is required")
    value: dict[str, object] = {
        "schema_version": "pharma.environment.install-plan.v1",
        "generated_at": at.isoformat(),
        "expires_at": (at + timedelta(hours=24)).isoformat(),
        "product_version": __version__,
        "revision": host.revision,
        "manifest_sha256": host.manifest_sha256,
        "recipe_id": recipe_id,
        "offline": offline,
        "commands": recipe_commands(recipe_id, offline=offline, package_manager=package_manager),
    }
    value["plan_id"] = "0" * 64
    draft = EnvironmentInstallPlanRead.model_validate(value)
    digest = plan_digest(draft.model_dump(mode="json", exclude={"plan_id"}))
    return draft.model_copy(update={"plan_id": digest})
