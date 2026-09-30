from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_quarantine_workflow_acceptance_uses_real_runtime_boundaries() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-quarantine-workflow.sh"
    bash = shutil.which("bash")
    assert bash is not None
    subprocess.run(  # noqa: S603 - fixed repository script is syntax checked only.
        [bash, "-n", str(script)],
        cwd=root,
        check=True,
    )
    text = script.read_text(encoding="utf-8")

    required = {
        "pharma.quarantine-workflow-acceptance.v1",
        "EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
        "pharma-ingest once",
        "/api/v1/admin/quarantine-cases/$version_id/decisions",
        "/api/v1/admin/source-versions/$version_id/replay",
        "source-version-reprocess-$version_id",
        "immutable_source_version_quarantine_decisions",
        "source_version_quarantine_decisions",
        "relforcerowsecurity",
        "generic_replay_blocked",
        "temporary_database_records_after",
    }
    assert required <= set(filter(None, (item if item in text else "" for item in required)))
    assert "mock" not in text.lower()
    assert 'credentials_recorded":False' in text


def test_quarantine_workflow_acceptance_is_packaged_and_invocable() -> None:
    root = Path(__file__).parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")

    assert "quarantine-workflow-acceptance:" in makefile
    assert "verify-quarantine-workflow.sh" in makefile
    assert "verify-quarantine-workflow.sh" in dockerfile
