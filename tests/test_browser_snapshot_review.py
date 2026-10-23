from __future__ import annotations

import json
import os
import re
import time
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import browser_snapshot_cli as cli
from scripts.browser_cases import PROJECTS, mapping, sequence
from scripts.browser_phases import COMPANY_FILES, CONTROLLED_FILES, create_manifest, manifest_cases
from scripts.browser_snapshot_review import (
    CAPTURE_FILES,
    CAPTURE_MARKERS,
    capture_arguments,
    capture_cases,
    capture_scenarios,
    create_plan,
    verify_capture_results,
    verify_fresh_captures,
)
from tests.test_browser_phases import report


def capture_report(*, executed: bool = False, capture_only: bool = False) -> dict[str, object]:
    value = report(set(CONTROLLED_FILES | COMPANY_FILES) | {"workspace.spec.ts"}, executed=executed)
    suite = mapping(sequence(value["suites"])[0])
    specs = sequence(suite["specs"])
    for item in specs:
        spec = mapping(item)
        if spec["file"] == "workspace.spec.ts":
            spec["title"] = "".join(sorted(CAPTURE_MARKERS)) + " original navigation"
    if capture_only:
        suite["specs"] = [item for item in specs if mapping(item)["file"] == "workspace.spec.ts"]
        mapping(value["stats"])["expected"] = len(PROJECTS) if executed else 0
    return value


def manifest() -> dict[str, object]:
    return create_manifest(capture_report(), "a" * 40)


def test_generation_selects_four_original_owners_without_claiming_complete_coverage() -> None:
    original = manifest()
    before = deepcopy(original)
    selected = capture_cases(original)
    assert len(manifest_cases(original)) == 40
    assert len(selected) == 4
    assert {case.project for case in selected.values()} == set(PROJECTS)
    assert original == before
    arguments = capture_arguments(original)
    assert arguments[0] == r"e2e/workspace\.spec\.ts$"
    assert arguments[1] == "--grep"
    assert re.fullmatch(arguments[2], "[workspace-navigation]")
    result = verify_capture_results(create_plan(original), capture_report(executed=True, capture_only=True))
    assert result["passed"] == 4 and result["required_captures"] == 20
    assert result["release_evidence"] is False
    assert result["scope"] == "snapshot-generation-only"


@pytest.mark.parametrize("change", ["missing-project", "extra-owner", "different-file", "missing-domain"])
def test_capture_owner_discovery_rejects_ambiguous_missing_or_replaced_cases(change: str) -> None:
    discovery = capture_report()
    specs = sequence(mapping(sequence(discovery["suites"])[0])["specs"])
    owner = next(mapping(item) for item in specs if mapping(item)["file"] == "workspace.spec.ts")
    if change == "missing-project":
        owner["title"] = "original without the capture marker"
    elif change == "extra-owner":
        extra = deepcopy(owner)
        extra["id"] = "additional-owner"
        specs.append(extra)
    elif change == "different-file":
        owner["file"] = "another.spec.ts"
    else:
        owner["title"] = str(owner["title"]).replace("[professional-deal-query]", "")
    with pytest.raises(ValueError):
        capture_cases(create_manifest(discovery, "a" * 40))


@pytest.mark.parametrize(
    "change", ["missing", "extra", "relabeled", "retry", "two-results", "flaky", "skipped", "wrong-count"]
)
def test_producer_requires_exact_same_source_cases_passing_once(change: str) -> None:
    results = capture_report(executed=True, capture_only=True)
    specs = sequence(mapping(sequence(results["suites"])[0])["specs"])
    first = mapping(specs[0])
    test = mapping(sequence(first["tests"])[0])
    if change == "missing":
        specs.pop()
        mapping(results["stats"])["expected"] = 3
    elif change == "extra":
        results = capture_report(executed=True)
    elif change == "relabeled":
        first["title"] = str(first["title"]) + " changed"
    elif change == "retry":
        mapping(sequence(test["results"])[0])["retry"] = 1
    elif change == "two-results":
        sequence(test["results"]).append({"status": "passed", "retry": 1})
    else:
        mapping(results["stats"])[{"flaky": "flaky", "skipped": "skipped", "wrong-count": "expected"}[change]] = 1
    with pytest.raises(ValueError):
        verify_capture_results(create_plan(manifest()), results)


