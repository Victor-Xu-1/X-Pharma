"""Probe the installed CPython tarfile security boundary without user inputs."""

from __future__ import annotations

import io
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch


def verify_stream_eof() -> None:
    """Seeking beyond a finite stream must terminate at its actual end."""
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w"):
        pass
    payload = archive_bytes.getvalue()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r|") as archive:
        archive.fileobj.seek(len(payload) + 4096)
        if archive.fileobj.tell() != len(payload):
            raise RuntimeError("tarfile streaming seek does not stop at EOF")


def verify_hardlink_filter_rejection() -> None:
    """Hardlink copy fallback must retain a custom filter's None rejection."""
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
        member = tarfile.TarInfo("source")
        member.size = 7
        archive.addfile(member, io.BytesIO(b"fixture"))
        link = tarfile.TarInfo("copy")
        link.type = tarfile.LNKTYPE
        link.linkname = "source"
        archive.addfile(link)

    def reject_copy(member: tarfile.TarInfo, _destination: str) -> tarfile.TarInfo | None:
        if member.name == "copy" and member.isfile():
            return None
        return member

    with tempfile.TemporaryDirectory(prefix="x-pharma-tarfile-filter-probe-") as directory:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes.getvalue()), mode="r") as archive:
            with patch("tarfile.os.link", side_effect=OSError("Fixed probe forces copy fallback")):
                archive.extractall(directory, filter=reject_copy)  # noqa: S202 - Fixed fixture in a private temporary directory.
        if (Path(directory) / "copy").exists() or (Path(directory) / "source").read_bytes() != b"fixture":
            raise RuntimeError("tarfile hardlink fallback ignores filter rejection")


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
    verify_stream_eof()
    verify_hardlink_filter_rejection()
    verify_hardlink_relocation()
    print("tarfile_stream_eof=protected hardlink_filter_rejection=protected hardlink_relocation=protected")
