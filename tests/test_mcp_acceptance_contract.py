from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_mcp_interoperability_acceptance_binds_to_an_explicit_compose_runtime() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-mcp-interoperability.sh"
    text = script.read_text(encoding="utf-8")
    bash = shutil.which("bash")
    assert bash is not None

    syntax = subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert syntax.returncode == 0, syntax.stderr
    assert 'project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"' in text
    assert "--project-name NAME" in text
    assert 'compose=(docker compose --project-name "$project_name")' in text
    assert 'export COMPOSE_FILE="compose.yaml:compose.dev.yaml:compose.telemetry.yaml"' in text
    assert "--seed-local-commercial-fixture" in text
    assert "pharma_intel.mcp_interoperability_fixture seed" in text
    assert "cleanup_local_commercial_fixture" in text
    assert "program_tags, target_set_version, organization_set_version" in text
    assert "'[]'::json, 1, 1, '$fixture_target_id_b'" in text
