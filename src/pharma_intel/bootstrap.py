from __future__ import annotations

import argparse
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from pharma_intel.accounts.identity import create_account
from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.ingest.readiness import AUTHORIZATION_SCOPE_PATTERN
from pharma_intel.ingest.source_roots import SourceRootPolicyError, validate_folder_source_root
from pharma_intel.licensing import EvidenceLicensePolicy, internal_evidence_license_policy
from pharma_intel.models import ApiKey, DataSource, DataSourceType, Tenant, TenantDataset, User, UserRole
from pharma_intel.security import hash_password, issue_api_key, normalize_email


def _authorization_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include a timezone")
    return parsed.astimezone(UTC)


def run() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a tenant and one scoped service key")
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--key-name", default="initial-admin")
    parser.add_argument("--skip-api-key", action="store_true")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    parser.add_argument("--admin-name", default="Administrator")
    parser.add_argument("--admin-oidc-issuer")
    parser.add_argument("--admin-oidc-subject")
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        metavar="KEY",
        help="Register an authorized logical dataset",
    )
    parser.add_argument(
        "--dataset-license",
        action="append",
        default=[],
        metavar="KEY=JSON_FILE",
        help="Bind an explicit evidence-delivery license policy to a registered dataset",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="NAME|ABSOLUTE_PATH|DATASET_KEY",
        help="Register a read-only folder for automatic ingestion",
    )
    parser.add_argument("--source-owner", help="Named accountable owner for every registered source")
    parser.add_argument(
        "--source-authorization-scope",
        action="append",
        default=[],
        help="Approved source authorization scope; repeat for multiple scopes",
    )
    parser.add_argument(
        "--source-data-classification",
        choices=["public", "internal", "confidential", "restricted"],
        default="internal",
    )
    parser.add_argument(
        "--source-authorization-valid-from",
        type=_authorization_datetime,
        help="ISO 8601 source authorization effective time; defaults to the bootstrap time",
    )
    parser.add_argument(
        "--source-authorization-valid-until",
        type=_authorization_datetime,
        help="Optional exclusive ISO 8601 source authorization end time",
    )
    parser.add_argument("--source-freshness-seconds", type=int, default=86_400)
    args = parser.parse_args()
    if args.admin_password and not args.admin_email:
        parser.error("--admin-password requires --admin-email")
    if args.admin_email and not args.admin_password and not args.admin_oidc_issuer:
        parser.error("--admin-email requires a password or an OIDC identity")
    if args.admin_password and len(args.admin_password) < 12:
        parser.error("--admin-password must contain at least 12 characters")
    if bool(args.admin_oidc_issuer) != bool(args.admin_oidc_subject):
        parser.error("--admin-oidc-issuer and --admin-oidc-subject must be supplied together")
    if args.admin_oidc_issuer and not args.admin_email:
        parser.error("OIDC identity requires an administrator account")
    if args.source and not args.source_owner:
        parser.error("--source-owner is required when registering a source")
    if args.source and not args.source_authorization_scope:
        parser.error("At least one --source-authorization-scope is required when registering a source")
    if any(not AUTHORIZATION_SCOPE_PATTERN.fullmatch(scope.strip()) for scope in args.source_authorization_scope):
        parser.error("--source-authorization-scope contains an invalid value")
    authorization_valid_from = args.source_authorization_valid_from or datetime.now(UTC)
    if (
        args.source_authorization_valid_until is not None
        and args.source_authorization_valid_until <= authorization_valid_from
    ):
        parser.error("--source-authorization-valid-until must be later than the effective time")
    if not 60 <= args.source_freshness_seconds <= 31_536_000:
        parser.error("--source-freshness-seconds must be between 60 and 31536000")
    dataset_license_policies: dict[str, dict[str, object]] = {}
    for value in args.dataset_license:
        key, separator, policy_file = value.partition("=")
        normalized_key = key.strip()
        if not normalized_key or not separator or not policy_file.strip():
            parser.error(f"Invalid --dataset-license value: {value}")
        if normalized_key in dataset_license_policies:
            parser.error(f"Duplicate dataset license policy: {normalized_key}")
        try:
            policy = EvidenceLicensePolicy.model_validate_json(Path(policy_file.strip()).read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            parser.error(f"Invalid dataset license policy for {normalized_key}: {exc}")
        dataset_license_policies[normalized_key] = policy.document()

    secret: str | None = None
    api_key_id: str | None = None
    with get_session_factory()() as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
        if tenant is None:
            tenant = Tenant(slug=args.tenant_slug, name=args.tenant_name)
            session.add(tenant)
            session.flush()
        set_tenant_context(session, tenant.id)
        if not args.skip_api_key:
            secret, secret_hash = issue_api_key()
            api_key = ApiKey(
                tenant_id=tenant.id,
                name=args.key_name,
                prefix=secret[:12],
                secret_hash=secret_hash,
                scopes=["*"],
            )
            session.add(api_key)
            session.flush()
            api_key_id = api_key.id
        if args.admin_email:
            normalized_email = normalize_email(args.admin_email)
            existing_user = session.scalar(select(User).where(User.normalized_email == normalized_email))
            if existing_user is not None:
                parser.error("An account with this email already exists")
            session.add(
                create_account(
                    tenant_id=tenant.id,
                    email=args.admin_email.strip(),
                    normalized_email=normalized_email,
                    display_name=args.admin_name.strip(),
                    password_hash=hash_password(args.admin_password or secrets.token_urlsafe(48)),
                    role=UserRole.ADMIN,
                    oidc_issuer=args.admin_oidc_issuer,
                    oidc_subject=args.admin_oidc_subject,
                )
            )
        dataset_values = list(args.dataset)
        processed_dataset_keys: set[str] = set()
        for value in dataset_values:
            if not value.strip() or "=" in value:
                parser.error(f"Invalid --dataset value: {value}")
            normalized_key = value.strip()
            processed_dataset_keys.add(normalized_key)
            license_policy = dataset_license_policies.get(
                normalized_key, internal_evidence_license_policy(source="bootstrap")
            )
            existing_dataset = session.scalar(
                select(TenantDataset).where(
                    TenantDataset.tenant_id == tenant.id,
                    TenantDataset.dataset_key == normalized_key,
                )
            )
            if existing_dataset is None:
                session.add(
                    TenantDataset(
                        tenant_id=tenant.id,
                        dataset_key=normalized_key,
                        display_name=normalized_key.replace("_", " ").title(),
                        required_scopes=["evidence:read"],
                        license_policy=license_policy,
                    )
                )
            if existing_dataset is not None and normalized_key in dataset_license_policies:
                existing_dataset.license_policy = license_policy
        unbound_license_keys = sorted(set(dataset_license_policies) - processed_dataset_keys)
        if unbound_license_keys:
            parser.error(f"Dataset license policies have no matching --dataset: {', '.join(unbound_license_keys)}")

        session.flush()
        for value in args.source:
            parts = value.split("|", 2)
            if len(parts) != 3 or not all(part.strip() for part in parts):
                parser.error(f"Invalid --source value: {value}")
            name, root_value, dataset_key = (part.strip() for part in parts)
            try:
                root = validate_folder_source_root(
                    Path(root_value),
                    get_settings().source_roots,
                    require_existing=False,
                )
            except SourceRootPolicyError as exc:
                parser.error(str(exc))
            target_dataset = session.scalar(
                select(TenantDataset).where(
                    TenantDataset.tenant_id == tenant.id,
                    TenantDataset.dataset_key == dataset_key,
                    TenantDataset.active.is_(True),
                )
            )
            if target_dataset is None:
                parser.error(f"Source dataset is not registered and active: {dataset_key}")
            try:
                validated_license = EvidenceLicensePolicy.model_validate(target_dataset.license_policy)
            except ValidationError:
                parser.error(f"Source dataset has an invalid license policy: {dataset_key}")
            license_checked_at = datetime.now(UTC)
            if not validated_license.permits("web", license_checked_at) and not validated_license.permits(
                "mcp", license_checked_at
            ):
                parser.error(f"Source dataset license is not currently deliverable: {dataset_key}")
            existing_source = session.scalar(
                select(DataSource).where(
                    DataSource.tenant_id == tenant.id,
                    DataSource.root_uri == str(root),
                )
            )
            if existing_source is None:
                session.add(
                    DataSource(
                        tenant_id=tenant.id,
                        name=name,
                        source_type=DataSourceType.FOLDER,
                        root_uri=str(root),
                        owner=args.source_owner.strip(),
                        data_classification=args.source_data_classification,
                        authorization_scopes=sorted({scope.strip() for scope in args.source_authorization_scope}),
                        authorization_valid_from=authorization_valid_from,
                        authorization_valid_until=args.source_authorization_valid_until,
                        dataset_key=dataset_key,
                        include_globs=["*", "**/*"],
                        expected_freshness_seconds=args.source_freshness_seconds,
                    )
                )
        session.commit()
    if secret:
        print("API key created. It is shown once; store it in a secret manager:")
        print(secret)
        print(f"API key identity for commercial client binding: {api_key_id}")
    if args.admin_email:
        print(f"Human administrator created: {args.admin_email.strip()}")
