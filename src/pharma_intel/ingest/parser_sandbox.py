from __future__ import annotations

import hashlib
import os
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from pharma_intel.ingest.parser_protocol import ParserProcessEnvelope
from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError, ParsedDocument


class ParserSandboxError(DocumentParseError):
    pass


class ParserSandboxTimeout(ParserSandboxError):
    pass


def parse_document_in_sandbox(
    path: Path,
    max_chars: int,
    *,
    source_sha256: str | None = None,
    timeout_seconds: float = 120,
    memory_bytes: int = 2_147_483_648,
    cpu_seconds: int = 90,
) -> ParsedDocument:
    try:
        source_stat = path.lstat()
    except OSError as exc:
        raise ParserSandboxError("Parser input is unavailable") from exc
    if not stat.S_ISREG(source_stat.st_mode) or path.is_symlink():
        raise ParserSandboxError("Parser input must be a regular non-symlink file")
    if max_chars < 1:
        raise ParserSandboxError("Parser text limit must be positive")
    digest = source_sha256 or _sha256_file(path)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ParserSandboxError("Parser source digest is invalid")
    output_bytes = max_chars * 4 + 4_194_304

    with tempfile.TemporaryDirectory(prefix="pharma-parser-sandbox-") as working_directory:
        root = Path(working_directory)
        output_path = root / "result.json"
        environment = {
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": str(Path(sys.executable).parent),
            "PYTHONUTF8": "1",
            "TMPDIR": str(root),
        }
        command = [
            sys.executable,
            "-I",
            "-m",
            "pharma_intel.ingest.parser_process",
            "--input",
            str(path.resolve(strict=True)),
            "--output",
            str(output_path),
            "--source-sha256",
            digest,
            "--max-chars",
            str(max_chars),
            "--memory-bytes",
            str(memory_bytes),
            "--cpu-seconds",
            str(cpu_seconds),
            "--output-bytes",
            str(output_bytes),
        ]
        with tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(  # noqa: S603
                command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                close_fds=True,
                start_new_session=True,
            )
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                _terminate_process_group(process)
                raise ParserSandboxTimeout("The isolated parser exceeded its wall-clock limit") from exc

        if not output_path.is_file() or output_path.is_symlink():
            raise ParserSandboxError(f"The isolated parser failed with exit code {return_code}")
        if output_path.stat().st_size > output_bytes:
            raise ParserSandboxError("The isolated parser response exceeded its output limit")
        try:
            envelope = ParserProcessEnvelope.model_validate_json(output_path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise ParserSandboxError("The isolated parser returned an invalid response") from exc
        if envelope.status == "rejected" and envelope.error_code == "document_ocr_required" and envelope.error_message:
            raise DocumentOcrRequired(envelope.error_message)
        if envelope.status == "rejected" and envelope.error_message:
            raise DocumentParseError(envelope.error_message)
        if return_code != 0 or envelope.status != "succeeded" or envelope.result is None:
            raise ParserSandboxError("The isolated parser failed")
        result = envelope.result
        if result.source_sha256 != digest:
            raise ParserSandboxError("The isolated parser returned a mismatched source digest")
        calculated_text_sha256 = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
        if result.text_sha256 != calculated_text_sha256:
            raise ParserSandboxError("The isolated parser returned a mismatched text digest")
        return ParsedDocument(result.text, result.metadata, result.parser_name, result.parser_version)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
