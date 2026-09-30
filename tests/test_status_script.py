from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def _write_fake_docker(directory: Path, source: str) -> Path:
    executable = directory / "docker"
    executable.write_text(source, encoding="utf-8")
    executable.chmod(0o755)
    return executable


def test_status_fails_fast_when_docker_engine_is_unresponsive(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    bash = shutil.which("bash")
    outer_timeout = shutil.which("timeout")
    assert bash is not None
    assert outer_timeout is not None

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin, "#!/usr/bin/env bash\nexec sleep 30\n")
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS"] = "1"

    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - fixed shell tools exercise the repository status boundary.
        [
            outer_timeout,
            "--signal=TERM",
            "--kill-after=1s",
            "5s",
            bash,
            str(root / "scripts" / "status.sh"),
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started

    assert completed.returncode == 1, completed.stderr
    assert elapsed < 4
    assert "Docker engine management API is unavailable" in completed.stderr
    assert "Docker Desktop status alone is not sufficient" in completed.stderr
    assert "No services were restarted and no volumes were changed" in completed.stderr


def test_status_rejects_invalid_docker_timeout_before_calling_docker(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    bash = shutil.which("bash")
    assert bash is not None

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    invocation_marker = tmp_path / "docker-invoked"
    _write_fake_docker(
        fake_bin,
        f"#!/usr/bin/env bash\nprintf invoked > {invocation_marker!s}\n",
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS"] = "unbounded"

    completed = subprocess.run(  # noqa: S603 - fixed Bash path and repository script are controlled.
        [bash, str(root / "scripts" / "status.sh")],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 2
    assert "must be an integer between 1 and 300" in completed.stderr
    assert not invocation_marker.exists()
