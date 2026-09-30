from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pharma_intel.config import Settings


def test_semantic_similarity_floor_cannot_be_disabled() -> None:
    with pytest.raises(ValidationError, match="search_semantic_min_score"):
        Settings(_env_file=None, search_semantic_min_score=0)


def test_ai_governance_accepts_third_party_https_api() -> None:
    settings = Settings(
        _env_file=None,
        ai_governance_enabled=True,
        ai_base_url="https://api.vendor.example/v1",
        ai_api_key="provider-secret",
        ai_model="approved-model",
    )

    settings.validate_remote_ai_api()


@pytest.mark.parametrize(
    "base_url",
    (
        "http://api.vendor.example/v1",
        "https://localhost/v1",
        "https://model.localhost/v1",
        "https://127.0.0.1/v1",
        "https://[::1]/v1",
        "https://user:password@api.vendor.example/v1",
        "https://api.vendor.example/v1?tenant=one",
        "https://api.vendor.example/v1#fragment",
    ),
)
def test_ai_governance_rejects_non_remote_or_ambiguous_api_roots(base_url: str) -> None:
    settings = Settings(
        _env_file=None,
        ai_governance_enabled=True,
        ai_base_url=base_url,
        ai_api_key="provider-secret",
        ai_model="approved-model",
    )

    with pytest.raises(RuntimeError, match="HTTPS remote API root"):
        settings.validate_remote_ai_api()


def test_ai_governance_rejects_partial_remote_api_configuration() -> None:
    settings = Settings(
        _env_file=None,
        ai_governance_enabled=True,
        ai_base_url="https://api.vendor.example/v1",
        ai_model="approved-model",
    )

    with pytest.raises(RuntimeError, match="URL, API key, and model"):
        settings.validate_remote_ai_api()


def test_semantic_search_accepts_third_party_https_embedding_api_without_local_fallback() -> None:
    settings = Settings(
        _env_file=None,
        search_semantic_enabled=True,
        search_embedding_base_url="https://embedding.vendor.example/v1",
        search_embedding_model="approved-embedding-v1",
    )

    settings.validate_remote_embedding_api()


@pytest.mark.parametrize(
    "base_url",
    (
        "http://embedding.vendor.example/v1",
        "https://localhost/v1",
        "https://embedding.localhost/v1",
        "https://127.0.0.1/v1",
        "https://[::1]/v1",
        "https://user:password@embedding.vendor.example/v1",
        "https://embedding.vendor.example/v1?tenant=one",
        "https://embedding.vendor.example/v1#fragment",
    ),
)
def test_semantic_search_rejects_non_remote_or_ambiguous_embedding_api_roots(base_url: str) -> None:
    settings = Settings(
        _env_file=None,
        search_semantic_enabled=True,
        search_embedding_base_url=base_url,
        search_embedding_model="approved-embedding-v1",
    )

    with pytest.raises(RuntimeError, match="HTTPS remote API root"):
        settings.validate_remote_embedding_api()


