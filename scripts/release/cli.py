from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.release.audit import audit_release
from scripts.release.batch import register_production_evidence_batch
from scripts.release.bundle import assemble_bundle
from scripts.release.capture import capture_gate
from scripts.release.handoff import prepare_production_evidence_handoff
from scripts.release.handoff_verification import (
    verify_production_evidence_handoff,
    verify_production_evidence_handoff_offline,
)
from scripts.release.intake import register_production_evidence
from scripts.release.io import _atomic_write, _canonical_json
from scripts.release.policy import production_evidence_requirements
from scripts.release.records import ReleaseEvidenceError
from scripts.release.statements import collect_release_statements
from scripts.release.verification import verify_bundle


def _default_policy(repo: Path) -> Path:
    return repo / "deploy" / "release" / "evidence-policy.json"


def _add_repository_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture, assemble and verify release evidence")
    commands = parser.add_subparsers(dest="action", required=True)

    capture_parser = commands.add_parser(
        "capture", help="Run one gate and bind its result to the current release subject"
    )
    _add_repository_arguments(capture_parser)
    capture_parser.add_argument("--category", required=True)
    capture_parser.add_argument("--security-dir", type=Path, required=True)
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--attachment", type=Path, action="append", default=[])
    capture_parser.add_argument("--log-attachment", type=Path)
    capture_parser.add_argument("command", nargs=argparse.REMAINDER)

    register_parser = commands.add_parser(
        "register-production",
        help="Atomically bind real external production artifacts and approvals to the current release subject",
    )
    _add_repository_arguments(register_parser)
    register_parser.add_argument("--security-dir", type=Path, required=True)
    register_parser.add_argument("--request", type=Path, required=True)
    register_parser.add_argument("--output", type=Path, required=True)

    requirements_parser = commands.add_parser(
        "production-requirements",
        help="Print the exact checks, approvals and artifact threshold for one production category",
    )
    _add_repository_arguments(requirements_parser)
    requirements_parser.add_argument("--category", required=True)
    requirements_parser.add_argument("--output", type=Path)

    handoff_parser = commands.add_parser(
        "prepare-production-handoff",
        help="Atomically publish the authoritative external production evidence requirements",
    )
    _add_repository_arguments(handoff_parser)
    handoff_parser.add_argument("--output", type=Path, required=True)
    handoff_parser.add_argument("--signing-key", type=Path)
    handoff_parser.add_argument("--signing-key-id")

    handoff_verify_parser = commands.add_parser(
        "verify-production-handoff",
        help="Verify a requirements handoff against the current committed production policy",
    )
    _add_repository_arguments(handoff_verify_parser)
    handoff_verify_parser.add_argument("--handoff", type=Path, required=True)
    handoff_verify_parser.add_argument("--trusted-public-key", type=Path)

    handoff_offline_parser = commands.add_parser(
        "verify-production-handoff-offline",
        help="Verify a signed requirements handoff without a source repository",
    )
    handoff_offline_parser.add_argument("--handoff", type=Path, required=True)
    handoff_offline_parser.add_argument("--trusted-public-key", type=Path, required=True)

    batch_parser = commands.add_parser(
        "register-production-batch",
        help="Atomically register every external production evidence category",
    )
    _add_repository_arguments(batch_parser)
    batch_parser.add_argument("--security-dir", type=Path, required=True)
    batch_parser.add_argument("--manifest", type=Path, required=True)
    batch_parser.add_argument("--output", type=Path, required=True)

    assemble_parser = commands.add_parser("assemble", help="Create a checksummed release evidence directory")
    _add_repository_arguments(assemble_parser)
    assemble_parser.add_argument("--level", required=True)
    assemble_parser.add_argument("--security-dir", type=Path, required=True)
    assemble_parser.add_argument("--statement", type=Path, action="append", default=[])
    assemble_parser.add_argument("--statement-dir", type=Path, action="append", default=[])
    assemble_parser.add_argument("--output", type=Path, required=True)
    assemble_parser.add_argument("--release-tag")
    assemble_parser.add_argument("--signing-key", type=Path)
    assemble_parser.add_argument("--signing-key-id")

    audit_parser = commands.add_parser("audit", help="Report missing or invalid release evidence without assembling")
    _add_repository_arguments(audit_parser)
    audit_parser.add_argument("--level", required=True)
    audit_parser.add_argument("--security-dir", type=Path, required=True)
    audit_parser.add_argument("--statement", type=Path, action="append", default=[])
    audit_parser.add_argument("--statement-dir", type=Path, action="append", default=[])
    audit_parser.add_argument("--release-tag")
    audit_parser.add_argument("--output", type=Path)

    verify_parser = commands.add_parser("verify", help="Verify a release evidence directory offline")
    verify_parser.add_argument("bundle", type=Path)
    verify_parser.add_argument("--trusted-public-key", type=Path)
    verify_parser.add_argument("--output", type=Path)
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.action == "capture":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            command = list(args.command)
            if command and command[0] == "--":
                command = command[1:]
            statement, exit_code = capture_gate(
                repo=repo,
                policy_path=policy,
                category=args.category,
                security_directory=args.security_dir,
                output=args.output,
                command=command,
                attachments=args.attachment,
                log_attachment=args.log_attachment,
            )
            print(json.dumps(statement, ensure_ascii=False, sort_keys=True))
            return exit_code
        if args.action == "register-production":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = register_production_evidence(
                repo=repo,
                policy_path=policy,
                security_directory=args.security_dir,
                request_path=args.request,
                output=args.output,
            )
        elif args.action == "production-requirements":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = production_evidence_requirements(policy_path=policy, category=args.category)
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
        elif args.action == "prepare-production-handoff":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = prepare_production_evidence_handoff(
                repo=repo,
                policy_path=policy,
                output=args.output,
                signing_key_path=args.signing_key,
                signing_key_id=args.signing_key_id,
            )
        elif args.action == "verify-production-handoff":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = verify_production_evidence_handoff(
                repo=repo,
                policy_path=policy,
                handoff=args.handoff,
                trusted_public_key=args.trusted_public_key,
            )
        elif args.action == "verify-production-handoff-offline":
            result = verify_production_evidence_handoff_offline(
                handoff=args.handoff,
                trusted_public_key=args.trusted_public_key,
            )
        elif args.action == "register-production-batch":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = register_production_evidence_batch(
                repo=repo,
                policy_path=policy,
                security_directory=args.security_dir,
                manifest_path=args.manifest,
                output=args.output,
            )
        elif args.action == "assemble":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = assemble_bundle(
                repo=repo,
                policy_path=policy,
                level_name=args.level,
                security_directory=args.security_dir,
                statements=collect_release_statements(args.statement, args.statement_dir),
                output=args.output,
                release_tag=args.release_tag,
                signing_key_path=args.signing_key,
                signing_key_id=args.signing_key_id,
            )
        elif args.action == "audit":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = audit_release(
                repo=repo,
                policy_path=policy,
                level_name=args.level,
                security_directory=args.security_dir,
                statements=collect_release_statements(args.statement, args.statement_dir),
                release_tag=args.release_tag,
            )
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] == "eligible" else 3
        else:
            result = verify_bundle(args.bundle, args.trusted_public_key)
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ReleaseEvidenceError as exc:
        print(f"release evidence error: {exc}", file=sys.stderr)
        return 2


def run() -> None:
    raise SystemExit(main())
