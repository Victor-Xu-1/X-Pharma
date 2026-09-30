from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from pharma_intel.models import AgentClient, AgentClientSubject, ApiKey, AuditEvent, Tenant, new_uuid
from pharma_intel.security import issue_api_key


class ApiKeyLifecycleError(ValueError):
    pass


class ApiKeyLifecycleNotFound(ApiKeyLifecycleError):
    pass


MANAGED_API_KEY_SCOPES: tuple[str, ...] = (
    "mcp:connect",
    "entities:read",
    "dossiers:read",
    "targets:read",
    "activities:read",
    "pipelines:read",
    "structures:read",
    "trials:read",
    "patents:read",
    "deals:read",
    "regulatory:read",
    "epidemiology:read",
    "news:read",
    "knowledge:read",
    "evidence:read",
    "workspace:export",
)
API_KEY_MIN_TTL = timedelta(hours=1)
API_KEY_MAX_TTL = timedelta(days=366)


@dataclass(frozen=True)
class ApiKeyView:
    key: ApiKey
    commercial_client_id: str | None
    commercial_client_name: str | None


@dataclass(frozen=True)
class ApiKeyIssue:
    key: ApiKey
    secret: str


@dataclass(frozen=True)
class ApiKeyRevocation:
    key: ApiKey
    commercial_client_id: str | None


@dataclass(frozen=True)
class ApiKeyRotation:
    secret: str
    old_key_id: str
    new_key_id: str
    name: str
    prefix: str
    commercial_client_id: str | None


