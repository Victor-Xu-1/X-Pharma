"""Keep every project installer on the same strict warm-cache lock policy."""

from pathlib import Path

import yaml


def test_workspace_policy_disables_optimistic_frozen_install_shortcut() -> None:
    workspace = Path(__file__).resolve().parents[1] / "apps/web/pnpm-workspace.yaml"
    policy = yaml.safe_load(workspace.read_text(encoding="utf-8"))
    assert isinstance(policy, dict)
    assert policy.get("optimisticRepeatInstall") is False
