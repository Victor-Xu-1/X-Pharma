from __future__ import annotations

import json
import stat
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from scripts import reference_visual_pair as visual_pair


def _png(path: Path, width: int, height: int, *, color: tuple[int, int, int] = (17, 77, 121)) -> Path:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    row = b"\x00" + bytes((*color, 255)) * width
    pixels = row * height
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        visual_pair.PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels, level=9))
        + chunk(b"IEND", b"")
    )
    return path


def _build(repo: Path, tmp_path: Path, *, viewport: str = "390x844") -> tuple[dict[str, Any], Path]:
    width, height = (int(value) for value in viewport.split("x"))
    reference = _png(tmp_path / "authorized-reference.png", width, height)
    platform = repo / "apps" / "web" / "e2e" / "visual-baselines" / "research-workbench-mobile-390.png"
    document = visual_pair.build_pair(
        repo=repo,
        reference_image=reference,
        platform_image=platform,
        reference_url="https://reference.example.test/drugde/index",
        reference_product="Approved reference workbench",
        reference_version="web-2026.07.26",
        reference_artifact_id="visual-ref-mobile-001",
        authorization_ticket="review-authorization-001",
        workflow_id="professional-composite-query",
        workflow_title="Professional composite query and governed result review",
        viewport=viewport,
        captured_at="2026-07-24T00:00:00Z",
    )
    return document, reference


def test_pair_manifest_is_schema_valid_content_addressed_and_path_free(tmp_path: Path) -> None:
    repo = Path(__file__).parents[1]
    document, reference = _build(repo, tmp_path)
    schema = json.loads((repo / "deploy" / "release" / "reference-visual-pair.schema.json").read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    visual_pair.validate_pair(document, repo=repo, reference_image=reference)
    serialized = json.dumps(document)

    assert document["pair_id"].startswith("sha256:")
    assert str(reference) not in serialized
    assert "?" not in document["reference"]["source_url"]
    assert document["comparison"]["parity_claim"] is False
    assert document["security"] == {
        "credentials_recorded": False,
        "cookies_recorded": False,
        "query_parameters_recorded": False,
        "production_data_recorded": False,
        "third_party_binary_recorded_in_repository": False,
    }


def test_pair_manifest_is_exclusively_written_outside_repository_with_private_permissions(tmp_path: Path) -> None:
    repo = Path(__file__).parents[1]
    document, _reference = _build(repo, tmp_path)
    output = tmp_path / "pair.json"

    visual_pair._write_exclusive(output, document, repo=repo)

    assert json.loads(output.read_text(encoding="utf-8")) == document
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(visual_pair.ReferenceVisualPairError, match="already exists"):
        visual_pair._write_exclusive(output, document, repo=repo)


def test_pair_registration_rejects_reference_images_inside_repository() -> None:
    repo = Path(__file__).parents[1]
    platform = repo / "apps" / "web" / "e2e" / "visual-baselines" / "research-workbench-mobile-390.png"

    with pytest.raises(visual_pair.ReferenceVisualPairError, match="outside the source repository"):
        visual_pair.build_pair(
            repo=repo,
            reference_image=platform,
            platform_image=platform,
            reference_url="https://reference.example.test/drugde/index",
            reference_product="Approved reference workbench",
            reference_version="web-2026.07.26",
            reference_artifact_id="visual-ref-mobile-001",
            authorization_ticket="review-authorization-001",
            workflow_id="professional-composite-query",
            workflow_title="Professional composite query",
            viewport="390x844",
            captured_at="2026-07-24T00:00:00Z",
        )


def test_pair_registration_rejects_mismatched_viewports_and_sensitive_urls(tmp_path: Path) -> None:
    repo = Path(__file__).parents[1]
    reference = _png(tmp_path / "reference.png", 390, 844)
    platform = repo / "apps" / "web" / "e2e" / "visual-baselines" / "research-workbench-mobile-390.png"
    arguments: dict[str, Any] = {
        "repo": repo,
        "reference_image": reference,
        "platform_image": platform,
        "reference_url": "https://reference.example.test/drugde/index",
        "reference_product": "Approved reference workbench",
        "reference_version": "web-2026.07.26",
        "reference_artifact_id": "visual-ref-mobile-001",
        "authorization_ticket": "review-authorization-001",
        "workflow_id": "professional-composite-query",
        "workflow_title": "Professional composite query",
        "viewport": "390x900",
        "captured_at": "2026-07-24T00:00:00Z",
    }

    with pytest.raises(visual_pair.ReferenceVisualPairError, match="declared viewport"):
        visual_pair.build_pair(**arguments)

    arguments["viewport"] = "390x844"
    arguments["reference_url"] = "https://reference.example.test/drugde/index?token=secret"
    with pytest.raises(visual_pair.ReferenceVisualPairError, match="query parameters"):
        visual_pair.build_pair(**arguments)

    arguments["reference_url"] = "https://reference.example.test:not-a-port/drugde/index"
    with pytest.raises(visual_pair.ReferenceVisualPairError, match="malformed"):
        visual_pair.build_pair(**arguments)


def test_pair_verification_rejects_identity_and_external_binary_tampering(tmp_path: Path) -> None:
    repo = Path(__file__).parents[1]
    document, reference = _build(repo, tmp_path)
    document["workflow"]["title"] = "Tampered workflow"

    with pytest.raises(visual_pair.ReferenceVisualPairError, match="identity is invalid"):
        visual_pair.validate_pair(document, repo=repo, reference_image=reference)

    document, reference = _build(repo, tmp_path)
    _png(reference, 390, 844, color=(141, 31, 88))
    with pytest.raises(visual_pair.ReferenceVisualPairError, match="does not match"):
        visual_pair.validate_pair(document, repo=repo, reference_image=reference)


def test_pair_manifest_output_is_rejected_inside_repository(tmp_path: Path) -> None:
    repo = Path(__file__).parents[1]
    document, _reference = _build(repo, tmp_path)
    forbidden = repo / "tests" / "__reference_visual_pair_forbidden.json"

    assert not forbidden.exists()
    with pytest.raises(visual_pair.ReferenceVisualPairError, match="external evidence store"):
        visual_pair._write_exclusive(forbidden, document, repo=repo)
    assert not forbidden.exists()
