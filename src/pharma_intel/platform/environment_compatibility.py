from __future__ import annotations

import re
from collections.abc import Mapping

from pharma_intel.schemas.environment import EnvironmentProbeStatus

_VERSION = re.compile(r"^(?:v|Python |uv |Corepack )?(\d+)\.(\d+)(?:\.(\d+))?(?: \([A-Za-z0-9_. -]+\))?$")
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([0-9][A-Za-z0-9_.+-]*)(?:;(.+))?$")


def version_state(observed: str | None, expected: str | None) -> EnvironmentProbeStatus:
    if observed is None:
        return "missing"
    if expected is None:
        return "unverified"
    actual = _VERSION.fullmatch(observed)
    if actual is None:
        return "blocked"
    parts = tuple(int(value or 0) for value in actual.groups())
    if expected.startswith("=="):
        target = _VERSION.fullmatch(expected[2:])
        return "present" if target and parts == tuple(int(value or 0) for value in target.groups()) else "mismatch"
    major = re.fullmatch(r"(\d+)\.x", expected)
    if major:
        return "present" if parts[0] == int(major[1]) else "mismatch"
    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", expected)
    reverse_bounds = re.fullmatch(r"<(\d+)\.(\d+),>=(\d+)\.(\d+)", expected)
    if reverse_bounds:
        upper_major, upper_minor, lower_major, lower_minor = map(int, reverse_bounds.groups())
        return "present" if (lower_major, lower_minor, 0) <= parts < (upper_major, upper_minor, 0) else "mismatch"
    if bounds:
        lower_major, lower_minor, upper_major, upper_minor = map(int, bounds.groups())
        return "present" if (lower_major, lower_minor, 0) <= parts < (upper_major, upper_minor, 0) else "mismatch"
    return "unverified"


def pinned_dependencies(declarations: list[str]) -> dict[str, str]:
    result = {}
    for declaration in declarations:
        match = _PIN.fullmatch(declaration)
        if match is None:
            raise ValueError("Environment checks require explicit pinned dependency declarations")
        name, version, marker = match.groups()
        if marker:
            if re.fullmatch(r"sys_platform\s*==\s*['\"]win32['\"]", marker.strip()):
                continue  # This environment manager only supports the Linux host.
            raise ValueError("Unsupported dependency marker; compatibility cannot be asserted")
        result[re.sub(r"[-_.]+", "-", name).lower()] = version
    return result


def dependency_mismatches(expected: Mapping[str, str], installed: Mapping[str, str]) -> list[str]:
    normalized = {re.sub(r"[-_.]+", "-", name).lower(): value for name, value in installed.items()}
    return sorted(name for name, value in expected.items() if not versions_equal(normalized.get(name), value))


def versions_equal(observed: str | None, expected: str) -> bool:
    if observed is None:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)*", observed) and re.fullmatch(r"\d+(?:\.\d+)*", expected):
        return tuple(map(int, observed.split("."))) == tuple(map(int, expected.split(".")))
    return observed == expected
