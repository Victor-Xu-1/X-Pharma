from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_data_quality_postgres_acceptance_binds_to_an_explicit_compose_runtime() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-data-quality-postgres.sh"
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
