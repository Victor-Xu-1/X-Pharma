from __future__ import annotations

from pathlib import Path

from pharma_intel.ingest.scanner import classify_path, discover, route_dataset, sha256_file


def test_classifies_parseable_and_asset_only_files() -> None:
    assert classify_path(Path("trial.pdf")) == "parse"
    assert classify_path(Path("compound.sdf")) == "parse"
    assert classify_path(Path("compound.mol")) == "parse"
    assert classify_path(Path("protein.pdb")) == "parse"
    assert classify_path(Path("protein.cif")) == "parse"
    assert classify_path(Path("protein.mmcif")) == "parse"
    assert classify_path(Path("drawing.cdx")) == "asset"
    assert classify_path(Path("installer.exe")) == "exclude"


def test_discovers_real_files_and_excludes_admin_directories(tmp_path: Path) -> None:
    literature = tmp_path / "文献收集"
    literature.mkdir()
    paper = literature / "study.pdf"
    paper.write_bytes(b"real-pdf-placeholder-for-scanner")
    admin = tmp_path / "行政"
    admin.mkdir()
    (admin / "attendance.pdf").write_bytes(b"excluded")

    items = list(discover(tmp_path, 10_000))

    assert [item.path for item in items] == [paper]
    assert items[0].dataset_key == "literature"
    assert sha256_file(paper) == "236b2eb5149abbe1e66dcbe173b10ae8611b2ed68a13b22146f66c8e99fb247f"


def test_dataset_routing() -> None:
    assert route_dataset("专利收集/WO2024.pdf") == "patents"
    assert route_dataset("Poster/company.pptx") == "corporate"
    assert route_dataset("项目包/target.docx") == "projects"
