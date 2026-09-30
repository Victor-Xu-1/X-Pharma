from __future__ import annotations

import base64
import builtins
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.model_gateway import ModelGatewayError, OpenAICompatibleExtractionGateway
from pharma_intel.models import AuditEvent, LLMProviderConfig, Tenant, new_uuid


class LLMProviderError(RuntimeError):
    pass


class LLMProviderNotFound(LLMProviderError):
    pass


class LLMProviderConflict(LLMProviderError):
    pass


@dataclass(frozen=True)
class CreateLLMProviderCommand:
    name: str
    base_url: str
    api_key: str
    model: str
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"]
    thinking_mode: Literal["provider_default", "enabled", "disabled"]
    include_schema_in_prompt: bool
    max_output_tokens_per_segment: int
    request_timeout_seconds: float
    request_attempts: int
    reason: str


@dataclass(frozen=True)
class UpdateLLMProviderCommand:
    expected_version: int
    name: str
    base_url: str
    api_key: str | None
    model: str
    active: bool
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"]
    thinking_mode: Literal["provider_default", "enabled", "disabled"]
    include_schema_in_prompt: bool
    max_output_tokens_per_segment: int
    request_timeout_seconds: float
    request_attempts: int
    reason: str


class LLMCredentialCipher:
    def __init__(self, encoded_key: str) -> None:
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise LLMProviderError("LLM credential encryption key is invalid") from exc
        if len(key) != 32 or base64.urlsafe_b64encode(key).decode("ascii") != encoded_key:
            raise LLMProviderError("LLM credential encryption key must be canonical URL-safe Base64 for 32 bytes")
        self._cipher = AESGCM(key)

    def encrypt(self, tenant_id: str, provider_id: str, api_key: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, api_key.encode("utf-8"), self._aad(tenant_id, provider_id))
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, tenant_id: str, provider_id: str, ciphertext: str) -> str:
        try:
            payload = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            plaintext = self._cipher.decrypt(payload[:12], payload[12:], self._aad(tenant_id, provider_id))
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError, ValueError) as exc:
            raise LLMProviderError("LLM provider credential cannot be decrypted") from exc

    @staticmethod
    def _aad(tenant_id: str, provider_id: str) -> bytes:
        return f"pharma-llm-provider:v1:{tenant_id}:{provider_id}".encode()


