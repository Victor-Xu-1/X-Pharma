import shutil
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
PREFIX = "e2e-20261002000000-12345"


def _cleanup_pattern(recovery: bool) -> str:
    runner = (ROOT / "scripts/run-browser-acceptance.sh").read_text(encoding="utf-8")
    scope = runner[runner.index("email_pattern=") : runner.index("\npassword=")]
    executable = shutil.which("bash")
    assert executable is not None
    # Execute only the reviewed pattern selector, never the acceptance runner.
    script = f'set -eu\nemail_prefix=$1\nrecover_interrupted_run=$2\n{scope}\nprintf "%s" "$email_pattern"'
    result = subprocess.run(  # noqa: S603 - fixed trusted selector; inputs are positional values, no external calls.
        [executable, "-c", script, "cleanup-scope", PREFIX, str(recovery).lower()],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout


def test_normal_browser_cleanup_preserves_other_runs_and_unrelated_accounts() -> None:
    current = f"{PREFIX}-desktop-1440@example.test"
    other_run = "e2e-20261001000000-999-desktop-1920@example.test"
    unrelated = "e2e-researcher@example.test"
    with sqlite3.connect(":memory:") as database:
        database.execute("CREATE TABLE users (normalized_email TEXT PRIMARY KEY)")
        database.executemany("INSERT INTO users VALUES (?)", [(current,), (other_run,), (unrelated,)])
        database.execute("DELETE FROM users WHERE normalized_email LIKE ?", (_cleanup_pattern(False),))
        assert database.execute("SELECT normalized_email FROM users ORDER BY normalized_email").fetchall() == [
            (other_run,),
            (unrelated,),
        ]


def test_explicit_interrupted_recovery_is_the_only_broad_cleanup_mode() -> None:
    assert _cleanup_pattern(True) == "e2e-%@example.test"
    assert _cleanup_pattern(False) == f"{PREFIX}-%@example.test"