class ApiKeyLifecycleService:
    def __init__(
        self,
        session: Session,
        tenant: Tenant,
        *,
        actor_id: str,
        actor_type: Literal["user", "operator"] = "operator",
    ) -> None:
        normalized_actor = actor_id.strip()
        if not normalized_actor:
            raise ApiKeyLifecycleError("actor_id must not be empty")
        self.session = session
        self.tenant = tenant
        self.actor_id = normalized_actor
        self.actor_type = actor_type

    def list_keys(self, *, limit: int = 200) -> list[ApiKeyView]:
        if limit <= 0 or limit > 500:
            raise ApiKeyLifecycleError("API key list limit must be between 1 and 500")
        rows = self.session.execute(
            select(ApiKey, AgentClient)
            .outerjoin(
                AgentClient,
                and_(
                    AgentClient.tenant_id == ApiKey.tenant_id,
                    AgentClient.oauth_client_id == ApiKey.id,
                ),
            )
            .where(ApiKey.tenant_id == self.tenant.id)
            .order_by(ApiKey.active.desc(), ApiKey.created_at.desc(), ApiKey.id.desc())
            .limit(limit)
        ).all()
        return [
            ApiKeyView(
                key=row[0],
                commercial_client_id=row[1].id if row[1] is not None else None,
                commercial_client_name=row[1].display_name if row[1] is not None else None,
            )
            for row in rows
        ]

    def get(self, key_id: str) -> ApiKeyView:
        key = self.session.scalar(
            select(ApiKey).where(
                ApiKey.tenant_id == self.tenant.id,
                ApiKey.id == key_id,
            )
        )
        if key is None:
            raise ApiKeyLifecycleNotFound("API key does not exist")
        client = self.session.scalar(
            select(AgentClient).where(
                AgentClient.tenant_id == self.tenant.id,
                AgentClient.oauth_client_id == key.id,
            )
        )
        return ApiKeyView(
            key=key,
            commercial_client_id=client.id if client is not None else None,
            commercial_client_name=client.display_name if client is not None else None,
        )

    def create(
        self,
        *,
        name: str,
        scopes: list[str],
        expires_at: datetime,
        reason: str,
        request_id: str | None = None,
    ) -> ApiKeyIssue:
        now = datetime.now(UTC)
        normalized_name = _validated_name(name)
        normalized_scopes = _validated_scopes(scopes)
        normalized_expiry = _validated_expiry(expires_at, now)
        normalized_reason = _validated_reason(reason)
        secret, secret_hash = issue_api_key()
        key = ApiKey(
            tenant_id=self.tenant.id,
            name=normalized_name,
            prefix=secret[:12],
            secret_hash=secret_hash,
            scopes=normalized_scopes,
            expires_at=normalized_expiry,
        )
        self.session.add(key)
        self.session.flush()
        self._audit(
            action="security.api_key.create",
            resource_id=key.id,
            request_id=request_id,
            details={
                "name": key.name,
                "prefix": key.prefix,
                "scopes": key.scopes,
                "expires_at": key.expires_at.isoformat() if key.expires_at is not None else None,
                "reason": normalized_reason,
            },
        )
        self.session.flush()
        return ApiKeyIssue(key=key, secret=secret)

    def rotate(
        self,
        key_id: str,
        *,
        new_name: str | None = None,
        expires_at: datetime | None = None,
        reason: str = "Scheduled API key rotation",
        request_id: str | None = None,
    ) -> ApiKeyRotation:
        now = datetime.now(UTC)
        old_key = self.session.scalar(
            select(ApiKey)
            .where(
                ApiKey.tenant_id == self.tenant.id,
                ApiKey.id == key_id,
                ApiKey.active.is_(True),
                ApiKey.revoked_at.is_(None),
            )
            .with_for_update()
        )
        if old_key is None:
            raise ApiKeyLifecycleNotFound("active API key does not exist")
        if old_key.expires_at is not None and _as_utc(old_key.expires_at) <= now:
            raise ApiKeyLifecycleError("expired API key cannot be rotated")

        name = _validated_name(new_name or old_key.name)
        normalized_reason = _validated_reason(reason)
        replacement_expiry = _validated_expiry(expires_at, now) if expires_at is not None else old_key.expires_at

        client = self.session.scalar(
            select(AgentClient)
            .where(
                AgentClient.tenant_id == self.tenant.id,
                AgentClient.oauth_client_id == old_key.id,
            )
            .with_for_update()
        )
        subject: AgentClientSubject | None = None
        if client is not None:
            subjects = list(
                self.session.scalars(
                    select(AgentClientSubject)
                    .where(
                        AgentClientSubject.tenant_id == self.tenant.id,
                        AgentClientSubject.agent_client_id == client.id,
                        AgentClientSubject.actor_type == "api_key",
                        AgentClientSubject.subject_id == old_key.id,
                        AgentClientSubject.active.is_(True),
                    )
                    .with_for_update()
                ).all()
            )
            if len(subjects) != 1:
                raise ApiKeyLifecycleError("commercial API key must have exactly one active client subject binding")
            subject = subjects[0]

        secret, secret_hash = issue_api_key()
        replacement = ApiKey(
            tenant_id=self.tenant.id,
            name=name,
            prefix=secret[:12],
            secret_hash=secret_hash,
            scopes=list(old_key.scopes),
            expires_at=replacement_expiry,
        )
        self.session.add(replacement)
        self.session.flush()

        if client is not None and subject is not None:
            client.oauth_client_id = replacement.id
            subject.subject_id = replacement.id

        old_key.active = False
        old_key.revoked_at = now
        self._audit(
            action="security.api_key.rotate",
            resource_id=replacement.id,
            request_id=request_id,
            details={
                "old_key_id": old_key.id,
                "old_prefix": old_key.prefix,
                "new_prefix": replacement.prefix,
                "commercial_client_id": client.id if client is not None else None,
                "expires_at": replacement.expires_at.isoformat() if replacement.expires_at is not None else None,
                "reason": normalized_reason,
            },
        )
        self.session.flush()
        return ApiKeyRotation(
            secret=secret,
            old_key_id=old_key.id,
            new_key_id=replacement.id,
            name=replacement.name,
            prefix=replacement.prefix,
            commercial_client_id=client.id if client is not None else None,
        )

    def revoke(
        self,
        key_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> ApiKeyRevocation:
        normalized_reason = _validated_reason(reason)
        key = self.session.scalar(
            select(ApiKey)
            .where(
                ApiKey.tenant_id == self.tenant.id,
                ApiKey.id == key_id,
            )
            .with_for_update()
        )
        if key is None:
            raise ApiKeyLifecycleNotFound("API key does not exist")
        client = self.session.scalar(
            select(AgentClient)
            .where(
                AgentClient.tenant_id == self.tenant.id,
                AgentClient.oauth_client_id == key.id,
            )
            .with_for_update()
        )
        if key.revoked_at is not None or not key.active:
            return ApiKeyRevocation(key=key, commercial_client_id=client.id if client is not None else None)

        now = datetime.now(UTC)
        key.active = False
        key.revoked_at = now
        subjects: list[AgentClientSubject] = []
        if client is not None:
            subjects = list(
                self.session.scalars(
                    select(AgentClientSubject)
                    .where(
                        AgentClientSubject.tenant_id == self.tenant.id,
                        AgentClientSubject.agent_client_id == client.id,
                        AgentClientSubject.actor_type == "api_key",
                        AgentClientSubject.subject_id == key.id,
                        AgentClientSubject.active.is_(True),
                    )
                    .with_for_update()
                ).all()
            )
            for subject in subjects:
                subject.active = False
        self._audit(
            action="security.api_key.revoke",
            resource_id=key.id,
            request_id=request_id,
            details={
                "name": key.name,
                "prefix": key.prefix,
                "commercial_client_id": client.id if client is not None else None,
                "deactivated_subject_count": len(subjects),
                "reason": normalized_reason,
            },
        )
        self.session.flush()
        return ApiKeyRevocation(key=key, commercial_client_id=client.id if client is not None else None)

    def _audit(
        self,
        *,
        action: str,
        resource_id: str,
        request_id: str | None,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant.id,
                actor_type=self.actor_type,
                actor_id=self.actor_id,
                action=action,
                resource_type="api_key",
                resource_id=resource_id,
                outcome="success",
                request_id=request_id or new_uuid(),
                details=details,
            )
        )


def _validated_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 120:
        raise ApiKeyLifecycleError("API key name must contain 1 to 120 characters")
    return normalized


def _validated_scopes(values: list[str]) -> list[str]:
    normalized = sorted({value.strip() for value in values if value.strip()})
    if "mcp:connect" not in normalized:
        raise ApiKeyLifecycleError("Managed API keys must include mcp:connect")
    unknown = sorted(set(normalized) - set(MANAGED_API_KEY_SCOPES))
    if unknown:
        raise ApiKeyLifecycleError(f"API key scopes are not managed: {', '.join(unknown)}")
    if len(normalized) < 2:
        raise ApiKeyLifecycleError("Managed API keys must include at least one data-access scope")
    return normalized


def _validated_expiry(value: datetime, now: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApiKeyLifecycleError("API key expiry must include a timezone")
    normalized = value.astimezone(UTC)
    if normalized < now + API_KEY_MIN_TTL:
        raise ApiKeyLifecycleError("API key expiry must be at least one hour in the future")
    if normalized > now + API_KEY_MAX_TTL:
        raise ApiKeyLifecycleError("API key expiry must not exceed 366 days")
    return normalized


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validated_reason(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 3 or len(normalized) > 500:
        raise ApiKeyLifecycleError("API key change reason must contain 3 to 500 characters")
    return normalized
