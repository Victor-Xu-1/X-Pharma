import re
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


def test_fixture_source_cleanup_removes_ingestion_children_before_evidence_and_replay_sources() -> None:
    runner = (ROOT / "scripts/run-browser-acceptance.sh").read_text(encoding="utf-8")
    cleanup = runner.split("cleanup_fixtures() {", 1)[1].split("COMMIT;", 1)[0]
    source_scope = re.search(
        r"CREATE TEMP TABLE browser_fixture_sources.*?;\s*INSERT INTO browser_fixture_sources.*?;",
        cleanup,
        re.DOTALL,
    )
    statements = []
    for match in re.finditer(
        r"DELETE FROM (audit_events|ingestion_run_operations|ingestion_findings|ingestion_runs|data_sources)\b.*?;",
        cleanup,
        re.DOTALL,
    ):
        if match.group(1) != "audit_events" or "resource_type = 'ingestion_run'" in match.group():
            statements.append(match.group())
    sql = "\n".join([source_scope.group() if source_scope else "", *statements])
    sql = sql.replace(" ON COMMIT DROP", "").replace("'$tenant_id'", "'owned-tenant'")
    with sqlite3.connect(":memory:") as database:
        database.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE data_sources (id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT);
            CREATE TABLE ingestion_runs (
                id TEXT PRIMARY KEY, tenant_id TEXT,
                data_source_id TEXT REFERENCES data_sources(id)
            );
            CREATE TABLE ingestion_run_operations (
                tenant_id TEXT, ingestion_run_id TEXT REFERENCES ingestion_runs(id)
            );
            CREATE TABLE ingestion_findings (
                tenant_id TEXT, ingestion_run_id TEXT REFERENCES ingestion_runs(id)
            );
            CREATE TABLE audit_events (tenant_id TEXT, resource_type TEXT, resource_id TEXT);
            """
        )
        sources = [
            ("evidence", "owned-tenant", f"Browser evidence {PREFIX}"),
            ("replay", "owned-tenant", f"Browser replay {PREFIX} desktop-1440"),
            ("public", "owned-tenant", "Public clinical source"),
            ("foreign", "other-tenant", f"Browser evidence {PREFIX}"),
        ]
        database.executemany("INSERT INTO data_sources VALUES (?, ?, ?)", sources)
        for source_id, tenant_id, _name in sources:
            database.execute("INSERT INTO ingestion_runs VALUES (?, ?, ?)", (source_id, tenant_id, source_id))
            database.execute("INSERT INTO ingestion_run_operations VALUES (?, ?)", (tenant_id, source_id))
            database.execute("INSERT INTO ingestion_findings VALUES (?, ?)", (tenant_id, source_id))
            database.execute("INSERT INTO audit_events VALUES (?, 'ingestion_run', ?)", (tenant_id, source_id))
        database.executescript(sql)
        for table in ("data_sources", "ingestion_runs"):
            assert database.execute(f"SELECT id FROM {table} ORDER BY id").fetchall() == [  # noqa: S608 - fixed test tables.
                ("foreign",),
                ("public",),
            ]
        for table in ("ingestion_run_operations", "ingestion_findings"):
            assert database.execute(f"SELECT ingestion_run_id FROM {table} ORDER BY ingestion_run_id").fetchall() == [  # noqa: S608 - fixed test tables.
                ("foreign",),
                ("public",),
            ]
        assert database.execute("SELECT resource_id FROM audit_events ORDER BY resource_id").fetchall() == [
            ("foreign",),
            ("public",),
        ]
