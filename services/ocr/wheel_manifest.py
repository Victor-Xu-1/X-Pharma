"""Bind locally built wheels to the complete, already hash-verified runtime lock."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version


def wheel_manifest(lock: Path, directory: Path) -> str:
    expected: dict[str, Version] = {}
    for line in lock.read_text().splitlines():
        if not line or line.startswith(("#", " ")):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)(?: \\)?", line)
        if match is None:
            raise ValueError("Unsupported runtime lock entry")
        name = canonicalize_name(match[1])
        if name in expected:
            raise ValueError("Duplicate runtime lock distribution")
        expected[name] = Version(match[2])
    found: dict[str, tuple[Version, str]] = {}
    for wheel in sorted(directory.glob("*.whl")):
        if wheel.is_symlink() or not wheel.is_file():
            raise ValueError("Wheel is not a regular file")
        name, version, _, _ = parse_wheel_filename(wheel.name)
        if name in found or expected.get(name) != version:
            raise ValueError("Unexpected, duplicate or wrong-version wheel")
        with wheel.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        found[name] = (version, digest)
    if not expected or set(found) != set(expected):
        raise ValueError("Built wheel inventory does not match the complete runtime lock")
    return (
        "\n".join(f"{name}=={version} --hash=sha256:{digest}" for name, (version, digest) in sorted(found.items()))
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(wheel_manifest(args.lock, args.directory), end="")


if __name__ == "__main__":
    main()