def test_semantic_search_rejects_missing_remote_embedding_contract() -> None:
    settings = Settings(_env_file=None, search_semantic_enabled=True)

    with pytest.raises(RuntimeError, match="remote embedding API URL and model"):
        settings.validate_remote_embedding_api()


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="human-session-production-secret",  # noqa: S106
        internal_service_jwt_secret="internal-service-production-secret",  # noqa: S106
        tenant_context_signing_secret="tenant-context-production-secret",  # noqa: S106
        mcp_cursor_signing_secret="cursor-signing-production-secret-123456",  # noqa: S106
        mcp_correlation_hmac_secret="correlation-production-secret-123456789",  # noqa: S106
        billing_statement_signing_secret="billing-statement-production-secret-123456",  # noqa: S106
        billing_provider_enabled=True,
        billing_provider_name="approved-erp",
        billing_provider_base_url="https://billing.example.test",
        billing_provider_api_token="billing-provider-production-token-123456789",  # noqa: S106
        export_manifest_signing_secret="export-manifest-production-secret-123456789",  # noqa: S106
        api_key_hash_salt="api-key-production-salt",
        postgres_runtime_password="runtime-database-production-password",  # noqa: S106
        human_auth_mode="oidc",
        human_oidc_issuer_url="https://identity.example.test",
        human_oidc_authorization_url="https://identity.example.test/authorize",
        human_oidc_token_url="https://identity.example.test/token",  # noqa: S106
        human_oidc_jwks_url="https://identity.example.test/jwks",
        human_oidc_client_id="pharma-workspace",
        human_oidc_redirect_uri="https://workspace.example.test/api/v1/auth/oidc/callback",
        mcp_token_verifier_mode="oidc",  # noqa: S106
        mcp_auth_issuer_url="https://identity.example.test",
        mcp_resource_server_url="https://mcp.example.test/mcp",
        mcp_oidc_jwks_url="https://identity.example.test/jwks",
        mcp_require_token_confirmation=True,
        mcp_dpop_required=True,
        redis_url="rediss://:production-valkey-password@valkey.example.test:6379/0",  # noqa: S106
        mcp_trusted_proxy_cidrs_config="10.42.0.0/16",
        object_store_backend="s3",
        object_store_s3_bucket="pharma-production",
        object_store_s3_access_key_id="object-access-key",
        object_store_s3_secret_access_key="object-secret-key",  # noqa: S106
        source_roots_config="/sources/knowledge",
        temporal_enabled=True,
        ai_governance_enabled=True,
        malware_scan_enabled=True,
        clamav_host="clamav.internal",
        parser_backend="service",
        parser_service_url="https://pharma-parser:8070",
        parser_service_token="parser-service-production-secret-123456789",  # noqa: S106
        parser_service_ca_certs="/etc/pharma-parser-server-ca/ca.crt",
        parser_service_client_cert="/etc/pharma-parser-client-tls/tls.crt",
        parser_service_client_key="/etc/pharma-parser-client-tls/tls.key",
        ocr_backend="service",
        ocr_service_url="https://pharma-ocr:8071",
        ocr_service_token="ocr-service-production-secret-123456789012",  # noqa: S106
        ocr_service_ca_certs="/etc/pharma-ocr-server-ca/ca.crt",
        ocr_service_client_cert="/etc/pharma-ocr-client-tls/tls.crt",
        ocr_service_client_key="/etc/pharma-ocr-client-tls/tls.key",
        ai_base_url="https://model.example.test/v1",
        ai_api_key="model-api-key",
        ai_model="governed-extractor",
        ai_allowed_response_models_json='["governed-extractor-2026-07"]',
        ai_input_cost_per_million_tokens=2,
        ai_output_cost_per_million_tokens=8,
        ai_max_document_cost=25,
        search_backend="opensearch",
        opensearch_url="https://search.example.test",
        opensearch_username="pharma-service",
        opensearch_password="search-production-password",  # noqa: S106
        opensearch_verify_certs=True,
        opensearch_index_replicas=1,
        search_semantic_enabled=True,
        search_embedding_base_url="https://model.example.test/v1",
        search_embedding_api_key="embedding-api-key",
        search_embedding_model="approved-remote-embedding-v1",
        search_projection_enabled=True,
        otel_enabled=True,
        otel_exporter_otlp_endpoint="https://otel.example.test:4317",
    )


def test_production_configuration_accepts_complete_independent_security_boundaries() -> None:
    settings = _production_settings()

    settings.validate_production()

    assert settings.effective_internal_service_jwt_secret == "internal-service-production-secret"  # noqa: S105
    assert settings.effective_tenant_context_signing_secret == "tenant-context-production-secret"  # noqa: S105
    assert settings.effective_mcp_cursor_signing_secret == "cursor-signing-production-secret-123456"  # noqa: S105
    assert settings.effective_mcp_correlation_hmac_secret == (
        "correlation-production-secret-123456789"  # noqa: S105
    )
    assert (
        settings.effective_billing_statement_signing_secret == "billing-statement-production-secret-123456"  # noqa: S105
    )
    assert settings.effective_export_manifest_signing_secret == (
        "export-manifest-production-secret-123456789"  # noqa: S105
    )


def test_production_prompt_only_ai_mode_requires_schema_in_prompt() -> None:
    settings = Settings(_env_file=None, ai_response_format_mode="prompt_only")

    with pytest.raises(RuntimeError, match="schema in the prompt"):
        settings.validate_ai_response_format()


