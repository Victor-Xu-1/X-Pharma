import shutil
import subprocess
from pathlib import Path

import pytest


def _run(nonce: str, timestamp: str = "20261005133700") -> subprocess.CompletedProcess[str]:
    helper = Path(__file__).parents[1] / "scripts" / "lib" / "browser_fixture_identity.sh"
    bash = shutil.which("bash")
    assert bash is not None, "The browser acceptance runtime requires Bash"
    # The command is fixed; test values are quoted positional arguments, never executable shell source.
    return subprocess.run(  # noqa: S603
        [bash, "-c", 'source "$1"; browser_fixture_run_id "$2" "$3"', "_", str(helper), timestamp, nonce],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


@pytest.mark.parametrize("nonce", ["0", "7", "99", "1000", "32767"])
def test_browser_fixture_nonce_has_fixed_width_without_losing_identity(nonce: str) -> None:
    result = _run(nonce)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"20261005133700-{int(nonce):05d}\n"
    assert len(result.stdout.strip()) == 20


@pytest.mark.parametrize("nonce", ["32768", "-1", "123456", "7;echo unsafe"])
def test_browser_fixture_rejects_out_of_range_or_non_numeric_nonces(nonce: str) -> None:
    result = _run(nonce)
    assert result.returncode == 2
    assert not result.stdout


def test_browser_fixture_requires_a_fixed_width_timestamp() -> None:
    result = _run("7", "2026-10-05")
    assert result.returncode == 2
    assert not result.stdout