class LLMProviderCatalogService:
    def __init__(
        self,
        session: Session,
        *,
        tenant_id: str,
        actor_id: str,
        request_id: str,
        settings: Settings,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._actor_id = actor_id
        self._request_id = request_id
        self._settings = settings

    def list(self) -> list[LLMProviderConfig]:
        return list(
            self._session.scalars(
                select(LLMProviderConfig)
                .where(LLMProviderConfig.tenant_id == self._tenant_id)
                .order_by(LLMProviderConfig.priority, LLMProviderConfig.id)
            )
        )

    def create(self, command: CreateLLMProviderCommand) -> LLMProviderConfig:
        self._lock_tenant()
        if self._session.scalar(
            select(LLMProviderConfig.id).where(
                LLMProviderConfig.tenant_id == self._tenant_id,
                func.lower(LLMProviderConfig.name) == command.name.casefold(),
            )
        ):
            raise LLMProviderConflict("An LLM provider with this name already exists")
        provider_id = new_uuid()
        priority = (
            int(
                self._session.scalar(
                    select(func.coalesce(func.max(LLMProviderConfig.priority), -1)).where(
                        LLMProviderConfig.tenant_id == self._tenant_id
                    )
                )
                or 0
            )
            + 1
        )
        provider = LLMProviderConfig(
            id=provider_id,
            tenant_id=self._tenant_id,
            priority=priority,
            active=True,
            api_key_ciphertext=self._credential_cipher().encrypt(self._tenant_id, provider_id, command.api_key),
            api_key_fingerprint=_api_key_fingerprint(command.api_key),
        )
        self._apply(provider, command)
        self._validate_provider(provider, command.api_key)
        self._session.add(provider)
        self._record(
            "enterprise.llm_provider.created",
            provider,
            command.reason,
            {"credential_changed": True},
        )
        self._session.commit()
        self._session.refresh(provider)
        return provider

    def update(self, provider_id: str, command: UpdateLLMProviderCommand) -> LLMProviderConfig:
        provider = self._locked(provider_id)
        if provider.version != command.expected_version:
            raise LLMProviderConflict("LLM provider changed; refresh before saving")
        if self._session.scalar(
            select(LLMProviderConfig.id).where(
                LLMProviderConfig.tenant_id == self._tenant_id,
                func.lower(LLMProviderConfig.name) == command.name.casefold(),
                LLMProviderConfig.id != provider.id,
            )
        ):
            raise LLMProviderConflict("An LLM provider with this name already exists")
        if provider.active and not command.active and self._active_count() <= 1:
            raise LLMProviderConflict("At least one active LLM provider must remain")
        if provider.priority == 0 and provider.active and not command.active:
            raise LLMProviderConflict("Promote another LLM provider before disabling the primary")
        api_key = command.api_key or self._credential_cipher().decrypt(
            self._tenant_id,
            provider.id,
            provider.api_key_ciphertext,
        )
        self._apply(provider, command)
        if command.api_key is not None:
            provider.api_key_ciphertext = self._credential_cipher().encrypt(
                self._tenant_id,
                provider.id,
                command.api_key,
            )
            provider.api_key_fingerprint = _api_key_fingerprint(command.api_key)
        provider.version += 1
        self._validate_provider(provider, api_key)
        self._record(
            "enterprise.llm_provider.updated",
            provider,
            command.reason,
            {"credential_changed": command.api_key is not None, "active": command.active},
        )
        self._session.commit()
        self._session.refresh(provider)
        return provider

    def make_primary(self, provider_id: str, expected_version: int, reason: str) -> builtins.list[LLMProviderConfig]:
        self._lock_tenant()
        providers = self.list()
        selected = next((item for item in providers if item.id == provider_id), None)
        if selected is None:
            raise LLMProviderNotFound("LLM provider not found")
        if selected.version != expected_version:
            raise LLMProviderConflict("LLM provider changed; refresh before switching")
        if not selected.active:
            raise LLMProviderConflict("Disabled LLM provider cannot become primary")
        ordered = [selected, *(item for item in providers if item.id != selected.id)]
        for item in ordered:
            item.priority += 1000
        self._session.flush()
        for priority, item in enumerate(ordered):
            item.priority = priority
            item.version += 1
        self._record("enterprise.llm_provider.primary_changed", selected, reason, {})
        self._session.commit()
        return self.list()

    def test(self, provider_id: str) -> LLMProviderConfig:
        provider = self._locked(provider_id)
        api_key = self._credential_cipher().decrypt(self._tenant_id, provider.id, provider.api_key_ciphertext)
        settings = _provider_settings(self._settings, provider, api_key)
        try:
            response = OpenAICompatibleExtractionGateway(settings).extract(
                "A public report states that EGFR is a molecular target.",
                fact_kind_allowlist=frozenset({"claim"}),
                max_facts=1,
            )
        except ModelGatewayError as exc:
            provider.last_test_status = "failed"
            provider.last_test_message = _safe_test_message(str(exc), secrets=(api_key,))
        else:
            provider.last_test_status = "passed"
            provider.last_test_message = (
                f"{response.model_name or provider.model} · {response.finish_reason or 'completed'} · "
                f"request_id={'yes' if response.provider_request_id else 'no'}"
            )
        provider.last_tested_at = datetime.now(UTC)
        provider.version += 1
        self._record(
            "enterprise.llm_provider.tested",
            provider,
            "Administrator requested a provider connectivity test",
            {"status": provider.last_test_status},
        )
        self._session.commit()
        self._session.refresh(provider)
        return provider

    def _locked(self, provider_id: str) -> LLMProviderConfig:
        provider = self._session.scalar(
            select(LLMProviderConfig)
            .where(
                LLMProviderConfig.tenant_id == self._tenant_id,
                LLMProviderConfig.id == provider_id,
            )
            .with_for_update()
        )
        if provider is None:
            raise LLMProviderNotFound("LLM provider not found")
        return provider

    def _lock_tenant(self) -> None:
        if self._session.scalar(select(Tenant.id).where(Tenant.id == self._tenant_id).with_for_update()) is None:
            raise LLMProviderNotFound("Tenant not found")

    def _active_count(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(LLMProviderConfig)
                .where(
                    LLMProviderConfig.tenant_id == self._tenant_id,
                    LLMProviderConfig.active.is_(True),
                )
            )
            or 0
        )

    def _credential_cipher(self) -> LLMCredentialCipher:
        return LLMCredentialCipher(self._settings.llm_credentials_encryption_key)

    @staticmethod
    def _apply(provider: LLMProviderConfig, command: CreateLLMProviderCommand | UpdateLLMProviderCommand) -> None:
        provider.name = command.name
        provider.base_url = command.base_url.rstrip("/")
        provider.model = command.model
        provider.response_format_mode = command.response_format_mode
        provider.thinking_mode = command.thinking_mode
        provider.include_schema_in_prompt = command.include_schema_in_prompt
        provider.max_output_tokens_per_segment = command.max_output_tokens_per_segment
        provider.request_timeout_seconds = command.request_timeout_seconds
        provider.request_attempts = command.request_attempts
        if isinstance(command, UpdateLLMProviderCommand):
            provider.active = command.active

    def _validate_provider(self, provider: LLMProviderConfig, api_key: str) -> None:
        try:
            OpenAICompatibleExtractionGateway(_provider_settings(self._settings, provider, api_key))
        except ModelGatewayError as exc:
            raise LLMProviderConflict(str(exc)) from exc

    def _record(
        self,
        action: str,
        provider: LLMProviderConfig,
        reason: str,
        details: dict[str, object],
    ) -> None:
        self._session.add(
            AuditEvent(
                tenant_id=self._tenant_id,
                actor_type="user",
                actor_id=self._actor_id,
                action=action,
                resource_type="llm_provider",
                resource_id=provider.id,
                outcome="success",
                request_id=self._request_id,
                details={
                    "name": provider.name,
                    "model": provider.model,
                    "base_url": provider.base_url,
                    "reason": reason,
                    **details,
                },
            )
        )


