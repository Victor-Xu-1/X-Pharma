"""One audited ownership map; every original browser case must execute exactly once."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from scripts.browser_cases import PROJECTS, BrowserCase, collect_cases, mapping, sequence, text

Phase = Literal["controlled", "full-stack"]
PHASES: tuple[Phase, Phase] = ("controlled", "full-stack")
CONTROLLED_FILES = frozenset(
    {
        "deal-language.spec.ts",
        "patent-language.spec.ts",
        "regulatory-language.spec.ts",
        "epidemiology-language.spec.ts",
        "news-language.spec.ts",
        "environment-language.spec.ts",
        "explorer-feedback.spec.ts",
        "table-preference-intent.spec.ts",
    }
)
SCHEMA = "x-pharma.browser-phase-manifest.v1"


def fingerprint(cases: dict[str, BrowserCase]) -> str:
    records = [cases[key].record() for key in sorted(cases)]
    return hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def partition(cases: dict[str, BrowserCase], phase: Phase) -> dict[str, BrowserCase]:
    return {key: case for key, case in cases.items() if (case.file in CONTROLLED_FILES) == (phase == "controlled")}


def create_manifest(discovery: dict[str, object], revision: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("Browser manifest requires an exact clean source revision")
    cases = collect_cases(discovery)
    if not CONTROLLED_FILES.issubset({case.file for case in cases.values()}):
        raise ValueError("An audited controlled browser file is missing from original discovery")
    for phase in PHASES:
        assigned = partition(cases, phase)
        if {case.project for case in assigned.values()} != set(PROJECTS):
            raise ValueError("Both browser phases must retain every original viewport project")
    return {
        "schema": SCHEMA,
        "revision": revision,
        "case_fingerprint": fingerprint(cases),
        "cases": [cases[key].record() for key in sorted(cases)],
    }


def manifest_cases(manifest: dict[str, object]) -> dict[str, BrowserCase]:
    if manifest.get("schema") != SCHEMA or re.fullmatch(r"[0-9a-f]{40}", text(manifest.get("revision"))) is None:
        raise ValueError("Browser manifest schema or source identity is invalid")
    cases: dict[str, BrowserCase] = {}
    for item in sequence(manifest.get("cases")):
        record = mapping(item)
        case = BrowserCase(*(text(record.get(key)) for key in ("id", "project", "file", "title")))
        if case.project not in PROJECTS or case.key in cases:
            raise ValueError("Browser manifest contains an unexpected project or duplicate case")
        cases[case.key] = case
    if not cases or fingerprint(cases) != manifest.get("case_fingerprint"):
        raise ValueError("Browser manifest case fingerprint is invalid")
    for phase in PHASES:
        assigned = partition(cases, phase)
        if {case.project for case in assigned.values()} != set(PROJECTS):
            raise ValueError("Browser manifest is incomplete across its phases")
    return cases


def verify_results(manifest: dict[str, object], results: dict[str, object], phase: Phase) -> dict[str, object]:
    expected = partition(manifest_cases(manifest), phase)
    actual = collect_cases(results, passed=True)
    if actual != expected:
        raise ValueError("Browser phase omitted, duplicated, relabeled or unexpectedly executed a case")
    return {
        "phase": phase,
        "revision": manifest["revision"],
        "case_fingerprint": manifest["case_fingerprint"],
        "cases": [actual[key].record() for key in sorted(actual)],
        "passed": len(actual),
        "skipped": 0,
        "flaky": 0,
        "failed": 0,
    }


def close_coverage(
    manifest: dict[str, object], controlled: dict[str, object], full_stack: dict[str, object]
) -> dict[str, object]:
    cases = manifest_cases(manifest)
    observed: dict[str, BrowserCase] = {}
    receipts: tuple[tuple[Phase, dict[str, object]], ...] = (("controlled", controlled), ("full-stack", full_stack))
    for phase, receipt in receipts:
        if (
            receipt.get("phase") != phase
            or receipt.get("revision") != manifest["revision"]
            or receipt.get("case_fingerprint") != manifest["case_fingerprint"]
        ):
            raise ValueError("Browser phase evidence belongs to a different source, manifest or owner")
        assigned: dict[str, BrowserCase] = {}
        for item in sequence(receipt.get("cases")):
            record = mapping(item)
            case = BrowserCase(*(text(record.get(key)) for key in ("id", "project", "file", "title")))
            if case.key in assigned or case.key in observed:
                raise ValueError("Browser phase evidence executed a case more than once")
            assigned[case.key] = case
        if (
            assigned != partition(cases, phase)
            or type(receipt.get("passed")) is not int
            or receipt.get("passed") != len(assigned)
        ):
            raise ValueError("Browser phase evidence omits or changes a required case")
        if any(type(receipt.get(key)) is not int or receipt.get(key) != 0 for key in ("skipped", "flaky", "failed")):
            raise ValueError("Browser phase evidence cannot contain failures, skips or retries")
        observed.update(assigned)
    if observed != cases:
        raise ValueError("Browser phase union is not the unchanged original case set")
    return {
        "revision": manifest["revision"],
        "case_fingerprint": manifest["case_fingerprint"],
        "total": len(cases),
        "projects": {project: sum(case.project == project for case in cases.values()) for project in PROJECTS},
        "controlled": len(partition(cases, "controlled")),
        "full_stack": len(partition(cases, "full-stack")),
        "complete": True,
    }
