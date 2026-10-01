from __future__ import annotations

import base64
import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.enterprise.llm_providers import (
    CreateLLMProviderCommand,
    LLMCredentialCipher,
    LLMProviderCatalogService,
    LLMProviderConflict,
    LLMProviderError,
    UpdateLLMProviderCommand,
    effective_ai_settings,
)
from pharma_intel.governance.model_gateway import ModelGatewayError, OpenAICompatibleExtractionGateway
from pharma_intel.models import AuditEvent, LLMProviderConfig, Tenant, UserRole
from pharma_intel.security import Principal, hash_password, require_principal

ENCRYPTION_KEY = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")


def _settings() -> Settings:
    return Settings(
        llm_credentials_encryption_key=ENCRYPTION_KEY,
        ai_base_url="https://environment-fallback.test/v1",
        ai_api_key="environment-secret",
        ai_model="environment-model",
        ai_allowed_response_models_json='["cp_glm_5d2_w4a8_p800"]',
    )


def _command(name: str, base_url: str, api_key: str, model: str) -> CreateLLMProviderCommand:
    return CreateLLMProviderCommand(
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=model,
        response_format_mode="prompt_only",
        thinking_mode="disabled",
        include_schema_in_prompt=True,
        max_output_tokens_per_segment=16_384,
        request_timeout_seconds=120,
        request_attempts=2,
        reason="Approved provider onboarding",
    )


def _service(session: Session, tenant_id: str) -> LLMProviderCatalogService:
    return LLMProviderCatalogService(
        session,
        tenant_id=tenant_id,
        actor_id="admin-user",
        request_id="llm-provider-test",
        settings=_settings(),
    )


def test_catalog_encrypts_credentials_and_drives_primary_fallback_order(session: Session, tenant: Tenant) -> None:
    service = _service(session, tenant.id)
    mimo = service.create(_command("mimo", "https://token-plan-cn.xiaomimimo.com/v1", "mimo-secret-key", "mimo-v2.5"))
    glm = service.create(_command("glm", "https://chatapi.weixin.qq.com/openai/v1", "glm-secret-key", "GLM-5.2"))

    assert [item.name for item in service.list()] == ["mimo", "glm"]
    assert "mimo-secret-key" not in mimo.api_key_ciphertext
    assert "glm-secret-key" not in glm.api_key_ciphertext
    assert LLMCredentialCipher(ENCRYPTION_KEY).decrypt(tenant.id, mimo.id, mimo.api_key_ciphertext) == "mimo-secret-key"

    effective = effective_ai_settings(session, _settings(), tenant.id)
    assert effective.ai_model == "mimo-v2.5"
    assert effective.ai_api_key == "mimo-secret-key"
    assert effective.ai_allowed_response_models == frozenset({"mimo-v2.5", "GLM-5.2", "cp_glm_5d2_w4a8_p800"})
    assert [(item.name, item.model) for item in effective.ai_fallback_providers] == [("glm", "GLM-5.2")]

    reordered = service.make_primary(glm.id, glm.version, "GLM promoted for controlled validation")
    assert [item.name for item in reordered] == ["glm", "mimo"]
    assert effective_ai_settings(session, _settings(), tenant.id).ai_model == "GLM-5.2"
    assert {event.action for event in session.query(AuditEvent).all()} >= {
        "enterprise.llm_provider.created",
        "enterprise.llm_provider.primary_changed",
    }


def test_catalog_rejects_stale_updates_and_disabling_the_last_provider(session: Session, tenant: Tenant) -> None:
    service = _service(session, tenant.id)
    provider = service.create(
        _command("mimo", "https://token-plan-cn.xiaomimimo.com/v1", "mimo-secret-key", "mimo-v2.5")
    )
    update = UpdateLLMProviderCommand(
        expected_version=provider.version,
        name=provider.name,
        base_url=provider.base_url,
        api_key=None,
        model=provider.model,
        active=False,
        response_format_mode="prompt_only",
        thinking_mode="disabled",
        include_schema_in_prompt=True,
        max_output_tokens_per_segment=16_384,
        request_timeout_seconds=120,
        request_attempts=2,
        reason="Attempt to disable final provider",
    )
    with pytest.raises(LLMProviderConflict, match="At least one active"):
        service.update(provider.id, update)
    with pytest.raises(LLMProviderConflict, match="refresh"):
        service.update(
            provider.id, UpdateLLMProviderCommand(**{**update.__dict__, "expected_version": 99, "active": True})
        )


def test_catalog_rejects_wrong_master_key_and_redacts_test_failures(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(session, tenant.id)
    secret = f"provider-{tenant.id}-credential"
    provider = service.create(_command("mimo", "https://token-plan-cn.xiaomimimo.com/v1", secret, "mimo-v2.5"))

    wrong_key = base64.urlsafe_b64encode(b"w" * 32).decode("ascii")
    with pytest.raises(LLMProviderError, match="cannot be decrypted"):
        LLMCredentialCipher(wrong_key).decrypt(tenant.id, provider.id, provider.api_key_ciphertext)

    def fail_with_secret(*_args: object, **_kwargs: object) -> None:
        raise ModelGatewayError(f"provider rejected Authorization: Bearer {secret}")

    monkeypatch.setattr(OpenAICompatibleExtractionGateway, "extract", fail_with_secret)
    tested = service.test(provider.id)
    assert tested.last_test_status == "failed"
    assert tested.last_test_message is not None
    assert secret not in tested.last_test_message
    assert "[REDACTED]" in tested.last_test_message


def test_enterprise_llm_provider_api_never_returns_credentials(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = create_account(
        tenant_id=tenant.id,
        email="llm-admin@example.test",
        normalized_email="llm-admin@example.test",
        display_name="LLM Admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        role=UserRole.ADMIN,
        active=True,
    )
    session.add(actor)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        actor.id,
        "user",
        frozenset({"*"}),
    )
    monkeypatch.setattr("pharma_intel.http.runtime.get_settings", _settings)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/enterprise/llm-providers",
                json={
                    "name": "mimo",
                    "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
                    "api_key": "mimo-api-secret",
                    "model": "mimo-v2.5",
                    "response_format_mode": "prompt_only",
                    "thinking_mode": "disabled",
                    "include_schema_in_prompt": True,
                    "max_output_tokens_per_segment": 16384,
                    "request_timeout_seconds": 120,
                    "request_attempts": 2,
                    "reason": "Approved provider onboarding",
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["priority"] == 0
            assert body["api_key_configured"] is True
            assert "mimo-api-secret" not in created.text
            assert "ciphertext" not in created.text

            listed = client.get("/api/v1/enterprise/llm-providers")
            assert listed.status_code == 200
            assert listed.json()[0]["model"] == "mimo-v2.5"
            assert "mimo-api-secret" not in listed.text
            persisted = session.get(LLMProviderConfig, body["id"])
            assert persisted is not None
            assert "mimo-api-secret" not in persisted.api_key_ciphertext
            assert "mimo-api-secret" not in json.dumps([event.details for event in session.query(AuditEvent).all()])
    finally:
        app.dependency_overrides.clear()


def test_enterprise_llm_provider_catalog_requires_enterprise_admin(
    session: Session,
    tenant: Tenant,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "viewer-user",
        "user",
        frozenset({"entities:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/enterprise/llm-providers")

        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient scope"}
        assert "api_key" not in response.text
        assert "ciphertext" not in response.text
    finally:
        app.dependency_overrides.clear()
