from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.release.contracts.browser import (
    BROWSER_ACCEPTANCE_REPORT,
    BROWSER_ACCEPTANCE_SCENARIOS,
    BROWSER_ACCEPTANCE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_browser_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("browser acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == BROWSER_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("browser acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / BROWSER_ACCEPTANCE_REPORT, "browser acceptance report")
    base_url = report.get("base_url")
    parsed_base_url = urlsplit(base_url) if isinstance(base_url, str) else urlsplit("")
    browser = report.get("browser")
    supported_browsers = {
        ("chrome", "Google Chrome"),
        ("msedge", "Microsoft Edge"),
    }
    reflow = report.get("reflow")
    if (
        report.get("schema") != BROWSER_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 9
        or report.get("status") != "passed"
        or report.get("production_claim") is not False
        or report.get("environment_kind") != "local-controlled-browser"
        or report.get("credentials_recorded") is not False
        or report.get("temporary_accounts_after") != 0
        or report.get("temporary_entities_after") != 0
        or report.get("temporary_chemistry_fixtures_after") != 0
        or not isinstance(reflow, dict)
        or reflow.get("scope") != "effective-css-viewport-equivalent"
        or reflow.get("css_widths") != [320, 360, 720]
        or reflow.get("system_zoom_verified") is not False
        or parsed_base_url.scheme not in {"http", "https"}
        or parsed_base_url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed_base_url.username is not None
        or parsed_base_url.password is not None
        or parsed_base_url.query
        or parsed_base_url.fragment
        or not isinstance(browser, dict)
        or (browser.get("channel"), browser.get("product")) not in supported_browsers
        or not isinstance(browser.get("version"), str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", browser["version"]) is None
    ):
        raise ReleaseEvidenceError("browser acceptance report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "browser acceptance statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "browser acceptance generated_at")
    maximum_age_hours = policy.categories["browser"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("browser acceptance report is outside the allowed evidence window")
    scenarios = report.get("scenarios")
    if (
        not isinstance(scenarios, dict)
        or set(scenarios) != BROWSER_ACCEPTANCE_SCENARIOS
        or not all(value is True for value in scenarios.values())
    ):
        raise ReleaseEvidenceError("browser acceptance did not pass every contracted scenario")
    tests = report.get("tests")
    test_project_keys = {"desktop_1440", "desktop_1920", "tablet_1024", "mobile_390"}
    if not isinstance(tests, dict) or set(tests) != {"total", "failed", *test_project_keys}:
        raise ReleaseEvidenceError("browser acceptance test inventory is invalid")
    total = tests.get("total")
    project_counts: list[int] = []
    for key in sorted(test_project_keys):
        value = tests.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ReleaseEvidenceError("browser acceptance test inventory is incomplete")
        project_counts.append(value)
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or any(value < 9 for value in project_counts)
        or len(set(project_counts)) != 1
        or total != sum(project_counts)
        or tests.get("failed") != 0
        or not isinstance(report.get("duration_ms"), int)
        or isinstance(report.get("duration_ms"), bool)
        or report["duration_ms"] < 1
    ):
        raise ReleaseEvidenceError("browser acceptance test inventory is incomplete")
    performance = report.get("performance")
    if (
        not isinstance(performance, dict)
        or set(performance) != {"scope", "thresholds", "projects"}
        or performance.get("scope") != "local-controlled-navigation"
        or performance.get("thresholds") != {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}
        or not isinstance(performance.get("projects"), dict)
        or set(performance["projects"]) != test_project_keys
    ):
        raise ReleaseEvidenceError("browser acceptance performance evidence is invalid")
    for metrics in performance["projects"].values():
        if not isinstance(metrics, dict) or set(metrics) != {"cls", "inp_ms", "interaction_count", "lcp_ms"}:
            raise ReleaseEvidenceError("browser acceptance performance metrics are invalid")
        cls = metrics.get("cls")
        inp_ms = metrics.get("inp_ms")
        interaction_count = metrics.get("interaction_count")
        lcp_ms = metrics.get("lcp_ms")
        if (
            not isinstance(cls, int | float)
            or isinstance(cls, bool)
            or not 0 <= cls <= 0.1
            or not isinstance(inp_ms, int | float)
            or isinstance(inp_ms, bool)
            or not 0 <= inp_ms <= 200
            or not isinstance(interaction_count, int)
            or isinstance(interaction_count, bool)
            or interaction_count < 1
            or not isinstance(lcp_ms, int | float)
            or isinstance(lcp_ms, bool)
            or not 0 < lcp_ms <= 2500
        ):
            raise ReleaseEvidenceError("browser acceptance performance budget failed")
    visual = report.get("visual_regression")
    expected_viewports = {
        "desktop_1440": ("desktop-1440", 1440, 900),
        "desktop_1920": ("desktop-1920", 1920, 1080),
        "tablet_1024": ("tablet-1024", 1024, 768),
        "mobile_390": ("mobile-390", 390, 844),
    }
    if (
        not isinstance(visual, dict)
        or set(visual) != {"baseline_kind", "comparison", "max_diff_pixel_ratio", "projects"}
        or visual.get("baseline_kind") != "repository-owned-controlled-workbench-states"
        or visual.get("comparison") != "pixel"
        or visual.get("max_diff_pixel_ratio") != 0.001
        or not isinstance(visual.get("projects"), dict)
        or set(visual["projects"]) != test_project_keys
    ):
        raise ReleaseEvidenceError("browser acceptance visual regression evidence is invalid")
    for key, expected_viewport in expected_viewports.items():
        baseline = visual["projects"].get(key)
        if (
            not isinstance(baseline, dict)
            or set(baseline) != {"project", "width", "height", "baselines"}
            or (baseline.get("project"), baseline.get("width"), baseline.get("height")) != expected_viewport
            or not isinstance(baseline.get("baselines"), dict)
            or set(baseline["baselines"])
            != {"no_result", "dense_results", "trial_outcomes", "patent_timeline", "deal_rights"}
        ):
            raise ReleaseEvidenceError("browser acceptance visual baseline inventory is invalid")
        for state, capture in (
            ("no_result", "full-page"),
            ("dense_results", "table-shell"),
            ("trial_outcomes", "dossier-section"),
            ("patent_timeline", "dossier-section"),
            ("deal_rights", "dossier-section"),
        ):
            state_baseline = baseline["baselines"].get(state)
            if (
                not isinstance(state_baseline, dict)
                or set(state_baseline) != {"capture", "sha256"}
                or state_baseline.get("capture") != capture
                or not isinstance(state_baseline.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", state_baseline["sha256"]) is None
            ):
                raise ReleaseEvidenceError("browser acceptance visual baseline inventory is invalid")
