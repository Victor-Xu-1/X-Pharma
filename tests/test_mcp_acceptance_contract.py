from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pharma_intel.models.enums import ReviewStatus


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
    assert text.count("mcp_fixture_opensearch") == 3
    assert 'source "$root/scripts/lib/mcp_fixture_http.sh"' in text
    assert text.count(f"'{ReviewStatus.VERIFIED.name}', now(), now()") == 4
    assert f'"review_status": "{ReviewStatus.VERIFIED.value}"' in text


@pytest.mark.parametrize("docker_status", [0, 17])
@pytest.mark.parametrize("input_mode", ["body", "none"])
def test_mcp_fixture_http_scopes_real_shell_arguments_and_propagates_failure(
    tmp_path: Path, docker_status: int, input_mode: str
) -> None:
    root = Path(__file__).parents[1]
    bash = shutil.which("bash")
    assert bash is not None
    arguments = tmp_path / "arguments"
    payload = tmp_path / "payload"
    helper = root / "scripts/lib/mcp_fixture_http.sh"
    shell = """
set -euo pipefail
source "$HELPER"
record_composition() {
  printf '%s\\0' "$@" > "$CAPTURE_ARGUMENTS"
  cat > "$CAPTURE_PAYLOAD"
  printf '{"result":"created"}\\n'
  return "$DOCKER_STATUS"
}
compose=(record_composition --project-name isolated-project)
mcp_fixture_opensearch "$INPUT_MODE" --fail --request PUT http://127.0.0.1:9200/fixture --data-binary @-
"""
    result = subprocess.run(  # noqa: S603 - fixed shell helper; Docker alone is isolated by the controlled boundary.
        [bash, "-c", shell],
        env={
            **os.environ,
            "HELPER": str(helper),
            "CAPTURE_ARGUMENTS": str(arguments),
            "CAPTURE_PAYLOAD": str(payload),
            "DOCKER_STATUS": str(docker_status),
            "INPUT_MODE": input_mode,
        },
        input='{"fixture":true}',
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == docker_status, result.stderr
    captured = arguments.read_bytes().decode().split("\0")[:-1]
    assert captured[:7] == [
        "--project-name",
        "isolated-project",
        "exec",
        "-T",
        f"--interactive={'true' if input_mode == 'body' else 'false'}",
        "opensearch",
        "curl",
    ]
    assert "--connect-timeout" in captured and "--max-time" in captured
    assert captured[-2:] == ["--data-binary", "@-"]
    assert payload.read_text() == '{"fixture":true}'
    assert result.stdout == '{"result":"created"}\n'
