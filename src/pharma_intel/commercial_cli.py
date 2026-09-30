from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from pharma_intel.commercial.accounting import (
    BillingStatementCommand,
    CommercialAccountingConflict,
    CommercialAccountingService,
    CommercialBalanceViolation,
    ReversalCommand,
    UsageAdjustmentCommand,
)
from pharma_intel.commercial.admin import (
    CommercialAdminConflict,
    CommercialAdminService,
    ProvisionClientCommand,
    RateCardMigrationCommand,
)
from pharma_intel.commercial.billing import (
    BillingProviderReceipt,
    BillingStatementSigner,
    canonical_manifest_bytes,
)
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import Tenant


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the authoritative commercial MCP configuration")
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--actor", required=True, help="Named operator or change-ticket identity")
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish-rate-card")
    publish.add_argument("--file", required=True, type=Path)

    migrate = subparsers.add_parser("migrate-rate-card")
    migrate.add_argument("--subscription-key", required=True)
    migrate.add_argument("--rate-card-key", required=True)
    migrate.add_argument("--rate-card-revision", required=True, type=int)
    migrate.add_argument("--reason", required=True)

    provision = subparsers.add_parser("provision-client")
    provision.add_argument("--client-key", required=True)
    provision.add_argument("--oauth-client-id", required=True)
    provision.add_argument("--display-name", required=True)
    provision.add_argument("--actor-type", required=True, choices=("agent", "api_key"))
    provision.add_argument("--subject-id", required=True)
    provision.add_argument("--account-key", required=True)
    provision.add_argument("--account-name", required=True)
    provision.add_argument("--subscription-key", required=True)
    provision.add_argument("--rate-card-key", required=True)
    provision.add_argument("--rate-card-revision", required=True, type=int)
    provision.add_argument("--export-field-policy", required=True, type=Path)
    provision.add_argument("--max-page-depth", type=int, default=10)
    provision.add_argument("--daily-unique-record-limit", type=int, default=5000)
    provision.add_argument("--max-response-bytes", type=int, default=2_000_000)

    export_policy = subparsers.add_parser("set-export-field-policy")
    export_policy.add_argument("--account-key", required=True)
    export_policy.add_argument("--file", required=True, type=Path)

    grant = subparsers.add_parser("grant-credit")
    grant.add_argument("--subscription-key", required=True)
    grant.add_argument("--units", required=True)
    grant.add_argument("--external-reference", required=True)
    grant.add_argument("--reason", required=True)

    adjustment = subparsers.add_parser("adjust-usage")
    adjustment.add_argument("--subscription-key", required=True)
    adjustment.add_argument("--adjustment-key", required=True)
    adjustment.add_argument("--units-delta", required=True)
    adjustment.add_argument("--reason", required=True)

    reverse_settlement = subparsers.add_parser("reverse-settlement")
    reverse_settlement.add_argument("--settlement-id", required=True)
    reverse_settlement.add_argument("--adjustment-key", required=True)
    reverse_settlement.add_argument("--reason", required=True)

    reverse_adjustment = subparsers.add_parser("reverse-adjustment")
    reverse_adjustment.add_argument("--adjustment-id", required=True)
    reverse_adjustment.add_argument("--adjustment-key", required=True)
    reverse_adjustment.add_argument("--reason", required=True)

    expire = subparsers.add_parser("expire-reservations")
    expire.add_argument("--limit", type=int, default=1000)

    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--subscription-key", required=True)
    reconcile.add_argument("--run-key", required=True)

    statement = subparsers.add_parser("generate-statement")
    statement.add_argument("--subscription-key", required=True)
    statement.add_argument("--statement-key", required=True)
    statement.add_argument("--period-start", required=True, type=_datetime)
    statement.add_argument("--period-end", required=True, type=_datetime)
    statement.add_argument("--revision", type=int, default=1)
    statement.add_argument("--output", required=True, type=Path)

    invoice = subparsers.add_parser("record-invoice")
    invoice.add_argument("--statement-id", required=True)
    invoice.add_argument("--provider", required=True)
    invoice.add_argument("--external-invoice-id", required=True)
    invoice.add_argument("--status", required=True)
    invoice.add_argument("--amount-due", required=True)
    invoice.add_argument("--currency", required=True)
    invoice.add_argument("--metadata-json", default="{}")
    return parser


