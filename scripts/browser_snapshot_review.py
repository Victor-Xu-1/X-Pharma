"""Capture-only policy; never a substitute for the unchanged read-only browser suite."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from scripts.browser_cases import PROJECTS, BrowserCase, collect_cases, mapping, sequence
from scripts.browser_phases import manifest_cases

SCHEMA = "x-pharma.browser-snapshot-producer.v1"
CAPTURE_MARKERS = frozenset(
    {
        "[workspace-navigation]",
        "[research-workbench]",
        "[global-search-landscape]",
        "[clinical-full-result-landscape]",
        "[professional-patent-query]",
        "[professional-deal-query]",
        "[browser-quality]",
        "[web-vitals-rum]",
        "[initial-load-boundary]",
    }
)
CAPTURE_FILES = frozenset(
    f"research-{family}-{project}.png"
    for family in ("workbench", "dense-results", "trial-outcomes", "deal-rights", "patent-timeline")
    for project in PROJECTS
)


def capture_cases(manifest: dict[str, object]) -> dict[str, BrowserCase]:
    selected = {key: case for key, case in manifest_cases(manifest).items() if "[workspace-navigation]" in case.title}
    if len(selected) != len(PROJECTS) or {case.project for case in selected.values()} != set(PROJECTS):
        raise ValueError("Snapshot generation requires one original capture owner in every viewport")
    if any(
        case.file != "workspace.spec.ts" or not all(tag in case.title for tag in CAPTURE_MARKERS)
        for case in selected.values()
    ):
        raise ValueError("Snapshot generation cannot replace or relabel the original screenshot owner")
    return selected


def capture_arguments(manifest: dict[str, object]) -> list[str]:
    capture_cases(manifest)
    return [re.escape("e2e/workspace.spec.ts") + "$", "--grep", re.escape("[workspace-navigation]")]


def create_plan(manifest: dict[str, object]) -> dict[str, object]:
    cases = capture_cases(manifest)
    return {
        "schema": SCHEMA,
        "scope": "snapshot-generation-only",
        "release_evidence": False,
        "phase_manifest": manifest,
        "cases": [cases[key].record() for key in sorted(cases)],
    }


def verify_capture_results(plan: dict[str, object], results: dict[str, object]) -> dict[str, object]:
    if (
        plan.get("schema") != SCHEMA
        or plan.get("scope") != "snapshot-generation-only"
        or plan.get("release_evidence") is not False
    ):
        raise ValueError("Snapshot producer evidence cannot be used as complete browser acceptance")
    manifest = mapping(plan.get("phase_manifest"))
    expected = capture_cases(manifest)
    if sequence(plan.get("cases")) != [expected[key].record() for key in sorted(expected)]:
        raise ValueError("Snapshot producer case identities were changed")
    if collect_cases(results, passed=True) != expected:
        raise ValueError("Snapshot producer omitted, duplicated, retried or changed an original capture case")
    return {
        "schema": SCHEMA,
        "scope": "snapshot-generation-only",
        "release_evidence": False,
        "revision": manifest["revision"],
        "passed": len(expected),
        "required_captures": len(CAPTURE_FILES),
    }


def capture_scenarios(scenarios: Mapping[str, str]) -> dict[str, str]:
    selected = {name: marker for name, marker in scenarios.items() if marker in CAPTURE_MARKERS}
    if set(selected.values()) != CAPTURE_MARKERS:
        raise ValueError("The original screenshot-owner scenario contract is incomplete")
    return selected


def verify_fresh_captures(directory: Path, names: set[str] | frozenset[str], started_ns: int) -> None:
    if names != CAPTURE_FILES or type(started_ns) is not int or started_ns <= 0:
        raise ValueError("Snapshot generation must retain the complete original twenty-image inventory")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Snapshot capture directory is missing or unsafe")
    # Some supported filesystems expose only whole-second modification times.
    minimum_mtime = started_ns // 1_000_000_000 * 1_000_000_000
    for name in sorted(names):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Snapshot capture is missing, empty or unsafe: {name}")
        if path.stat().st_mtime_ns < minimum_mtime:
            raise ValueError(f"Snapshot capture belongs to an earlier producer: {name}")