def test_ai_fallback_provider_supports_independent_protocol_limits() -> None:
    settings = Settings(
        _env_file=None,
        ai_response_format_mode="json_object",
        ai_thinking_mode="enabled",
        ai_max_output_tokens_per_segment=512,
        ai_fallback_providers_json=json.dumps(
            [
                {
                    "name": "mimo",
                    "base_url": "https://fallback.example/v1",
                    "api_key": "fallback-secret",
                    "model": "fallback-model",
                    "response_format_mode": "prompt_only",
                    "thinking_mode": "disabled",
                    "include_schema_in_prompt": True,
                    "max_output_tokens_per_segment": 16384,
                    "request_timeout_seconds": 180,
                    "request_attempts": 2,
                }
            ]
        ),
    )

    provider = settings.ai_fallback_providers[0]

    assert provider.name == "mimo"
    assert provider.response_format_mode == "prompt_only"
    assert provider.thinking_mode == "disabled"
    assert provider.include_schema_in_prompt is True
    assert provider.max_output_tokens_per_segment == 16384
    assert provider.request_timeout_seconds == 180
    assert provider.request_attempts == 2


def test_ai_fallback_prompt_only_mode_requires_schema_in_prompt() -> None:
    settings = Settings(
        _env_file=None,
        ai_fallback_providers_json=json.dumps(
            [
                {
                    "name": "fallback",
                    "base_url": "https://fallback.example/v1",
                    "api_key": "fallback-secret",
                    "model": "fallback-model",
                    "response_format_mode": "prompt_only",
                    "include_schema_in_prompt": False,
                }
            ]
        ),
    )

    with pytest.raises(ValueError, match="schema in the prompt"):
        _ = settings.ai_fallback_providers


def test_production_rejects_non_authoritative_search_projection_mode() -> None:
    settings = _production_settings().model_copy(update={"search_allow_non_authoritative_projection": True})

    with pytest.raises(RuntimeError, match="Non-authoritative search projections"):
        settings.validate_production()


def test_production_accepts_openbao_dynamic_database_credentials_without_static_password() -> None:
    settings = _production_settings().model_copy(
        update={
            "database_credentials_mode": "openbao_dynamic",
            "database_url": "postgresql+psycopg://lease-user:lease-password@postgres.example.test/pharma",
            "postgres_runtime_password": "",
        }
    )

    settings.validate_production()


def test_openbao_dynamic_database_credentials_require_postgresql() -> None:
    settings = _production_settings().model_copy(
        update={
            "database_credentials_mode": "openbao_dynamic",
            "database_url": "sqlite:///unsafe.db",
            "postgres_runtime_password": "",
        }
    )

    with pytest.raises(RuntimeError, match="PostgreSQL psycopg URL"):
        settings.validate_production()


def _billing_worker_production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        jwt_secret="",
        internal_service_jwt_secret="",
        human_oidc_client_secret="",
        object_store_s3_access_key_id="",
        object_store_s3_secret_access_key="",
        ai_api_key="",
        database_credentials_mode="openbao_dynamic",
        database_url="postgresql+psycopg://lease-user:lease-password@postgres.example.test/pharma",
        tenant_context_signing_secret="billing-worker-tenant-secret-123456789",  # noqa: S106
        billing_statement_signing_secret="billing-worker-statement-secret-123456",  # noqa: S106
        billing_provider_enabled=True,
        billing_provider_name="approved-erp",
        billing_provider_base_url="https://billing.example.test",
        billing_provider_api_token="billing-worker-provider-token-123456789",  # noqa: S106
        otel_enabled=True,
        otel_exporter_otlp_endpoint="http://pharma-collector:4317",
    )


