"""Probe the installed CPython tarfile security boundary without user inputs."""

from __future__ import annotations

import io
import tarfile
import tempfile
from pathlib import Path


def verify_hardlink_relocation() -> None:
    """A hard link must not relocate a relative symbolic link outside extraction."""
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
        content = b"decoy"
        member = tarfile.TarInfo("a/escape")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
        symbolic = tarfile.TarInfo("a/b/s")
        symbolic.type = tarfile.SYMTYPE
        symbolic.linkname = "../escape"
        archive.addfile(symbolic)
        hard = tarfile.TarInfo("s")
        hard.type = tarfile.LNKTYPE
        hard.linkname = "a/b/s"
        archive.addfile(hard)

    for policy in ("data", "tar"):
        with tempfile.TemporaryDirectory(prefix="x-pharma-tarfile-probe-") as directory:
            root = Path(directory)
            protected = root / "escape"
            protected.write_bytes(b"protected")
            destination = root / "extract"
            destination.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive_bytes.getvalue()), mode="r") as archive:
                archive.extractall(destination, filter=policy)  # noqa: S202 - Fixed hostile fixture; explicit filters are under test.
            relocated = destination / "s"
            if relocated.is_symlink() or relocated.read_bytes() != b"decoy" or protected.read_bytes() != b"protected":
                raise RuntimeError(f"tarfile {policy} filter permits hardlink/symlink relocation")


if __name__ == "__main__":
    verify_hardlink_relocation()
    print("tarfile_hardlink_relocation=protected")