def run() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        with get_session_factory()() as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
            if tenant is None:
                parser.error("Tenant does not exist")
            set_tenant_context(session, tenant.id)
            admin_service = CommercialAdminService(session, tenant, actor_id=args.actor)
            settings = get_settings()
            accounting_service = CommercialAccountingService(
                session,
                tenant,
                actor_id=args.actor,
                statement_signer=BillingStatementSigner(
                    settings.effective_billing_statement_signing_secret,
                    key_id=settings.billing_statement_signing_key_id,
                ),
            )
            request_id = str(uuid.uuid4())
            if args.command == "publish-rate-card":
                definition = RateCardDefinition.model_validate_json(args.file.read_text(encoding="utf-8"))
                rate_card = admin_service.publish_rate_card(definition)
                print(
                    f"Published immutable rate card {rate_card.rate_card_key} "
                    f"revision {rate_card.revision}: {rate_card.id}"
                )
            elif args.command == "migrate-rate-card":
                subscription = admin_service.migrate_rate_card(
                    RateCardMigrationCommand(
                        subscription_key=args.subscription_key,
                        rate_card_key=args.rate_card_key,
                        rate_card_revision=args.rate_card_revision,
                        reason=args.reason,
                    )
                )
                print(
                    f"Migrated commercial subscription {subscription.subscription_key} "
                    f"to rate-card version {subscription.rate_card_version_id}"
                )
            elif args.command == "provision-client":
                subscription = admin_service.provision_client(
                    ProvisionClientCommand(
                        client_key=args.client_key,
                        oauth_client_id=args.oauth_client_id,
                        display_name=args.display_name,
                        actor_type=args.actor_type,
                        subject_id=args.subject_id,
                        account_key=args.account_key,
                        account_name=args.account_name,
                        subscription_key=args.subscription_key,
                        rate_card_key=args.rate_card_key,
                        rate_card_revision=args.rate_card_revision,
                        created_by=args.actor,
                        export_field_policy=json.loads(args.export_field_policy.read_text(encoding="utf-8")),
                        max_page_depth=args.max_page_depth,
                        daily_unique_record_limit=args.daily_unique_record_limit,
                        max_response_bytes=args.max_response_bytes,
                    )
                )
                print(f"Provisioned commercial subscription: {subscription.id}")
            elif args.command == "set-export-field-policy":
                policy = admin_service.set_export_field_policy(
                    args.account_key,
                    json.loads(args.file.read_text(encoding="utf-8")),
                )
                print(f"Updated export field policy {policy.policy_version}: {policy.id}")
            elif args.command == "grant-credit":
                grant = admin_service.grant_credit(
                    args.subscription_key,
                    _decimal(args.units, "--units"),
                    external_reference=args.external_reference,
                    reason=args.reason,
                )
                print(f"Granted {grant.granted_units} units: {grant.id}")
            elif args.command == "adjust-usage":
                adjustment = accounting_service.adjust_usage(
                    UsageAdjustmentCommand(
                        subscription_key=args.subscription_key,
                        adjustment_key=args.adjustment_key,
                        units_delta=_decimal(args.units_delta, "--units-delta"),
                        reason=args.reason,
                        request_id=request_id,
                    )
                )
                print(f"Recorded {adjustment.adjustment_kind} {adjustment.units_delta}: {adjustment.id}")
            elif args.command == "reverse-settlement":
                adjustment = accounting_service.reverse_settlement(
                    args.settlement_id,
                    ReversalCommand(args.adjustment_key, args.reason, request_id),
                )
                print(f"Reversed settlement with {adjustment.units_delta} units: {adjustment.id}")
            elif args.command == "reverse-adjustment":
                adjustment = accounting_service.reverse_adjustment(
                    args.adjustment_id,
                    ReversalCommand(args.adjustment_key, args.reason, request_id),
                )
                print(f"Reversed adjustment with {adjustment.units_delta} units: {adjustment.id}")
            elif args.command == "expire-reservations":
                outcome = accounting_service.expire_stale_reservations(
                    request_id=request_id,
                    limit=args.limit,
                )
                print(f"Expired {outcome.expired_reservations} reservations; released {outcome.released_units} units")
            elif args.command == "reconcile":
                run = accounting_service.reconcile(
                    args.subscription_key,
                    run_key=args.run_key,
                    request_id=request_id,
                )
                print(f"Reconciliation {run.status}; issues={run.issue_count}: {run.id}")
                if run.status != "clean":
                    raise CommercialBalanceViolation(json.dumps(run.issues_json, ensure_ascii=True))
            elif args.command == "generate-statement":
                statement = accounting_service.create_statement(
                    BillingStatementCommand(
                        subscription_key=args.subscription_key,
                        statement_key=args.statement_key,
                        period_start=args.period_start,
                        period_end=args.period_end,
                        revision=args.revision,
                        request_id=request_id,
                    )
                )
                envelope = accounting_service.statement_manifest(statement).envelope()
                _atomic_export(args.output, canonical_manifest_bytes(envelope) + b"\n")
                print(f"Generated signed billing statement {statement.id}: {args.output.resolve()}")
            else:
                metadata = json.loads(args.metadata_json)
                if not isinstance(metadata, dict):
                    parser.error("--metadata-json must contain a JSON object")
                reference = accounting_service.record_invoice(
                    args.statement_id,
                    BillingProviderReceipt(
                        provider=args.provider,
                        external_invoice_id=args.external_invoice_id,
                        status=args.status,
                        amount_due=_decimal(args.amount_due, "--amount-due"),
                        currency=args.currency,
                        metadata=metadata,
                    ),
                    request_id=request_id,
                )
                print(f"Recorded invoice reference {reference.external_invoice_id}: {reference.id}")
    except (
        CommercialAccountingConflict,
        CommercialAdminConflict,
        CommercialBalanceViolation,
        json.JSONDecodeError,
        OSError,
        ValidationError,
        ValueError,
    ) as exc:
        parser.error(str(exc))


def _decimal(value: str, option: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{option} must be a decimal number") from exc


def _datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _atomic_export(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == body:
            return
        raise ValueError(f"Refusing to replace a different billing export: {path}")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(body)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
