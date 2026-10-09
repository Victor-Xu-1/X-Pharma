from __future__ import annotations

import json
import runpy
import tomllib
from pathlib import Path


def test_cpython_security_runtime_is_pinned_without_superseded_overlays() -> None:
    root = Path(__file__).resolve().parents[1]
    reference = "python:3.13.16-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c"
    assert (root / ".python-version").read_text().strip() == "3.13.16"
    for relative, stages in (("deploy/api.Dockerfile", 2), ("services/ocr/Dockerfile", 1)):
        dockerfile = (root / relative).read_text()
        assert dockerfile.count(reference) == stages
        assert "COPY deploy/cpython/html-parser.py" not in dockerfile
        assert "COPY deploy/cpython/tarfile.py" not in dockerfile
        assert "CPYTHON_TARFILE_COMMIT" not in dockerfile
        assert "CPYTHON_HTML_PARSER_COMMIT" not in dockerfile
        assert "verify_cpython_tarfile.py" in dockerfile
        assert "verify_cpython_tls.py" in dockerfile


def test_actual_cpython_tls_client_requires_a_hostname() -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts/verify_cpython_tls.py"))
    namespace["verify_hostname_requirement"]()


def test_container_test_stage_retains_runtime_contract_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "deploy/api.Dockerfile").read_text()
    assert "COPY pyproject.toml uv.lock README.md .python-version ./" in dockerfile
    assert "COPY deploy/security ./deploy/security" in dockerfile


def test_native_descriptor_and_declared_minimum_match_the_fixed_release() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.13.16,<3.14"
    assert project["tool"]["uv"]["required-version"] == "==0.11.28"
    descriptor_path = project["tool"]["uv"]["python-downloads-json-url"]
    descriptor = json.loads((root / descriptor_path).read_text())
    assert set(descriptor) == {"cpython-3.13.16-linux-x86_64-gnu"}
    download = descriptor["cpython-3.13.16-linux-x86_64-gnu"]
    assert (download["major"], download["minor"], download["patch"]) == (3, 13, 16)
    assert download["sha256"] == "4595c5589fff7bf0cb158d9a88a797e0d791fa33830770fcb7bf3f4b104feeae"
    assert download["url"] == (
        "https://github.com/astral-sh/python-build-standalone/releases/download/20261003/"
        "cpython-3.13.16%2B20261003-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    )


def test_superseded_python_overlays_have_no_files_or_vex_suppressions() -> None:
    root = Path(__file__).resolve().parents[1]
    for filename in ("html-parser.py", "tarfile.py"):
        assert not (root / "deploy/cpython" / filename).exists()
    for filename in ("api.openvex.json", "ocr.openvex.json"):
        evidence = json.loads((root / "deploy/security" / filename).read_text())
        for statement in evidence["statements"]:
            assert statement["vulnerability"]["name"] not in {"CVE-2026-19445", "CVE-2026-19553"}
            assert all(product["@id"] != "pkg:generic/python@3.13.14" for product in statement["products"])


def test_actual_cpython_tarfile_retains_all_security_boundaries() -> None:
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "scripts/verify_cpython_tarfile.py"))
    namespace["verify_stream_eof"]()
    namespace["verify_hardlink_filter_rejection"]()
    namespace["verify_hardlink_relocation"]()