def effective_ai_settings(session: Session, settings: Settings, tenant_id: str) -> Settings:
    providers = list(
        session.scalars(
            select(LLMProviderConfig)
            .where(
                LLMProviderConfig.tenant_id == tenant_id,
                LLMProviderConfig.active.is_(True),
            )
            .order_by(LLMProviderConfig.priority, LLMProviderConfig.id)
        )
    )
    if not providers:
        return settings
    cipher = LLMCredentialCipher(settings.llm_credentials_encryption_key)
    primary, *fallbacks = providers
    primary_key = cipher.decrypt(tenant_id, primary.id, primary.api_key_ciphertext)
    fallback_payload = [
        {
            "name": provider.name,
            "base_url": provider.base_url,
            "api_key": cipher.decrypt(tenant_id, provider.id, provider.api_key_ciphertext),
            "model": provider.model,
            "response_format_mode": provider.response_format_mode,
            "thinking_mode": provider.thinking_mode,
            "include_schema_in_prompt": provider.include_schema_in_prompt,
            "max_output_tokens_per_segment": provider.max_output_tokens_per_segment,
            "request_timeout_seconds": provider.request_timeout_seconds,
            "request_attempts": provider.request_attempts,
        }
        for provider in fallbacks
    ]
    allowed_response_models = sorted(settings.ai_allowed_response_models | {provider.model for provider in providers})
    return settings.model_copy(
        update={
            "ai_governance_enabled": True,
            "ai_base_url": primary.base_url,
            "ai_api_key": primary_key,
            "ai_model": primary.model,
            "ai_response_format_mode": primary.response_format_mode,
            "ai_thinking_mode": primary.thinking_mode,
            "ai_include_schema_in_prompt": primary.include_schema_in_prompt,
            "ai_max_output_tokens_per_segment": primary.max_output_tokens_per_segment,
            "ai_request_timeout_seconds": primary.request_timeout_seconds,
            "ai_request_attempts": primary.request_attempts,
            "ai_fallback_providers_json": json.dumps(fallback_payload, separators=(",", ":")),
            "ai_allowed_response_models_json": json.dumps(allowed_response_models),
        }
    )


def _provider_settings(settings: Settings, provider: LLMProviderConfig, api_key: str) -> Settings:
    allowed_response_models = sorted(settings.ai_allowed_response_models | {provider.model})
    return settings.model_copy(
        update={
            "ai_governance_enabled": True,
            "ai_base_url": provider.base_url,
            "ai_api_key": api_key,
            "ai_model": provider.model,
            "ai_response_format_mode": provider.response_format_mode,
            "ai_thinking_mode": provider.thinking_mode,
            "ai_include_schema_in_prompt": provider.include_schema_in_prompt,
            "ai_max_output_tokens_per_segment": provider.max_output_tokens_per_segment,
            "ai_request_timeout_seconds": provider.request_timeout_seconds,
            "ai_request_attempts": provider.request_attempts,
            "ai_fallback_providers_json": "[]",
            "ai_allowed_response_models_json": json.dumps(allowed_response_models),
        }
    )


def _api_key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _safe_test_message(message: str, *, secrets: tuple[str, ...] = ()) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    normalized = " ".join(message.split())
    return normalized[:500]
