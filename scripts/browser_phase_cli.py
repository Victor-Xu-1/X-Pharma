"""Explicit CI partition commands; ordinary browser acceptance still defaults to all cases."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from scripts.browser_cases import mapping
from scripts.browser_phase_runtime import discover, load, phase_arguments, save, source_revision, validate_destination
from scripts.browser_phases import PHASES, Phase, close_coverage, verify_results


def attach(manifest_path: Path, results_path: Path, report_path: Path, phase: Phase) -> None:
    manifest = load(manifest_path)
    if manifest["revision"] != source_revision():
        raise ValueError("Browser source changed during phase execution")
    coverage = verify_results(manifest, load(results_path), phase)
    report = load(report_path)
    if report.get("status") != "passed" or mapping(report.get("tests")).get("total") != coverage["passed"]:
        raise ValueError("Validated browser report and exact executed case count differ")
    report["case_coverage"] = coverage
    report["phase_manifest"] = manifest
    # The original report has already been atomically written by its owner.
    # Attach coverage to a distinct immutable file; never overwrite prior evidence.
    save(report_path.with_name(f"{report_path.stem}-verified.json"), report)


def close(stack_path: Path, controlled_path: Path, output: Path, *, company_path: Path) -> None:
    stack, controlled, company = load(stack_path), load(controlled_path), load(company_path)
    manifest = mapping(stack.get("phase_manifest"))
    if (
        any(manifest != receipt.get("phase_manifest") for receipt in (controlled, company))
        or manifest.get("revision") != source_revision()
    ):
        raise ValueError("Browser phase artifacts do not bind the same current source and original discovery")
    if any(receipt.get("status") != "passed" for receipt in (stack, controlled, company)):
        raise ValueError("All three required browser phases must have passed")
    browser = mapping(stack.get("browser"))
    for receipt in (controlled, company):
        if (
            receipt.get("schema") != "x-pharma.controlled-browser-acceptance.v1"
            or receipt.get("real_backend") is not False
            or receipt.get("browser") != f"{browser.get('product')} {browser.get('version')}"
        ):
            raise ValueError(
                "Controlled evidence must retain the same verified browser profile and isolated backend boundary"
            )
    coverage = close_coverage(
        manifest,
        mapping(controlled.get("case_coverage")),
        mapping(stack.get("case_coverage")),
        company=mapping(company.get("case_coverage")),
    )
    tests = mapping(stack.get("tests")).copy()
    projects = mapping(coverage["projects"])
    tests.update(
        {
            "total": coverage["total"],
            "desktop_1440": projects["desktop-1440"],
            "desktop_1920": projects["desktop-1920"],
            "tablet_1024": projects["tablet-1024"],
            "mobile_390": projects["mobile-390"],
        }
    )
    stack["tests"] = tests
    stack["stack_case_coverage"] = stack["case_coverage"]
    stack["case_coverage"] = {
        "phase": "complete",
        "revision": coverage["revision"],
        "case_fingerprint": coverage["case_fingerprint"],
        "cases": manifest["cases"],
        "passed": coverage["total"],
    }
    stack["execution_phases"] = coverage
    save(output, stack)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--phase", choices=PHASES, required=True)
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--arguments", type=Path, required=True)
    attaching = commands.add_parser("attach")
    attaching.add_argument("--phase", choices=PHASES, required=True)
    attaching.add_argument("--manifest", type=Path, required=True)
    attaching.add_argument("--results", type=Path, required=True)
    attaching.add_argument("--report", type=Path, required=True)
    closing = commands.add_parser("close")
    closing.add_argument("--stack", type=Path, required=True)
    closing.add_argument("--controlled", type=Path, required=True)
    closing.add_argument("--company", type=Path, required=True)
    closing.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        validate_destination(args.manifest)
        manifest = discover()
        save(args.manifest, manifest)
        with args.arguments.open("x", encoding="utf-8") as handle:
            handle.write("\n".join(phase_arguments(manifest, cast(Phase, args.phase))) + "\n")
    elif args.command == "attach":
        attach(args.manifest, args.results, args.report, cast(Phase, args.phase))
    else:
        close(args.stack, args.controlled, args.output, company_path=args.company)


if __name__ == "__main__":
    main()