def test_billing_worker_production_profile_requires_only_role_scoped_secrets() -> None:
    settings = _billing_worker_production_settings()

    settings.validate_billing_worker_production()

    assert settings.jwt_secret == ""
    assert settings.human_oidc_client_secret == ""
    assert settings.object_store_s3_secret_access_key == ""
    assert settings.ai_api_key == ""


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"billing_provider_enabled": False}, "must enable"),
        ({"database_url": "sqlite:///unsafe.db"}, "PostgreSQL psycopg URL"),
        ({"tenant_context_signing_secret": "short"}, "Tenant-context"),
        ({"billing_statement_signing_secret": "short"}, "Billing statement"),
        (
            {"billing_statement_signing_secret": "billing-worker-tenant-secret-123456789"},
            "must be independent",
        ),
        ({"billing_provider_base_url": "http://billing.example.test"}, "credential-free HTTPS"),
        ({"billing_provider_api_token": "short"}, "at least 32 bytes"),
        ({"otel_enabled": False}, "OpenTelemetry"),
    ],
)
def test_billing_worker_production_profile_rejects_unsafe_configuration(
    updates: dict[str, object],
    message: str,
) -> None:
    settings = _billing_worker_production_settings().model_copy(update=updates)

    with pytest.raises(RuntimeError, match=message):
        settings.validate_billing_worker_production()


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"jwt_secret": ""}, "secrets"),
        ({"internal_service_jwt_secret": "human-session-production-secret"}, "must be different"),
        ({"tenant_context_signing_secret": "human-session-production-secret"}, "must be independent"),
        ({"mcp_cursor_signing_secret": "human-session-production-secret"}, "must be independent"),
        ({"mcp_cursor_signing_secret": "short"}, "at least 32 bytes"),
        ({"mcp_correlation_hmac_secret": "human-session-production-secret"}, "must be independent"),
        ({"mcp_correlation_hmac_secret": "short"}, "at least 32 bytes"),
        ({"billing_statement_signing_secret": "human-session-production-secret"}, "must be independent"),
        ({"billing_statement_signing_secret": "short"}, "at least 32 bytes"),
        ({"billing_provider_base_url": "http://billing.example.test"}, "credential-free HTTPS"),
        ({"billing_provider_base_url": "https://user@billing.example.test"}, "credential-free HTTPS"),
        ({"billing_provider_api_token": "short"}, "at least 32 bytes"),
        ({"billing_provider_api_token": "internal-service-production-secret"}, "must be independent"),
        ({"billing_provider_verify_certs": False}, "must verify certificates"),
        ({"billing_provider_ca_certs": "relative/ca.pem"}, "path must be absolute"),
        (
            {"billing_provider_lease_seconds": 30, "billing_provider_request_timeout_seconds": 30},
            "lease must exceed",
        ),
        ({"export_manifest_signing_secret": "human-session-production-secret"}, "must be independent"),
        ({"export_manifest_signing_secret": "short"}, "at least 32 bytes"),
        ({"human_auth_mode": "local"}, "must use OIDC"),
        ({"human_oidc_token_url": "http://identity.example.test/token"}, "do not use HTTPS"),
        ({"mcp_auth_enabled": False}, "cannot be disabled"),
        ({"mcp_commercial_enforcement_enabled": False}, "Commercial MCP enforcement"),
        ({"mcp_oidc_client_id_claim": ""}, "client identity claim"),
        ({"mcp_require_token_confirmation": False}, "confirmation key"),
        ({"mcp_dpop_required": False}, "DPoP sender constraints"),
        ({"redis_url": "redis://valkey.example.test:6379/0"}, "authenticated rediss URL"),
        ({"redis_url": "rediss://valkey.example.test:6379/0"}, "authenticated rediss URL"),
        ({"redis_url": "rediss://:password@127.0.0.1:6379/0"}, "authenticated rediss URL"),
        ({"mcp_correlation_key_id": "invalid key id"}, "correlation key ID"),
        ({"mcp_trusted_proxy_cidrs_config": ""}, "trusted proxy CIDRs"),
        ({"mcp_trusted_proxy_cidrs_config": "0.0.0.0/0"}, "explicit and bounded"),
        ({"mcp_token_verifier_mode": "api_key"}, "must use an OIDC"),
        ({"mcp_resource_server_url": "http://mcp.example.test/mcp"}, "must use HTTPS"),
        ({"object_store_backend": "filesystem"}, "must use an S3"),
        ({"object_store_s3_secret_access_key": ""}, "credentials"),
        ({"source_roots_config": ""}, "SOURCE_ROOTS"),
        ({"source_http_allow_insecure_loopback": True}, "Insecure loopback"),
        ({"source_http_allowed_origins_config": "http://supplier.example"}, "must use HTTPS"),
        ({"source_s3_allow_insecure_loopback": True}, "Insecure loopback S3"),
        ({"source_s3_endpoint_url": "http://s3.example.test"}, "S3 source endpoint must use HTTPS"),
        (
            {"source_sftp_allowed_origins_config": "sftp://supplier.example:22"},
            "SFTP sources require SOURCE_SFTP_KNOWN_HOSTS_PATH",
        ),
        ({"source_sftp_allow_password_auth": True}, "SFTP password authentication is disabled"),
        ({"source_smb_allow_insecure_loopback": True}, "Insecure loopback SMB"),
        (
            {"source_smb_allowed_origins_config": "smb://files.example:445", "source_smb_require_encryption": False},
            "SMB sources require SMB encryption",
        ),
        ({"temporal_enabled": False}, "must be enabled"),
        (
            {"temporal_worker_enabled": False, "temporal_scheduler_enabled": False},
            "process role",
        ),
        ({"ai_governance_enabled": False}, "AI governance"),
        ({"ai_base_url": "http://model.example.test/v1"}, "credential-free HTTPS"),
        ({"ai_base_url": "https://user@model.example.test/v1"}, "credential-free HTTPS"),
        ({"ai_max_document_chars": 100_000}, "character budget"),
        ({"ai_max_document_output_tokens": 1000}, "output budget"),
        ({"ai_require_usage_metadata": False}, "usage metadata"),
        ({"ai_require_provider_request_id": False}, "provider request IDs"),
        ({"ai_allowed_response_models_json": "[]"}, "response model allowlist"),
        ({"ai_input_cost_per_million_tokens": 0}, "positive token rates"),
        ({"ai_output_cost_per_million_tokens": 0}, "positive token rates"),
        ({"ai_max_document_cost": 0}, "document cost budget"),
        ({"malware_scan_enabled": False}, "ClamAV"),
        ({"parser_backend": "in_process"}, "isolated parser service"),
        ({"parser_service_url": "http://pharma-parser:8070"}, "must use HTTPS"),
        ({"parser_service_token": "short"}, "at least 32 bytes"),
        (
            {"parser_service_token": "cursor-signing-production-secret-123456"},
            "must be independent",
        ),
        (
            {"parser_service_max_file_bytes": 134_217_728},
            "cannot be lower than the malware scan limit",
        ),
        (
            {"parser_service_url": "https://parser.example.test", "parser_service_verify_certs": False},
            "must verify certificates",
        ),
        ({"parser_service_ca_certs": ""}, "absolute CA certificate path"),
        ({"parser_service_client_cert": ""}, "mTLS client certificate and key paths"),
        ({"parser_service_client_key": "relative.key"}, "mTLS client certificate and key paths"),
        ({"ocr_backend": "disabled"}, "isolated OCR service"),
        ({"ocr_service_url": "http://pharma-ocr:8071"}, "must use HTTPS"),
        ({"ocr_service_token": "short"}, "at least 32 bytes"),
        (
            {"ocr_service_token": "parser-service-production-secret-123456789"},
            "must be independent",
        ),
        ({"ocr_service_max_file_bytes": 134_217_728}, "cannot be lower than the malware scan limit"),
        ({"ocr_service_verify_certs": False}, "must verify certificates"),
        ({"ocr_service_ca_certs": ""}, "absolute CA certificate path"),
        ({"ocr_service_client_cert": ""}, "mTLS client certificate and key paths"),
        ({"search_backend": "database"}, "must use OpenSearch"),
        ({"search_projection_enabled": False}, "projection worker"),
        ({"opensearch_url": "http://search.example.test"}, "verified TLS"),
        ({"opensearch_verify_certs": False}, "verified TLS"),
        ({"opensearch_index_replicas": 0}, "at least one replica"),
        ({"search_semantic_enabled": False}, "hybrid semantic search"),
        ({"search_embedding_base_url": "http://model.example.test"}, "HTTPS remote API root"),
        ({"search_embedding_model": ""}, "remote embedding API URL and model"),
        ({"otel_enabled": False}, "OpenTelemetry"),
        ({"otel_exporter_otlp_endpoint": ""}, "OpenTelemetry"),
    ],
)
def test_production_configuration_rejects_unsafe_or_incomplete_boundaries(
    updates: dict[str, object],
    message: str,
) -> None:
    settings = _production_settings().model_copy(update=updates)

    with pytest.raises(RuntimeError, match=message):
        settings.validate_production()


