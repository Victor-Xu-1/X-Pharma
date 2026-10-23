from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.browser_cases import PROJECTS, collect_cases, mapping, sequence
from scripts.browser_phases import (
    COMPANY_FILES,
    CONTROLLED_FILES,
    close_coverage,
    create_manifest,
    manifest_cases,
    partition,
    verify_results,
)


def report(files: set[str], *, executed: bool = False) -> dict[str, object]:
    specs = []
    for project in PROJECTS:
        for filename in sorted(files):
            specs.append(
                {
                    "id": f"{project}-{filename}",
                    "title": f"Original {filename}",
                    "file": filename,
                    "tests": [
                        {
                            "projectName": project,
                            "expectedStatus": "passed",
                            "status": "expected",
                            "results": [{"status": "passed", "retry": 0}] if executed else [],
                        }
                    ],
                }
            )
    return {
        "suites": [{"specs": specs}],
        "errors": [],
        "stats": {"expected": len(specs) if executed else 0, "unexpected": 0, "flaky": 0, "skipped": 0},
    }


def receipts() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    manifest = create_manifest(report(set(CONTROLLED_FILES | COMPANY_FILES) | {"workspace.spec.ts"}), "a" * 40)
    controlled = verify_results(manifest, report(set(CONTROLLED_FILES), executed=True), "controlled")
    stack = verify_results(manifest, report({"workspace.spec.ts"}, executed=True), "full-stack")
    company = verify_results(manifest, report(set(COMPANY_FILES), executed=True), "company-controlled")
    return manifest, controlled, stack, company


def test_original_case_set_is_partitioned_once_across_all_four_projects() -> None:
    manifest, controlled, stack, company = receipts()
    result = close_coverage(manifest, controlled, stack, company=company)
    assert result["complete"] is True
    assert result["total"] == 40
    assert result["controlled"] == 32
    assert result["full_stack"] == 4
    assert result["company_controlled"] == 4
    assert result["projects"] == {project: 10 for project in PROJECTS}


def test_new_unclassified_cases_stay_required_in_the_real_stack() -> None:
    files = set(CONTROLLED_FILES | COMPANY_FILES) | {"workspace.spec.ts", "new-real-api.spec.ts"}
    manifest = create_manifest(report(files), "a" * 40)
    with pytest.raises(ValueError, match="omitted"):
        verify_results(manifest, report({"workspace.spec.ts"}, executed=True), "full-stack")


def test_audited_company_cases_do_not_consume_the_real_stack_deadline() -> None:
    manifest = create_manifest(
        report(set(CONTROLLED_FILES) | {"workspace.spec.ts", "company-language.spec.ts"}), "a" * 40
    )
    stack = partition(manifest_cases(manifest), "full-stack")
    assert {case.file for case in stack.values()} == {"workspace.spec.ts"}
    assert {case.project for case in stack.values()} == set(PROJECTS)


@pytest.mark.parametrize("field", ["skipped", "flaky", "unexpected"])
@pytest.mark.parametrize("value", [1, False, None])
def test_results_reject_skips_failures_flakiness_and_invalid_counts(field: str, value: object) -> None:
    value_report = report(set(CONTROLLED_FILES), executed=True)
    mapping(value_report["stats"])[field] = value
    with pytest.raises(ValueError):
        collect_cases(value_report, passed=True)


@pytest.mark.parametrize("change", ["missing", "duplicate", "foreign-source", "wrong-owner", "changed-case"])
@pytest.mark.parametrize("owner", ["controlled", "company"])
def test_phase_closure_rejects_missing_duplicate_foreign_or_relabeled_evidence(change: str, owner: str) -> None:
    manifest, controlled, stack, company = receipts()
    invalid = deepcopy(controlled if owner == "controlled" else company)
    if change == "missing":
        sequence(invalid["cases"]).pop()
    elif change == "duplicate":
        sequence(invalid["cases"]).append(sequence(invalid["cases"])[0])
    elif change == "foreign-source":
        invalid["revision"] = "b" * 40
    elif change == "wrong-owner":
        invalid["phase"] = "full-stack"
    else:
        mapping(sequence(invalid["cases"])[0])["title"] = "Different assertion owner"
    with pytest.raises(ValueError):
        close_coverage(
            manifest,
            invalid if owner == "controlled" else controlled,
            stack,
            company=invalid if owner == "company" else company,
        )


def test_discovery_requires_every_audited_file_and_does_not_accept_one_viewport() -> None:
    with pytest.raises(ValueError, match="missing"):
        create_manifest(report({"workspace.spec.ts"}), "a" * 40)
    partial = report(set(CONTROLLED_FILES | COMPANY_FILES) | {"workspace.spec.ts"})
    suite = mapping(sequence(partial["suites"])[0])
    suite["specs"] = sequence(suite["specs"])[:1]
    with pytest.raises(ValueError, match="four"):
        create_manifest(partial, "a" * 40)


@pytest.mark.parametrize("field", ["skipped", "flaky", "failed"])
@pytest.mark.parametrize("value", [False, None, "0"])
def test_phase_receipts_require_integer_zero_counts(field: str, value: object) -> None:
    manifest, controlled, stack, company = receipts()
    controlled[field] = value
    with pytest.raises(ValueError):
        close_coverage(manifest, controlled, stack, company=company)


def test_execution_retry_count_cannot_be_a_boolean() -> None:
    executed = report(set(CONTROLLED_FILES), executed=True)
    suite = mapping(sequence(executed["suites"])[0])
    spec = mapping(sequence(suite["specs"])[0])
    test = mapping(sequence(spec["tests"])[0])
    mapping(sequence(test["results"])[0])["retry"] = False
    with pytest.raises(ValueError):
        collect_cases(executed, passed=True)
