from __future__ import annotations

import argparse
from pathlib import Path

from pharma_intel.platform.environment_executor import execute_install_plan, read_install_result
from pharma_intel.platform.environment_host import detect_host, workspace_path
from pharma_intel.platform.environment_recipes import create_plan, pnpm_release
from pharma_intel.schemas.environment import EnvironmentInstallPlanRead, RecipeId


def publish_report(path: Path, payload: str, *, public: bool = False) -> None:
    path = workspace_path(path)
    if path.is_symlink() or path.with_suffix(".partial").is_symlink():
        raise ValueError("Report targets cannot be symbolic links")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.stat().st_size > 256 * 1024:
            raise ValueError("An unrelated existing output was preserved")
        from pharma_intel.schemas.environment import HostEnvironmentRead

        if public:
            HostEnvironmentRead.model_validate_json(path.read_bytes())
        else:
            EnvironmentInstallPlanRead.model_validate_json(path.read_bytes())
    temporary = path.with_suffix(".partial")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(payload + "\n")
    temporary.chmod(0o644 if public else 0o600)
    temporary.replace(path)


def run() -> None:
    parser = argparse.ArgumentParser(description="Detect and manage only the local X-Pharma project environment")
    parser.add_argument("action", choices=("inspect", "plan", "install"))
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recipe", choices=("python-dependencies", "frontend-dependencies", "deployment-tools"))
    parser.add_argument(
        "--online", action="store_true", help="Explicitly permit reviewed recipe downloads; default is offline"
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument(
        "--execute", action="store_true", help="Explicit host-side approval; never executed by the Web gateway"
    )
    parser.add_argument("--state-root", type=Path, default=Path("/srv/wsl/data/x-pharma-environment"))
    args = parser.parse_args()
    try:
        root = workspace_path(args.repository)
        if args.action == "install":
            if not args.execute or args.plan is None:
                raise ValueError("Installation requires a plan file and explicit --execute")
            plan_path = workspace_path(args.plan)
            if plan_path.is_symlink() or plan_path.stat().st_size > 256 * 1024:
                raise ValueError("Unsafe or oversized plan")
            plan = EnvironmentInstallPlanRead.model_validate_json(plan_path.read_bytes())
            result = execute_install_plan(root, plan, args.state_root)
            print(result.model_dump_json(indent=2))
            if result.status != "succeeded":
                raise SystemExit(1)
            return
        latest = read_install_result(args.state_root)
        host = detect_host(root, latest_install=latest)
        if args.action == "plan":
            if args.recipe is None:
                raise ValueError("Choose one installation recipe")
            recipe: RecipeId = args.recipe
            value = create_plan(
                host, recipe_id=recipe, offline=not args.online, package_manager=pnpm_release(root)
            ).model_dump_json(indent=2)
        else:
            value = host.model_dump_json(indent=2)
        if args.output:
            if args.action == "inspect" and args.output.name != "host.json":
                raise ValueError("The host observation report must be named host.json")
            publish_report(args.output, value, public=args.action == "inspect")
            print(f"Wrote {args.action} evidence to the approved E-drive workspace")
        else:
            print(value)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Environment operation failed: {exc}\n")


if __name__ == "__main__":
    run()
