"""Prepare and verify an isolated capture producer without publishing release acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.browser_cases import mapping
from scripts.browser_phase_runtime import discover, load, save, source_revision, validate_destination
from scripts.browser_snapshot_review import (
    CAPTURE_FILES,
    capture_arguments,
    create_plan,
    verify_capture_results,
    verify_fresh_captures,
)


def prepare(manifest_path: Path, arguments_path: Path) -> None:
    validate_destination(manifest_path)
    validate_destination(arguments_path)
    capture_directory = manifest_path.parent / "snapshots"
    if capture_directory.exists() or capture_directory.is_symlink():
        raise FileExistsError(capture_directory)
    manifest = discover()
    plan = create_plan(manifest)
    capture_directory.mkdir(mode=0o700)
    save(manifest_path, plan)
    with arguments_path.open("x", encoding="utf-8") as output:
        output.write("\n".join(capture_arguments(manifest)) + "\n")


def verify(manifest_path: Path, results_path: Path, started_ns: int) -> dict[str, object]:
    plan = load(manifest_path)
    if mapping(plan.get("phase_manifest")).get("revision") != source_revision():
        raise ValueError("Source changed during isolated screenshot generation")
    result = verify_capture_results(plan, load(results_path))
    verify_fresh_captures(manifest_path.parent / "snapshots", CAPTURE_FILES, started_ns)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparing = commands.add_parser("prepare")
    preparing.add_argument("--manifest", type=Path, required=True)
    preparing.add_argument("--arguments", type=Path, required=True)
    verifying = commands.add_parser("verify")
    verifying.add_argument("--manifest", type=Path, required=True)
    verifying.add_argument("--results", type=Path, required=True)
    verifying.add_argument("--started-ns", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.manifest, args.arguments)
    else:
        print(json.dumps(verify(args.manifest, args.results, args.started_ns), sort_keys=True))


if __name__ == "__main__":
    main()
