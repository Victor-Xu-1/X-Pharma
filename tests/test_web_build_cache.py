from pathlib import Path


def test_web_build_caches_registry_metadata_without_waiving_locked_package_policy() -> None:
    dockerfile = (Path(__file__).parents[1] / "deploy/api.Dockerfile").read_text(encoding="utf-8")
    installation = dockerfile.split("COPY apps/web/package.json", 1)[1].split("COPY apps/web ./", 1)[0]
    assert "--mount=type=cache,target=/root/.local/share/pnpm/store" in installation
    assert "--mount=type=cache,target=/root/.cache/pnpm" in installation
    assert "pnpm install --frozen-lockfile" in installation
    assert "minimum-release-age=0" not in installation
    assert "--ignore-scripts" not in installation
    assert "--offline" not in installation
