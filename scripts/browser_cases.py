"""Strict identities and result validation shared by browser execution phases."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import cast

PROJECTS = ("desktop-1440", "desktop-1920", "tablet-1024", "mobile-390")


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Browser evidence must contain a JSON object")
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("Browser evidence must contain a JSON array")
    return cast(list[object], value)


def text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Browser case identity must be a nonempty string")
    return value


@dataclass(frozen=True)
class BrowserCase:
    id: str
    project: str
    file: str
    title: str

    def __post_init__(self) -> None:
        for value in (self.id, self.project, self.file, self.title):
            text(value)
        path = PurePosixPath(self.file)
        if (
            self.project not in PROJECTS
            or path.is_absolute()
            or ".." in path.parts
            or re.fullmatch(r"[A-Za-z0-9_/.-]+\.spec\.[jt]sx?", self.file) is None
        ):
            raise ValueError("Browser case identity must retain its original project and safe relative file")

    @property
    def key(self) -> str:
        return f"{self.project}:{self.id}"

    def record(self) -> dict[str, str]:
        return asdict(self)


def collect_cases(report: dict[str, object], *, passed: bool = False) -> dict[str, BrowserCase]:
    if sequence(report.get("errors", [])):
        raise ValueError("Playwright reported collection or execution errors")
    cases: dict[str, BrowserCase] = {}
    pending = sequence(report.get("suites"))[:]
    while pending:
        suite = mapping(pending.pop())
        pending.extend(sequence(suite.get("suites", [])))
        for item in sequence(suite.get("specs", [])):
            spec = mapping(item)
            filename = text(spec.get("file"))
            path = PurePosixPath(filename)
            if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or "\\" in filename:
                raise ValueError("Browser case file must remain relative to the original test directory")
            for item_test in sequence(spec.get("tests")):
                test = mapping(item_test)
                project = text(test.get("projectName"))
                if project not in PROJECTS or test.get("expectedStatus") != "passed":
                    raise ValueError("Browser cases must retain all original projects and expected passing status")
                case = BrowserCase(text(spec.get("id")), project, filename, text(spec.get("title")))
                if case.key in cases:
                    raise ValueError("Duplicate browser case identity")
                if passed:
                    results = sequence(test.get("results"))
                    if test.get("status") != "expected" or len(results) != 1:
                        raise ValueError("Browser cases cannot fail, skip, retry or become flaky")
                    result = mapping(results[0])
                    if (
                        result.get("status") != "passed"
                        or type(result.get("retry")) is not int
                        or result.get("retry") != 0
                    ):
                        raise ValueError("Every browser case must pass on its original attempt")
                cases[case.key] = case
    if not cases or {case.project for case in cases.values()} != set(PROJECTS):
        raise ValueError("Browser evidence is incomplete across the original four projects")
    if passed:
        stats = mapping(report.get("stats"))
        expected = stats.get("expected")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected != len(cases):
            raise ValueError("Playwright passing count differs from its case identities")
        if any(type(stats.get(key)) is not int or stats.get(key) != 0 for key in ("unexpected", "flaky", "skipped")):
            raise ValueError("Browser evidence contains failed, flaky or skipped tests")
    return cases
