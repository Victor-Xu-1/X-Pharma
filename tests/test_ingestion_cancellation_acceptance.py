from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_ingestion_cancellation_acceptance_uses_real_exact_execution_and_is_packaged() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-ingestion-cancellation.sh"
    text = script.read_text(encoding="utf-8")
    bash = shutil.which("bash")
    assert bash is not None

    completed = subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", str(script)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    for boundary in (
        "/api/v1/admin/ingestion-runs/$ingestion_run_id/cancel",
        "temporal_workflow_id",
        "temporal_run_id",
        '--run_id "$temporal_run_id"',
        "ingestion_run_operations",
        "ingestion_run.cancel",
        "downstream_processing_after_cancel",
        "credentials_recorded",
    ):
        assert boundary in text
    assert "unittest.mock" not in text
    assert "monkeypatch" not in text

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")
    assert "ingestion-cancellation-acceptance:" in makefile
    assert "verify-ingestion-cancellation.sh" in makefile
    assert "verify-ingestion-cancellation.sh" in dockerfile
