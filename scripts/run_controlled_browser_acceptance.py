"""Execute audited response-controlled UI cases, never real stack scenarios."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from scripts.browser_cases import PROJECTS
from scripts.browser_phase_runtime import (
    ROOT,
    WEB,
    discover,
    execute,
    load,
    phase_arguments,
    playwright_command,
    save,
    source_revision,
    stop_group,
    validate_destination,
)
from scripts.browser_phases import UI_PHASES, Phase, verify_results


def browser_profile() -> tuple[str, str]:
    bash = shutil.which("bash")
    if bash is None:
        raise ValueError("The original Bash browser-profile verifier is required")
    script = (
        "set -Eeuo pipefail; browser_target=chrome; update_snapshots=false; "
        "source scripts/lib/browser_fonts.sh; verify_browser_fonts; "
        "source scripts/lib/browser_runtime.sh; resolve_browser_runtime; verify_browser_visual_profile; "
        'printf \'%s\\n\' "$browser_launch_executable" "$browser_version"'
    )
    result = subprocess.run(  # noqa: S603  # Fixed existing profile owners; no caller commands or installers.
        [bash, "-c", script], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30
    )
    lines = result.stdout.splitlines()
    if len(lines) < 2 or not Path(lines[-2]).is_file() or not lines[-1].startswith("Google Chrome "):
        raise ValueError("The original verified Google Chrome profile is required")
    return lines[-2], lines[-1]


def ready(process: subprocess.Popen[bytes], origin: str) -> None:
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError("Controlled frontend exited before readiness")
        try:
            with urlopen(f"{origin}/workspace/research", timeout=1) as response:  # noqa: S310  # Generated loopback only.
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError("Controlled frontend readiness exceeded its bounded startup")


def run(output: Path, phase: Phase = "controlled") -> None:
    if phase not in UI_PHASES:
        raise ValueError("The isolated UI runner cannot execute real stack cases")
    validate_destination(output)
    if not (WEB / "dist/research.html").is_file() or not (WEB / "dist/internal.html").is_file():
        raise ValueError("The existing frontend job must build both workbenches before controlled acceptance")
    manifest = discover()
    executable, version = browser_profile()
    command = playwright_command()
    with (
        tempfile.TemporaryDirectory(prefix="x-pharma-controlled-browser-") as temporary,
        socket.socket() as dead_backend,
    ):
        state = Path(temporary)
        # Reserved but not listening: another service cannot accidentally supply a real backend.
        dead_backend.bind(("127.0.0.1", 0))
        backend_port = dead_backend.getsockname()[1]
        with socket.socket() as port_probe:
            port_probe.bind(("127.0.0.1", 0))
            port = port_probe.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        environment = dict(os.environ)
        environment.update(
            {
                "CI": "1",
                "E2E_BASE_URL": origin,
                "E2E_BROWSER_EXECUTABLE": executable,
                "WORKBENCH_PROXY_TARGET": f"http://127.0.0.1:{backend_port}",
                "PLAYWRIGHT_JSON_OUTPUT_FILE": str(state / "results.json"),
            }
        )
        with (state / "frontend.log").open("wb") as log:
            process = subprocess.Popen(  # noqa: S603  # Pinned manager, fixed Vite arguments and own process group.
                [*command[:4], "exec", "vite", "preview", "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                ready(process, origin)
                execute(
                    [
                        *command,
                        *phase_arguments(manifest, phase),
                        "--workers=1",
                        "--fail-on-flaky-tests",
                        "--reporter=line,json",
                        "--output",
                        str(state / "browser-output"),
                        *(f"--project={project}" for project in PROJECTS),
                    ],
                    environment,
                    300,
                )
                coverage = verify_results(manifest, load(state / "results.json"), phase)
                if source_revision() != manifest["revision"]:
                    raise ValueError("Controlled browser source changed during execution")
                save(
                    output,
                    {
                        "schema": "x-pharma.controlled-browser-acceptance.v1",
                        "status": "passed",
                        "production_claim": False,
                        "real_backend": False,
                        "browser": version,
                        "phase_manifest": manifest,
                        "case_coverage": coverage,
                        "credentials_recorded": False,
                    },
                )
                print(
                    f"CONTROLLED_BROWSER_ACCEPTANCE phase={phase} passed={coverage['passed']} "
                    "projects=4 workers=1 backend=false"
                )
            finally:
                stop_group(process)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=UI_PHASES, default="controlled")
    args = parser.parse_args()
    run(args.output, args.phase)


if __name__ == "__main__":
    main()