def test_production_configuration_does_not_require_embedding_secret_in_non_consumer_processes() -> None:
    settings = _production_settings().model_copy(update={"search_embedding_api_key": ""})

    settings.validate_production()


def test_production_configuration_does_not_require_opensearch_secret_in_non_consumer_processes() -> None:
    settings = _production_settings().model_copy(update={"opensearch_username": "", "opensearch_password": ""})

    settings.validate_production()


def test_non_ingestion_production_process_does_not_receive_document_processing_tokens() -> None:
    settings = _production_settings().model_copy(
        update={
            "document_processing_credentials_required": False,
            "parser_service_token": "",
            "ocr_service_token": "",
        }
    )

    settings.validate_production()

    with pytest.raises(RuntimeError, match="must not receive document-processing"):
        settings.model_copy(update={"parser_service_token": "unexpected-token"}).validate_production()


def test_structured_environment_properties_validate_json_and_source_roots() -> None:
    settings = Settings(
        _env_file=None,
        source_roots_config="C:/knowledge; /srv/research ;",
        source_credential_env_allowlist_config="SUPPLIER_A, SUPPLIER_B;SUPPLIER_A",
        source_http_allowed_origins_config="https://a.example/; https://b.example",
        source_s3_allowed_buckets_config="supplier-a, supplier-b;supplier-a",
        source_sftp_allowed_origins_config="sftp://a.example:22, sftp://b.example:2222;sftp://a.example:22",
        source_smb_allowed_origins_config="smb://a.example:445, smb://b.example:1445;smb://a.example:445",
        mcp_trusted_proxy_cidrs_config="10.0.0.0/8, 2001:db8::/32;10.0.0.0/8",
        ai_auto_publish_fact_kinds_json='["claim","target_profile"]',
        human_oidc_role_mapping_json='{"analysts":"analyst","readers":"viewer"}',
    )

    assert [path.as_posix() for path in settings.source_roots] == ["C:/knowledge", "/srv/research"]
    assert settings.source_credential_env_allowlist == {"SUPPLIER_A", "SUPPLIER_B"}
    assert settings.source_http_allowed_origins == {"https://a.example", "https://b.example"}
    assert settings.source_s3_allowed_buckets == {"supplier-a", "supplier-b"}
    assert settings.source_sftp_allowed_origins == {"sftp://a.example:22", "sftp://b.example:2222"}
    assert settings.source_smb_allowed_origins == {"smb://a.example:445", "smb://b.example:1445"}
    assert {str(network) for network in settings.mcp_trusted_proxy_cidrs} == {"10.0.0.0/8", "2001:db8::/32"}
    assert settings.ai_auto_publish_fact_kinds == {"claim", "target_profile"}
    assert settings.human_oidc_role_mapping == {"analysts": "analyst", "readers": "viewer"}

    with pytest.raises(ValueError, match="string array"):
        _ = Settings(_env_file=None, ai_auto_publish_fact_kinds_json='{"claim":true}').ai_auto_publish_fact_kinds
    with pytest.raises(ValueError, match="viewer or analyst"):
        _ = Settings(_env_file=None, human_oidc_role_mapping_json='{"admins":"admin"}').human_oidc_role_mapping


