from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_source_version_replay_acceptance_uses_real_runtime_and_is_packaged() -> None:
    root = Path(__file__).parents[1]
    script = root / "scripts" / "verify-source-version-replay.sh"
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
        "/api/v1/admin/source-versions/$version_id/replay",
        "source_version_operations",
        "source_version.replay",
        "tctl --address temporal:7233 workflow describe",
        "CLAMAV_PORT=1",
        "immutable_object_store",
        "credentials_recorded",
    ):
        assert boundary in text
    assert "unittest.mock" not in text
    assert "monkeypatch" not in text

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")
    assert "source-version-replay-acceptance:" in makefile
    assert "verify-source-version-replay.sh" in makefile
    assert "verify-source-version-replay.sh" in dockerfile
