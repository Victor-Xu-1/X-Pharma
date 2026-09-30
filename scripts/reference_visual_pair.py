from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SCHEMA = "pharma.reference-visual-pair.v1"
SCHEMA_VERSION = 1
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}")
SAFE_TEXT = re.compile(r"[^\x00-\x1f\x7f]{1,160}")
VIEWPORT = re.compile(r"([1-9][0-9]{1,4})x([1-9][0-9]{1,4})")
SHA256 = re.compile(r"[0-9a-f]{64}")
VISUAL_BASELINE_SCHEMA = "pharma.workbench-visual-baselines.v3"
VISUAL_BASELINE_MANIFEST_KEYS = {
    "browser",
    "contains_production_data",
    "contains_third_party_brand_assets",
    "files",
    "generated_at",
    "generator",
    "license",
    "schema",
    "schema_version",
    "source",
}
VISUAL_BASELINE_STATES = {
    ("controlled-no-result", "full-page"),
    ("controlled-dense-results", "table-shell"),
    ("controlled-trial-outcomes", "dossier-section"),
    ("controlled-patent-timeline", "dossier-section"),
    ("controlled-deal-rights", "dossier-section"),
}


class ReferenceVisualPairError(RuntimeError):
    pass


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, label: str, *, max_bytes: int) -> Path:
    if path.is_symlink():
        raise ReferenceVisualPairError(f"{label} must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise ReferenceVisualPairError(f"{label} is not readable") from exc
    if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= max_bytes:
        raise ReferenceVisualPairError(f"{label} must be a bounded regular file")
    return resolved


def _inspect_png(path: Path, label: str) -> dict[str, int | str]:
    resolved = _regular_file(path, label, max_bytes=MAX_IMAGE_BYTES)
    with resolved.open("rb") as handle:
        header = handle.read(33)
    if len(header) != 33 or header[:8] != PNG_SIGNATURE:
        raise ReferenceVisualPairError(f"{label} must be a PNG image")
    chunk_length = int.from_bytes(header[8:12], "big")
    chunk_type = header[12:16]
    chunk_data = header[16:29]
    expected_crc = int.from_bytes(header[29:33], "big")
    actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    if chunk_length != 13 or chunk_type != b"IHDR" or actual_crc != expected_crc:
        raise ReferenceVisualPairError(f"{label} has an invalid PNG IHDR")
    width = int.from_bytes(chunk_data[:4], "big")
    height = int.from_bytes(chunk_data[4:8], "big")
    if not 64 <= width <= 16384 or not 64 <= height <= 16384:
        raise ReferenceVisualPairError(f"{label} dimensions are outside the accepted bounds")
    return {
        "sha256": _sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
        "mime_type": "image/png",
        "width": width,
        "height": height,
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    resolved = _regular_file(path, label, max_bytes=MAX_JSON_BYTES)
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceVisualPairError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ReferenceVisualPairError(f"{label} must be a JSON object")
    return value


def _parse_viewport(value: str) -> tuple[int, int]:
    match = VIEWPORT.fullmatch(value)
    if match is None:
        raise ReferenceVisualPairError("viewport must use WIDTHxHEIGHT")
    width, height = (int(part) for part in match.groups())
    if width > 16384 or height > 16384:
        raise ReferenceVisualPairError("viewport dimensions exceed the accepted bounds")
    return width, height


def _safe_identifier(value: str, label: str) -> str:
    if SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ReferenceVisualPairError(f"{label} contains unsupported characters")
    return value


def _safe_text(value: str, label: str) -> str:
    normalized = " ".join(value.split())
    if SAFE_TEXT.fullmatch(normalized) is None:
        raise ReferenceVisualPairError(f"{label} must be printable and 1-160 characters")
    return normalized


def _sanitized_reference_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ReferenceVisualPairError("reference URL is malformed") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ReferenceVisualPairError(
            "reference URL must be HTTPS and must not contain credentials, query parameters, or fragments"
        )
    if port is not None and port != 443:
        raise ReferenceVisualPairError("reference URL must use the default HTTPS port")
    host = parsed.hostname.casefold()
    path = parsed.path or "/"
    return urlunsplit(("https", host, path, "", ""))


def _captured_at(value: str) -> str:
    try:
        captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReferenceVisualPairError("captured-at must be an ISO 8601 timestamp") from exc
    if captured.tzinfo is None:
        raise ReferenceVisualPairError("captured-at must include a UTC offset")
    captured_utc = captured.astimezone(UTC)
    if captured_utc > datetime.now(UTC) + timedelta(minutes=5):
        raise ReferenceVisualPairError("captured-at must not be in the future")
    return captured_utc.isoformat().replace("+00:00", "Z")


def _baseline_asset(repo: Path, platform_image: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_directory = (repo / "apps" / "web" / "e2e" / "visual-baselines").resolve(strict=True)
    image_path = _regular_file(platform_image, "platform baseline", max_bytes=MAX_IMAGE_BYTES)
    if not _is_within(image_path, baseline_directory):
        raise ReferenceVisualPairError("platform baseline must be a committed workbench visual baseline")
    manifest_path = baseline_directory / "manifest.json"
    manifest = _load_json(manifest_path, "visual baseline manifest")
    if (
        set(manifest) != VISUAL_BASELINE_MANIFEST_KEYS
        or manifest.get("schema") != VISUAL_BASELINE_SCHEMA
        or manifest.get("schema_version") != 3
        or manifest.get("generator") != "scripts/run-browser-acceptance.sh --update-snapshots"
        or manifest.get("license") != "repository-owned-test-artifact"
        or manifest.get("source")
        != "real local authenticated runtime with controlled no-result, dense-result and professional dossier queries"
        or manifest.get("contains_production_data") is not False
        or manifest.get("contains_third_party_brand_assets") is not False
        or not isinstance(manifest.get("generated_at"), str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", manifest["generated_at"]) is None
        or not isinstance(manifest.get("browser"), str)
        or re.fullmatch(r"Google Chrome [0-9]+(?:\.[0-9]+){3}", manifest["browser"]) is None
    ):
        raise ReferenceVisualPairError("visual baseline manifest has an unsupported or unsafe contract")
    files = manifest.get("files")
    entry = files.get(image_path.name) if isinstance(files, dict) else None
    if (
        not isinstance(entry, dict)
        or set(entry) != {"capture", "sha256", "state", "viewport"}
        or (entry.get("state"), entry.get("capture")) not in VISUAL_BASELINE_STATES
        or not isinstance(entry.get("sha256"), str)
        or SHA256.fullmatch(entry["sha256"]) is None
    ):
        raise ReferenceVisualPairError("platform baseline is not registered in the visual baseline manifest")
    observation = _inspect_png(image_path, "platform baseline")
    if entry.get("sha256") != observation["sha256"]:
        raise ReferenceVisualPairError("platform baseline checksum does not match its manifest")
    if not isinstance(entry.get("viewport"), str) or VIEWPORT.fullmatch(entry["viewport"]) is None:
        raise ReferenceVisualPairError("platform baseline viewport is invalid")
    return observation, manifest


def _pair_identity(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow": document["workflow"],
        "viewport": document["viewport"],
        "reference": document["reference"],
        "platform": document["platform"],
    }


def _pair_id(document: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(_pair_identity(document))).hexdigest()
    return f"sha256:{digest}"


def build_pair(
    *,
    repo: Path,
    reference_image: Path,
    platform_image: Path,
    reference_url: str,
    reference_product: str,
    reference_version: str,
    reference_artifact_id: str,
    authorization_ticket: str,
    workflow_id: str,
    workflow_title: str,
    viewport: str,
    captured_at: str,
) -> dict[str, Any]:
    repository = repo.resolve(strict=True)
    reference_path = _regular_file(reference_image, "reference image", max_bytes=MAX_IMAGE_BYTES)
    if _is_within(reference_path, repository):
        raise ReferenceVisualPairError("reference image must remain outside the source repository")
    reference = _inspect_png(reference_path, "reference image")
    platform, baseline_manifest = _baseline_asset(repository, platform_image)
    width, height = _parse_viewport(viewport)
    if reference["width"] != width or not isinstance(reference["height"], int) or reference["height"] < height:
        raise ReferenceVisualPairError("reference image does not cover the declared viewport width and height")
    if platform["width"] != width or not isinstance(platform["height"], int) or platform["height"] < height:
        raise ReferenceVisualPairError("platform baseline does not cover the declared viewport width and height")

    platform_path = _regular_file(platform_image, "platform baseline", max_bytes=MAX_IMAGE_BYTES)
    relative_platform_path = platform_path.relative_to(repository).as_posix()
    baseline_manifest_path = repository / "apps" / "web" / "e2e" / "visual-baselines" / "manifest.json"
    baseline_entry = baseline_manifest["files"][platform_path.name]
    if baseline_entry["viewport"] != viewport:
        raise ReferenceVisualPairError("platform baseline does not belong to the declared viewport")
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "registered",
        "workflow": {
            "id": _safe_identifier(workflow_id, "workflow-id"),
            "title": _safe_text(workflow_title, "workflow-title"),
        },
        "viewport": {"width": width, "height": height},
        "reference": {
            "product": _safe_text(reference_product, "reference-product"),
            "version": _safe_identifier(reference_version, "reference-version"),
            "source_url": _sanitized_reference_url(reference_url),
            "artifact_id": _safe_identifier(reference_artifact_id, "reference-artifact-id"),
            "captured_at": _captured_at(captured_at),
            "authorization": "user-authorized-observation",
            "authorization_ticket": _safe_identifier(authorization_ticket, "authorization-ticket"),
            "binary_storage": "external-evidence-store",
            "repository_embedded": False,
            **reference,
        },
        "platform": {
            "artifact_id": relative_platform_path,
            "baseline_manifest": baseline_manifest_path.relative_to(repository).as_posix(),
            "baseline_manifest_sha256": _sha256_file(baseline_manifest_path),
            "browser": _safe_text(str(baseline_manifest.get("browser", "")), "baseline browser"),
            "license": "repository-owned-test-artifact",
            "repository_embedded": True,
            **platform,
        },
        "comparison": {
            "same_viewport": True,
            "automated_equivalence_claim": False,
            "parity_claim": False,
            "review_status": "pending",
            "approval_artifact": None,
        },
        "security": {
            "credentials_recorded": False,
            "cookies_recorded": False,
            "query_parameters_recorded": False,
            "production_data_recorded": False,
            "third_party_binary_recorded_in_repository": False,
        },
    }
    document["pair_id"] = _pair_id(document)
    return document


def _require_exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ReferenceVisualPairError(f"{label} does not match the {SCHEMA} contract")
    return value


def validate_pair(document: dict[str, Any], *, repo: Path, reference_image: Path | None = None) -> None:
    expected_top_level = {
        "schema",
        "schema_version",
        "pair_id",
        "generated_at",
        "status",
        "workflow",
        "viewport",
        "reference",
        "platform",
        "comparison",
        "security",
    }
    _require_exact_keys(document, expected_top_level, "pair manifest")
    if document.get("schema") != SCHEMA or document.get("schema_version") != SCHEMA_VERSION:
        raise ReferenceVisualPairError("pair manifest schema is unsupported")
    if document.get("status") != "registered" or document.get("pair_id") != _pair_id(document):
        raise ReferenceVisualPairError("pair manifest identity is invalid")
    _captured_at(str(document.get("generated_at", "")))

    workflow = _require_exact_keys(document.get("workflow"), {"id", "title"}, "workflow")
    _safe_identifier(str(workflow.get("id", "")), "workflow id")
    _safe_text(str(workflow.get("title", "")), "workflow title")
    viewport = _require_exact_keys(document.get("viewport"), {"width", "height"}, "viewport")
    width, height = viewport.get("width"), viewport.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ReferenceVisualPairError("viewport dimensions must be integers")
    _parse_viewport(f"{width}x{height}")

    reference_keys = {
        "product",
        "version",
        "source_url",
        "artifact_id",
        "captured_at",
        "authorization",
        "authorization_ticket",
        "binary_storage",
        "repository_embedded",
        "sha256",
        "size_bytes",
        "mime_type",
        "width",
        "height",
    }
    reference = _require_exact_keys(document.get("reference"), reference_keys, "reference")
    if (
        reference.get("authorization") != "user-authorized-observation"
        or reference.get("binary_storage") != "external-evidence-store"
        or reference.get("repository_embedded") is not False
    ):
        raise ReferenceVisualPairError("reference storage and authorization declarations are invalid")
    _safe_text(str(reference.get("product", "")), "reference product")
    _safe_identifier(str(reference.get("version", "")), "reference version")
    _safe_identifier(str(reference.get("artifact_id", "")), "reference artifact id")
    _safe_identifier(str(reference.get("authorization_ticket", "")), "authorization ticket")
    _sanitized_reference_url(str(reference.get("source_url", "")))
    _captured_at(str(reference.get("captured_at", "")))

    platform_keys = {
        "artifact_id",
        "baseline_manifest",
        "baseline_manifest_sha256",
        "browser",
        "license",
        "repository_embedded",
        "sha256",
        "size_bytes",
        "mime_type",
        "width",
        "height",
    }
    platform = _require_exact_keys(document.get("platform"), platform_keys, "platform")
    if (
        platform.get("license") != "repository-owned-test-artifact"
        or platform.get("repository_embedded") is not True
        or platform.get("baseline_manifest") != "apps/web/e2e/visual-baselines/manifest.json"
    ):
        raise ReferenceVisualPairError("platform baseline declarations are invalid")
    repository = repo.resolve(strict=True)
    platform_artifact = repository / str(platform.get("artifact_id", ""))
    observation, baseline_manifest = _baseline_asset(repository, platform_artifact)
    baseline_manifest_path = repository / str(platform["baseline_manifest"])
    if platform.get("baseline_manifest_sha256") != _sha256_file(baseline_manifest_path):
        raise ReferenceVisualPairError("platform baseline manifest checksum is invalid")
    if platform.get("browser") != baseline_manifest.get("browser"):
        raise ReferenceVisualPairError("platform baseline browser does not match its manifest")
    baseline_files = baseline_manifest.get("files")
    baseline_entry = baseline_files.get(platform_artifact.name) if isinstance(baseline_files, dict) else None
    if not isinstance(baseline_entry, dict) or baseline_entry.get("viewport") != f"{width}x{height}":
        raise ReferenceVisualPairError("platform baseline does not belong to the registered viewport")

    for label, asset in (("reference", reference), ("platform", platform)):
        if (
            not isinstance(asset.get("sha256"), str)
            or SHA256.fullmatch(asset["sha256"]) is None
            or not isinstance(asset.get("size_bytes"), int)
            or not 0 < asset["size_bytes"] <= MAX_IMAGE_BYTES
            or asset.get("mime_type") != "image/png"
            or asset.get("width") != width
            or not isinstance(asset.get("height"), int)
            or asset["height"] < height
        ):
            raise ReferenceVisualPairError(f"{label} image metadata is invalid")
    if any(platform.get(field) != observation[field] for field in observation):
        raise ReferenceVisualPairError("platform baseline metadata does not match the registered image")

    comparison = _require_exact_keys(
        document.get("comparison"),
        {"same_viewport", "automated_equivalence_claim", "parity_claim", "review_status", "approval_artifact"},
        "comparison",
    )
    if comparison != {
        "same_viewport": True,
        "automated_equivalence_claim": False,
        "parity_claim": False,
        "review_status": "pending",
        "approval_artifact": None,
    }:
        raise ReferenceVisualPairError("comparison must remain pending without an automated parity claim")
    security = _require_exact_keys(
        document.get("security"),
        {
            "credentials_recorded",
            "cookies_recorded",
            "query_parameters_recorded",
            "production_data_recorded",
            "third_party_binary_recorded_in_repository",
        },
        "security",
    )
    if any(value is not False for value in security.values()):
        raise ReferenceVisualPairError("pair manifest contains a prohibited security claim")

    if reference_image is not None:
        reference_path = _regular_file(reference_image, "reference image", max_bytes=MAX_IMAGE_BYTES)
        if _is_within(reference_path, repository):
            raise ReferenceVisualPairError("reference image must remain outside the source repository")
        external = _inspect_png(reference_path, "reference image")
        if any(reference.get(field) != external[field] for field in external):
            raise ReferenceVisualPairError("external reference image does not match the pair manifest")


def _write_exclusive(path: Path, document: dict[str, Any], *, repo: Path) -> None:
    if not path.is_absolute():
        raise ReferenceVisualPairError("output must be an absolute path outside the source repository")
    if path.exists() or path.is_symlink():
        raise ReferenceVisualPairError("output already exists")
    parent = path.parent.resolve(strict=True)
    repository = repo.resolve(strict=True)
    if _is_within(parent, repository):
        raise ReferenceVisualPairError("pair manifests must be written to an external evidence store")
    payload = _canonical_json(document)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register and verify external reference visual evidence pairs")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    subcommands = parser.add_subparsers(dest="command", required=True)

    register = subcommands.add_parser(
        "register", help="Create a content-addressed pair manifest outside the repository"
    )
    register.add_argument("--reference-image", type=Path, required=True)
    register.add_argument("--platform-image", type=Path, required=True)
    register.add_argument("--reference-url", required=True)
    register.add_argument("--reference-product", required=True)
    register.add_argument("--reference-version", required=True)
    register.add_argument("--reference-artifact-id", required=True)
    register.add_argument("--authorization-ticket", required=True)
    register.add_argument("--workflow-id", required=True)
    register.add_argument("--workflow-title", required=True)
    register.add_argument("--viewport", required=True)
    register.add_argument("--captured-at", required=True)
    register.add_argument("--output", type=Path, required=True)

    verify = subcommands.add_parser("verify", help="Validate a pair manifest and its repository-owned baseline")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--reference-image", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "register":
            document = build_pair(
                repo=arguments.repo,
                reference_image=arguments.reference_image,
                platform_image=arguments.platform_image,
                reference_url=arguments.reference_url,
                reference_product=arguments.reference_product,
                reference_version=arguments.reference_version,
                reference_artifact_id=arguments.reference_artifact_id,
                authorization_ticket=arguments.authorization_ticket,
                workflow_id=arguments.workflow_id,
                workflow_title=arguments.workflow_title,
                viewport=arguments.viewport,
                captured_at=arguments.captured_at,
            )
            validate_pair(document, repo=arguments.repo, reference_image=arguments.reference_image)
            _write_exclusive(arguments.output, document, repo=arguments.repo)
            print(f"registered {document['pair_id']} at {arguments.output}")
        else:
            document = _load_json(arguments.manifest, "pair manifest")
            validate_pair(document, repo=arguments.repo, reference_image=arguments.reference_image)
            print(f"verified {document['pair_id']}")
    except ReferenceVisualPairError as exc:
        print(f"reference visual pair rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