@pytest.mark.parametrize("change", ["release-claim", "wrong-scope", "changed-identities", "bad-fingerprint"])
def test_capture_plan_cannot_be_used_as_a_release_or_foreign_inventory(change: str) -> None:
    plan = create_plan(manifest())
    if change == "release-claim":
        plan["release_evidence"] = True
    elif change == "wrong-scope":
        plan["scope"] = "complete"
    elif change == "changed-identities":
        sequence(plan["cases"]).pop()
    else:
        mapping(plan["phase_manifest"])["case_fingerprint"] = "f" * 64
    with pytest.raises(ValueError):
        verify_capture_results(plan, capture_report(executed=True, capture_only=True))


def test_generation_has_only_its_capture_markers_but_does_not_mutate_readonly_requirements() -> None:
    original = {str(index): value for index, value in enumerate(sorted(CAPTURE_MARKERS))}
    original["additional"] = "[accessibility]"
    before = original.copy()
    assert set(capture_scenarios(original).values()) == CAPTURE_MARKERS
    assert original == before and original["additional"] == "[accessibility]"
    original.pop("0")
    with pytest.raises(ValueError):
        capture_scenarios(original)


def fresh_captures(directory: Path) -> int:
    directory.mkdir()
    started = time.time_ns()
    for name in CAPTURE_FILES:
        (directory / name).write_bytes(b"controlled capture-file fixture")
    return started


def test_all_original_capture_families_and_viewports_must_be_fresh(tmp_path: Path) -> None:
    directory = tmp_path / "snapshots"
    started = fresh_captures(directory)
    assert len(CAPTURE_FILES) == 20
    verify_fresh_captures(directory, CAPTURE_FILES, started)
    with pytest.raises(ValueError):
        verify_fresh_captures(directory, frozenset(list(CAPTURE_FILES)[:19]), started)


@pytest.mark.parametrize("change", ["old", "missing", "empty", "symlink", "directory-symlink", "invalid-clock"])
def test_stale_missing_or_unsafe_captures_cannot_be_promoted(tmp_path: Path, change: str) -> None:
    directory = tmp_path / "snapshots"
    started = fresh_captures(directory)
    path = directory / sorted(CAPTURE_FILES)[0]
    if change == "old":
        os.utime(path, ns=(started - 2_000_000_000, started - 2_000_000_000))
    elif change == "missing":
        path.unlink()
    elif change == "empty":
        path.write_bytes(b"")
    elif change == "symlink":
        outside = tmp_path / "outside.png"
        outside.write_bytes(b"preserved fixture")
        path.unlink()
        path.symlink_to(outside)
    elif change == "directory-symlink":
        link = tmp_path / "alias"
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    else:
        started = 0
    with pytest.raises(ValueError):
        verify_fresh_captures(directory, CAPTURE_FILES, started)


def test_prepare_isolated_output_and_verify_do_not_modify_committed_baselines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "discover", manifest)
    plan, arguments = tmp_path / "plan.json", tmp_path / "arguments"
    cli.prepare(plan, arguments)
    directory = tmp_path / "snapshots"
    assert directory.is_dir() and not list(directory.iterdir())
    assert arguments.read_text().splitlines() == capture_arguments(manifest())
    started = time.time_ns()
    for name in CAPTURE_FILES:
        (directory / name).write_bytes(b"controlled capture-file fixture")
    results = tmp_path / "results.json"
    results.write_text(json.dumps(capture_report(executed=True, capture_only=True)), encoding="utf-8")
    monkeypatch.setattr(cli, "source_revision", lambda: "a" * 40)
    assert cli.verify(plan, results, started)["release_evidence"] is False
    monkeypatch.setattr(cli, "source_revision", lambda: "b" * 40)
    with pytest.raises(ValueError, match="Source changed"):
        cli.verify(plan, results, started)


def test_existing_plan_destination_is_never_overwritten_before_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text("existing immutable evidence", encoding="utf-8")
    monkeypatch.setattr(cli, "discover", lambda: pytest.fail("must not discover after an invalid destination"))
    with pytest.raises(FileExistsError):
        cli.prepare(plan, tmp_path / "arguments")
    assert plan.read_text() == "existing immutable evidence"
