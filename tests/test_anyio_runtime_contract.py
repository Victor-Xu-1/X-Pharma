"""Keep the exact async primitives used by MCP, parsers and activities importable."""

import subprocess
import sys
from pathlib import Path

PROBE = """
import asyncio
import anyio

async def main():
    with anyio.CancelScope(shield=True):
        async with anyio.Semaphore(1):
            with anyio.fail_after(5):
                assert await anyio.to_thread.run_sync(lambda: 42) == 42

asyncio.run(main())
"""


def test_anyio_runtime_apis_work_in_a_fresh_isolated_interpreter(tmp_path: Path) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal probe, never user input.
        [sys.executable, "-I", "-c", PROBE],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert completed.stdout == completed.stderr == ""
