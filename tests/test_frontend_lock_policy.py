"""Keep every project installer on the same strict warm-cache lock policy."""

from pathlib import Path

import yaml
from packaging.version import Version


def test_workspace_policy_disables_optimistic_frozen_install_shortcut() -> None:
    workspace = Path(__file__).resolve().parents[1] / "apps/web/pnpm-workspace.yaml"
    policy = yaml.safe_load(workspace.read_text(encoding="utf-8"))
    assert isinstance(policy, dict)
    assert policy.get("optimisticRepeatInstall") is False


def test_locked_undici_versions_meet_the_supported_security_floors() -> None:
    lock = Path(__file__).resolve().parents[1] / "apps/web/pnpm-lock.yaml"
    document = yaml.safe_load(lock.read_text(encoding="utf-8"))
    packages = document["packages"]
    versions = {Version(key.removeprefix("undici@").split("(")[0]) for key in packages if key.startswith("undici@")}
    assert versions, "The jsdom HTTP dependency must remain explicitly locked"
    # GHSA-xjj6-f33q-929c fixes all three maintained Undici release lines.
    minimums = {6: Version("6.29.1"), 7: Version("7.30.1"), 8: Version("8.12.2")}
    for version in versions:
        assert version.major in minimums, f"Review the new Undici release line: {version}"
        assert version >= minimums[version.major], f"Undici {version} is below its audited security floor"