def test_production_fallback_secrets_fail_closed() -> None:
    settings = Settings(_env_file=None, app_env="production", jwt_secret="configured")  # noqa: S106

    with pytest.raises(RuntimeError, match="INTERNAL_SERVICE_JWT_SECRET"):
        _ = settings.effective_internal_service_jwt_secret
    settings = settings.model_copy(update={"internal_service_jwt_secret": "internal"})
    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_SIGNING_SECRET"):
        _ = settings.effective_tenant_context_signing_secret
    with pytest.raises(RuntimeError, match="MCP_CURSOR_SIGNING_SECRET"):
        _ = settings.effective_mcp_cursor_signing_secret
    with pytest.raises(RuntimeError, match="MCP_CORRELATION_HMAC_SECRET"):
        _ = settings.effective_mcp_correlation_hmac_secret
    with pytest.raises(RuntimeError, match="BILLING_STATEMENT_SIGNING_SECRET"):
        _ = settings.effective_billing_statement_signing_secret
    with pytest.raises(RuntimeError, match="EXPORT_MANIFEST_SIGNING_SECRET"):
        _ = settings.effective_export_manifest_signing_secret


def test_development_cursor_secret_is_independently_derived_and_stable() -> None:
    settings = Settings(_env_file=None, jwt_secret="development-secret")  # noqa: S106

    assert len(settings.effective_mcp_cursor_signing_secret) == 64
    assert settings.effective_mcp_cursor_signing_secret != settings.effective_internal_service_jwt_secret
    assert settings.effective_mcp_cursor_signing_secret == settings.effective_mcp_cursor_signing_secret
    assert len(settings.effective_mcp_correlation_hmac_secret) == 64
    assert settings.effective_mcp_correlation_hmac_secret != settings.effective_mcp_cursor_signing_secret
    assert len(settings.effective_billing_statement_signing_secret) == 64
    assert settings.effective_billing_statement_signing_secret != settings.effective_mcp_cursor_signing_secret
    assert len(settings.effective_export_manifest_signing_secret) == 64
    assert settings.effective_export_manifest_signing_secret != settings.effective_billing_statement_signing_secret
