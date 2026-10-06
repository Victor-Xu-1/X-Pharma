from __future__ import annotations

import importlib.metadata
import os
import platform
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from pharma_intel import __version__
from pharma_intel.config import Settings
from pharma_intel.models import AuditEvent
from pharma_intel.platform.environment_compatibility import pinned_dependencies, version_state
from pharma_intel.platform.environment_recipes import RECIPES, create_plan
from pharma_intel.schemas.environment import (
    EnvironmentInstallPlanRead,
    EnvironmentPlanCreate,
    EnvironmentProbeRead,
    EnvironmentRead,
    HostEnvironmentRead,
    HostReportStatus,
)

MAX_REPORT_BYTES = 256 * 1024


def read_host_report(
    root: Path | None, *, now: datetime | None = None
) -> tuple[HostReportStatus, HostEnvironmentRead | None, str]:
    if root is None:
        return "not_configured", None, "尚未连接主机检测报告；网关内的运行版本不等同于主机安装状态。"
    target = root / "environment" / "host.json"
    try:
        if root.is_symlink() or target.parent.is_symlink() or target.is_symlink():
            raise ValueError("Symbolic report paths are not accepted")
        with os.fdopen(os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
                raise ValueError("Unsafe report")
            payload = stream.read(MAX_REPORT_BYTES + 1)
        if len(payload) > MAX_REPORT_BYTES:
            raise ValueError("Oversized report")
        host = HostEnvironmentRead.model_validate_json(payload)
        at = now or datetime.now(UTC)
        if host.generated_at.tzinfo is None or host.generated_at > at + timedelta(minutes=5):
            raise ValueError("Invalid observation time")
        if at - host.generated_at > timedelta(hours=24):
            return "stale", host, "主机报告已超过 24 小时；请重新检测后生成安装计划。"
        if host.product_version != __version__:
            return "stale", host, "主机报告不属于当前产品版本；请重新检测。"
        return "current", host, "主机侧真实检测报告；安装执行必须在该主机受控完成。"
    except FileNotFoundError:
        return "missing", None, "主机报告尚不存在；不会把缺失的探针当作健康。"
    except (OSError, ValueError, ValidationError):
        return "invalid", None, "主机报告无效或不可安全读取；请重新生成，原始错误和路径不对外披露。"


def environment_snapshot(settings: Settings) -> EnvironmentRead:
    try:
        metadata = importlib.metadata.metadata("x-pharma")
        python_requirement = metadata.get("Requires-Python")
        requirements = pinned_dependencies(importlib.metadata.requires("x-pharma") or [])
    except (importlib.metadata.PackageNotFoundError, ValueError):
        python_requirement, requirements = None, {}
    probes = [
        EnvironmentProbeRead(
            id="python",
            label="Python",
            scope="gateway",
            status=version_state(platform.python_version(), python_requirement),
            observed=platform.python_version(),
            expected=python_requirement,
            detail="当前网关进程实际使用的解释器。",
        )
    ]
    for name, label in (("x-pharma", "X-Pharma"), ("sqlalchemy", "SQLAlchemy"), ("mcp", "MCP SDK"), ("rdkit", "RDKit")):
        expected = __version__ if name == "x-pharma" else requirements.get(name)
        try:
            version = importlib.metadata.version(name)
            probe = EnvironmentProbeRead(
                id=name,
                label=label,
                scope="gateway",
                status=version_state(version, f"=={expected}" if expected else None),
                observed=version,
                expected=f"=={expected}" if expected else None,
                detail="已安装的发行包版本；不替代服务健康检查。",
            )
        except importlib.metadata.PackageNotFoundError:
            probe = EnvironmentProbeRead(
                id=name,
                label=label,
                scope="gateway",
                status="missing",
                expected=f"=={expected}" if expected else None,
                detail="当前网关环境未发现该发行包。",
            )
        probes.append(probe)
    probes.append(
        EnvironmentProbeRead(
            id="human-identity",
            label="人员身份与账号恢复",
            scope="gateway",
            status="unverified",
            observed="本地账号（邮箱未验证）" if settings.human_auth_mode == "local" else "企业 OIDC 配置",
            expected="正式环境使用企业 OIDC 与受控恢复策略",
            detail="本地登录不能作为正式身份验收；企业 IdP、账号恢复和目标部署必须提供独立实测证据。",
        )
    )
    host_status, host, detail = read_host_report(settings.platform_evidence_root)
    return EnvironmentRead(
        generated_at=datetime.now(UTC),
        product_version=__version__,
        environment=settings.app_env,
        runtime=probes,
        host_status=host_status,
        host=host,
        host_detail=detail,
        recipes=list(RECIPES),
    )


def environment_plan(settings: Settings, payload: EnvironmentPlanCreate) -> EnvironmentInstallPlanRead:
    state, host, _ = read_host_report(settings.platform_evidence_root)
    if state != "current" or host is None:
        raise ValueError("请先生成当前版本的有效主机检测报告。")
    manager = next((probe.expected for probe in host.probes if probe.id == "pnpm"), None)
    if manager is None or not manager.startswith("pnpm@"):
        raise ValueError("主机报告缺少项目声明的包管理器；请重新检测。")
    return create_plan(host, recipe_id=payload.recipe_id, offline=payload.offline, package_manager=manager)


def record_environment_plan(
    session: Session, *, tenant_id: str, actor_id: str, request_id: str, plan: EnvironmentInstallPlanRead
) -> None:
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="user",
            actor_id=actor_id,
            action="environment.install_plan.created",
            resource_type="environment_install_plan",
            resource_id=plan.plan_id,
            outcome="success",
            request_id=request_id,
            details={
                "recipe_id": plan.recipe_id,
                "offline": plan.offline,
                "revision": plan.revision,
                "manifest_sha256": plan.manifest_sha256,
            },
        )
    )
    session.commit()
