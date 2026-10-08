"""Select the official HTTPS archive on the ephemeral Ubuntu CI runner only."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path

ARCHIVE = "https://archive.ubuntu.com/ubuntu"
_AZURE_LINE = re.compile(r"(?m)^([ \t]*)https?://azure\.archive\.ubuntu\.com/ubuntu(/?)([ \t][^\n]*)?$")
_OFFICIAL_LINE = re.compile(r"(?m)^[ \t]*https://archive\.ubuntu\.com/ubuntu/?(?:[ \t][^\n]*)?$")


def canonical_mirrors(contents: str) -> str:
    replacement, count = _AZURE_LINE.subn(lambda match: f"{match[1]}{ARCHIVE}{match[2]}{match[3] or ''}", contents)
    if not count and not _OFFICIAL_LINE.search(contents):
        raise ValueError("Unexpected CI Ubuntu archive mirror; explicit review is required")
    return replacement


def configure_ci_archive(mirrors: Path, environment: Mapping[str, str], os_release: str) -> bool:
    if environment.get("GITHUB_ACTIONS") != "true" or environment.get("RUNNER_OS") != "Linux":
        raise ValueError("Archive preparation is restricted to the ephemeral GitHub Linux runner")
    release = dict(line.partition("=")[::2] for line in os_release.splitlines() if "=" in line)
    if release.get("ID", "").strip('"') != "ubuntu" or release.get("VERSION_ID", "").strip('"') != "24.04":
        raise ValueError("Browser acceptance requires the reviewed Ubuntu 24.04 runner")
    metadata = mirrors.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024:
        raise ValueError("CI mirror list must be a bounded regular file")
    contents = mirrors.read_text(encoding="utf-8")
    replacement = canonical_mirrors(contents)
    if replacement == contents:
        return False
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".x-pharma-browser-mirror-", dir=mirrors.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(replacement)
            stream.flush()
            os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
        temporary.replace(mirrors)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main() -> None:
    changed = configure_ci_archive(
        Path("/etc/apt/apt-mirrors.txt"), os.environ, Path("/etc/os-release").read_text(encoding="utf-8")
    )
    print(json.dumps({"archive": ARCHIVE, "changed": changed, "scope": "ephemeral-ci-transport-only"}))


if __name__ == "__main__":
    main()
