from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class AIFallbackProviderSettings:
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8080
    log_level: str = "INFO"
    jobs_supervisor_poll_seconds: float = Field(default=0.5, ge=0.05, le=10)
    jobs_shutdown_timeout_seconds: float = Field(default=60, ge=1, le=300)
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_insecure: bool = False
    otel_metric_export_interval_ms: int = Field(default=60_000, ge=5_000, le=300_000)
    public_base_url: str = "http://127.0.0.1:8080"
    api_docs_enabled: bool = False
    database_url: str = "sqlite:///./data/pharma-intel.db"
    database_credentials_mode: Literal["static", "openbao_dynamic"] = "static"
    database_pool_size: int = Field(default=10, ge=1, le=200)
    database_max_overflow: int = Field(default=20, ge=0, le=400)
    database_pool_timeout_seconds: float = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=900, ge=30, le=86_400)
    postgres_runtime_user: str = "pharma_runtime"
    postgres_runtime_password: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: str = ""
    internal_service_jwt_secret: str = ""
    internal_token_issuer: str = "pharma-mcp-gateway"  # noqa: S105
    internal_token_audience: str = "pharma-domain-api"  # noqa: S105
    internal_token_lifetime_seconds: int = Field(default=300, ge=120, le=900)
    session_lifetime_minutes: int = 480
    human_auth_mode: Literal["local", "oidc"] = "local"
    human_self_registration_enabled: bool = False
    human_oidc_issuer_url: str = ""
    human_oidc_authorization_url: str = ""
    human_oidc_token_url: str = ""
    human_oidc_jwks_url: str = ""
    human_oidc_client_id: str = ""
    human_oidc_client_secret: str = ""
    human_oidc_redirect_uri: str = ""
    human_oidc_tenant_claim: str = "tenant_id"
    human_oidc_auto_provision: bool = False
    human_oidc_default_role: Literal["viewer", "analyst"] = "viewer"
    human_oidc_role_claim: str = "groups"
    human_oidc_role_mapping_json: str = "{}"
    api_key_hash_salt: str = ""
    tenant_context_signing_secret: str = ""
    search_backend: Literal["database", "opensearch"] = "database"
    opensearch_url: str = "http://127.0.0.1:9200"
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_verify_certs: bool = True
    opensearch_ca_certs: str = ""
    opensearch_request_timeout_seconds: float = Field(default=10, ge=1, le=120)
    opensearch_max_retries: int = Field(default=3, ge=0, le=10)
    opensearch_pool_maxsize: int = Field(default=50, ge=1, le=500)
    opensearch_index_prefix: str = Field(default="pharma", pattern=r"^[a-z][a-z0-9-]{1,39}$")
    opensearch_index_shards: int = Field(default=1, ge=1, le=64)
    opensearch_index_replicas: int = Field(default=0, ge=0, le=10)
    search_semantic_enabled: bool = False
    search_allow_non_authoritative_projection: bool = False
    search_embedding_base_url: str = ""
    search_embedding_api_key: str = ""
    search_embedding_model: str = ""
    search_embedding_dimensions: int = Field(default=1024, ge=2, le=8192)
    search_embedding_batch_size: int = Field(default=16, ge=1, le=128)
    search_embedding_max_input_chars: int = Field(default=8192, ge=256, le=100_000)
    search_embedding_request_timeout_seconds: float = Field(default=30, ge=1, le=300)
    search_embedding_max_retries: int = Field(default=2, ge=0, le=10)
    search_hybrid_lexical_weight: float = Field(default=0.4, ge=0.05, le=0.95)
    search_semantic_min_score: float = Field(default=0.55, ge=0.01, le=1)
    search_hybrid_max_candidates: int = Field(default=1000, ge=50, le=10_000)
    search_projection_enabled: bool = False
    search_projection_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    search_projection_batch_size: int = Field(default=50, ge=1, le=1000)
    search_projection_lease_seconds: int = Field(default=120, ge=15, le=3600)
    search_projection_max_attempts: int = Field(default=8, ge=1, le=100)
    search_projection_retry_base_seconds: float = Field(default=2, ge=0.1, le=300)
    search_projection_retry_max_seconds: float = Field(default=300, ge=1, le=86400)
    search_allow_global_rebuild: bool = False
    platform_operator_user_ids_config: str = Field(
        default="",
        validation_alias=AliasChoices("PLATFORM_OPERATOR_USER_IDS", "platform_operator_user_ids_config"),
    )
    monitoring_enabled: bool = True
    monitoring_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    monitoring_batch_size: int = Field(default=50, ge=1, le=1000)
    monitoring_lease_seconds: int = Field(default=120, ge=15, le=3600)
    monitoring_max_attempts: int = Field(default=8, ge=1, le=100)
    monitoring_retry_base_seconds: float = Field(default=2, ge=0.1, le=300)
    monitoring_retry_max_seconds: float = Field(default=300, ge=1, le=86400)
    data_quality_evaluation_interval_seconds: int = Field(default=900, ge=60, le=86_400)
    data_quality_window_hours: int = Field(default=24, ge=1, le=720)
    data_quality_issue_sla_hours: int = Field(default=24, ge=1, le=720)
    data_quality_completeness_min: float = Field(default=0.95, ge=0, le=1)
    data_quality_duplicate_rate_max: float = Field(default=0.05, ge=0, le=1)
    data_quality_citation_coverage_min: float = Field(default=0.99, ge=0, le=1)
    data_quality_freshness_coverage_min: float = Field(default=0.95, ge=0, le=1)
    data_quality_ingestion_success_min: float = Field(default=0.95, ge=0, le=1)
    data_quality_drift_max: float = Field(default=0.10, ge=0, le=1)
    search_chunk_chars: int = Field(default=2400, ge=500, le=20_000)
    search_chunk_overlap_chars: int = Field(default=240, ge=0, le=5000)
    search_max_source_text_bytes: int = Field(default=200_000_000, ge=1024, le=1_000_000_000)
    source_roots_config: str = Field(
        default="",
        validation_alias=AliasChoices("SOURCE_ROOTS", "source_roots_config"),
    )
    source_credential_env_allowlist_config: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SOURCE_CREDENTIAL_ENV_ALLOWLIST",
            "source_credential_env_allowlist_config",
        ),
    )
    source_credential_max_bytes: int = Field(default=16_384, ge=256, le=1_048_576)
    source_http_allowed_origins_config: str = Field(
        default="",
        validation_alias=AliasChoices("SOURCE_HTTP_ALLOWED_ORIGINS", "source_http_allowed_origins_config"),
    )
    source_http_allow_insecure_loopback: bool = False
    source_http_connect_timeout_seconds: float = Field(default=10, ge=1, le=30)
    source_http_read_timeout_seconds: float = Field(default=60, ge=1, le=300)
    source_http_max_manifest_bytes: int = Field(default=1_048_576, ge=1024, le=16_777_216)
    source_http_max_pages: int = Field(default=100, ge=1, le=1000)
    source_retry_base_seconds: int = Field(default=60, ge=1, le=86_400)
    source_retry_max_seconds: int = Field(default=3_600, ge=1, le=604_800)
    source_ncbi_tool: str = Field(default="pharma_intelligence_platform", min_length=1, max_length=200)
    source_ncbi_email: str = Field(default="", max_length=320)
    source_s3_allowed_buckets_config: str = Field(
        default="",
        validation_alias=AliasChoices("SOURCE_S3_ALLOWED_BUCKETS", "source_s3_allowed_buckets_config"),
    )
    source_s3_endpoint_url: str = ""
    source_s3_region: str = "us-east-1"
    source_s3_allow_insecure_loopback: bool = False
    source_s3_allow_default_credential_chain: bool = False
    source_s3_force_path_style: bool = False
    source_s3_connect_timeout_seconds: float = Field(default=10, ge=1, le=30)
    source_s3_read_timeout_seconds: float = Field(default=60, ge=1, le=300)
    source_s3_max_pages: int = Field(default=10_000, ge=1, le=100_000)
    source_s3_page_size: int = Field(default=1000, ge=1, le=1000)
    source_sftp_allowed_origins_config: str = Field(
        default="",
        validation_alias=AliasChoices("SOURCE_SFTP_ALLOWED_ORIGINS", "source_sftp_allowed_origins_config"),
    )
    source_sftp_known_hosts_path: str = ""
    source_sftp_allow_password_auth: bool = False
    source_sftp_connect_timeout_seconds: float = Field(default=10, ge=1, le=30)
    source_sftp_read_timeout_seconds: float = Field(default=60, ge=1, le=300)
    source_sftp_max_entries: int = Field(default=1_000_000, ge=1, le=10_000_000)
    source_sftp_max_depth: int = Field(default=64, ge=1, le=256)
    source_smb_allowed_origins_config: str = Field(
        default="",
        validation_alias=AliasChoices("SOURCE_SMB_ALLOWED_ORIGINS", "source_smb_allowed_origins_config"),
    )
    source_smb_require_encryption: bool = True
    source_smb_allow_insecure_loopback: bool = False
    source_smb_connect_timeout_seconds: float = Field(default=10, ge=1, le=30)
    source_smb_max_entries: int = Field(default=1_000_000, ge=1, le=10_000_000)
    source_smb_max_depth: int = Field(default=64, ge=1, le=256)
    ingest_scan_interval_seconds: int = 60
    ingest_stable_seconds: int = 30
    public_sync_catchup_interval_seconds: int = Field(default=30, ge=10, le=3600)
    ingest_max_file_bytes: int = 1_073_741_824
    parser_max_text_chars: int = 50_000_000
    document_processing_credentials_required: bool = True
    parser_backend: Literal["in_process", "service"] = "in_process"
    parser_service_url: str = "http://127.0.0.1:8070"
    parser_service_token: str = ""
    parser_service_connect_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    parser_service_request_timeout_seconds: float = Field(default=180, ge=1, le=3600)
    parser_service_max_file_bytes: int = Field(default=268_435_456, ge=1024, le=1_073_741_824)
    parser_service_verify_certs: bool = True
    parser_service_ca_certs: str = ""
    parser_service_client_cert: str = ""
    parser_service_client_key: str = ""
    ocr_backend: Literal["disabled", "service"] = "disabled"
    ocr_service_url: str = "http://127.0.0.1:8071"
    ocr_service_token: str = ""
    ocr_service_connect_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    ocr_service_request_timeout_seconds: float = Field(default=600, ge=1, le=3600)
    ocr_service_max_file_bytes: int = Field(default=268_435_456, ge=1024, le=1_073_741_824)
    ocr_service_verify_certs: bool = True
    ocr_service_ca_certs: str = ""
    ocr_service_client_cert: str = ""
    ocr_service_client_key: str = ""
    malware_scan_enabled: bool = False
    malware_scan_max_file_bytes: int = Field(default=268_435_456, ge=1024, le=1_073_741_824)
    clamav_host: str = "127.0.0.1"
    clamav_port: int = Field(default=3310, ge=1, le=65_535)
    clamav_connect_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    clamav_read_timeout_seconds: float = Field(default=180, ge=1, le=3600)
    clamav_stream_chunk_bytes: int = Field(default=65_536, ge=4096, le=1_048_576)
    object_store_backend: Literal["filesystem", "s3"] = "filesystem"
    object_store_root: Path = Path("./data/object-store")
    object_store_s3_endpoint_url: str = ""
    object_store_s3_region: str = "us-east-1"
    object_store_s3_bucket: str = "pharma-intelligence"
    object_store_s3_access_key_id: str = ""
    object_store_s3_secret_access_key: str = ""
    temporal_enabled: bool = False
    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "pharma-data-factory"
    temporal_worker_enabled: bool = True
    temporal_scheduler_enabled: bool = True
    temporal_connect_attempts: int = Field(default=12, ge=1, le=100)
    temporal_connect_backoff_seconds: float = Field(default=1.0, ge=0.1, le=60)
    temporal_connect_max_backoff_seconds: float = Field(default=15.0, ge=0.1, le=300)
    temporal_scheduler_poll_seconds: int = Field(default=30, ge=1, le=3600)
    temporal_max_concurrent_activities: int = Field(default=20, ge=1, le=1000)
    platform_operations_contract_path: Path = Path("deploy/operations/operations-contract.yaml")
    platform_evidence_root: Path | None = None
    deterministic_governance_enabled: bool = True
    ai_governance_enabled: bool = False
    llm_credentials_encryption_key: str = ""
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_fallback_providers_json: str = Field(default="[]", max_length=200_000)
    ai_allowed_response_models_json: str = "[]"
    ai_thinking_mode: Literal["provider_default", "enabled", "disabled"] = "provider_default"
    ai_include_schema_in_prompt: bool = False
    ai_response_format_mode: Literal["json_schema", "json_object", "prompt_only"] = "json_schema"
    ai_request_timeout_seconds: float = Field(default=120, ge=1, le=600)
    ai_request_attempts: int = Field(default=3, ge=1, le=8)
    ai_retry_base_backoff_seconds: float = Field(default=1, ge=0.1, le=60)
    ai_retry_max_backoff_seconds: float = Field(default=15, ge=0.1, le=300)
    ai_stale_run_seconds: int = Field(default=7200, ge=300, le=604800)
    ai_max_input_chars: int = Field(default=200_000, ge=2_000, le=1_000_000)
    ai_max_document_chars: int = Field(default=5_000_000, ge=2_000, le=100_000_000)
    ai_max_segments_per_document: int = Field(default=32, ge=1, le=10_000)
    ai_max_facts_per_segment: int = Field(default=100, ge=1, le=500)
    ai_max_model_string_chars: int = Field(default=4_000, ge=64, le=40_000)
    ai_max_model_collection_items: int = Field(default=100, ge=1, le=500)
    ai_max_output_tokens_per_segment: int = Field(default=16_384, ge=256, le=131_072)
    ai_max_document_input_tokens: int = Field(default=1_500_000, ge=1_000, le=100_000_000)
    ai_max_document_output_tokens: int = Field(default=262_144, ge=256, le=10_000_000)
    ai_max_response_bytes: int = Field(default=4_194_304, ge=1_024, le=67_108_864)
    ai_require_usage_metadata: bool = True
    ai_require_provider_request_id: bool = True
    ai_input_cost_per_million_tokens: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    ai_output_cost_per_million_tokens: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    ai_max_document_cost: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    ai_auto_publish_threshold: float = Field(default=0.95, ge=0.5, le=1)
    ai_auto_publish_fact_kinds_json: str = '["claim","relationship","target_profile"]'
    markdown_export_root: Path = Path("./data/markdown-wiki")
    agent_api_base_url: str = "http://127.0.0.1:8080"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8090
    mcp_auth_enabled: bool = True
    mcp_token_verifier_mode: Literal["api_key", "oidc"] = "api_key"  # noqa: S105
    mcp_auth_issuer_url: str = "http://127.0.0.1:8080"
    mcp_resource_server_url: str = "http://127.0.0.1:18390/mcp"
    mcp_oidc_jwks_url: str = ""
    mcp_oidc_audience: str = "pharma-intelligence-mcp"
    mcp_oidc_tenant_claim: str = "tenant_id"
    mcp_oidc_client_id_claim: str = "azp"
    mcp_oidc_jwks_cache_seconds: int = 300
    mcp_require_token_confirmation: bool = False
    mcp_dpop_required: bool = False
    mcp_dpop_max_proof_age_seconds: int = Field(default=120, ge=30, le=300)
    mcp_dpop_clock_skew_seconds: int = Field(default=30, ge=0, le=120)
    mcp_dpop_replay_timeout_seconds: float = Field(default=1.0, ge=0.1, le=5.0)
    mcp_required_scope: str = "mcp:connect"
    mcp_commercial_enforcement_enabled: bool = True
    mcp_reservation_lease_seconds: int = Field(default=120, ge=15, le=900)
    mcp_max_durable_result_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    mcp_max_billable_units_per_call: Decimal = Field(default=Decimal("1000000"), gt=0)
    mcp_max_active_reservations_per_client: int = Field(default=20, ge=1, le=1000)
    mcp_cursor_signing_secret: str = ""
    mcp_cursor_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    mcp_cursor_max_token_chars: int = Field(default=4096, ge=512, le=16_384)
    mcp_correlation_hmac_secret: str = ""
    mcp_correlation_key_id: str = Field(
        default="local-correlation-v1",
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$",
    )
    mcp_trusted_proxy_cidrs_config: str = Field(
        default="",
        validation_alias=AliasChoices("MCP_TRUSTED_PROXY_CIDRS", "mcp_trusted_proxy_cidrs_config"),
    )
    mcp_trusted_proxy_hops: int = Field(default=1, ge=1, le=8)
    mcp_network_ipv4_prefix_length: int = Field(default=24, ge=8, le=32)
    mcp_network_ipv6_prefix_length: int = Field(default=56, ge=32, le=128)
    billing_statement_signing_secret: str = ""
    billing_statement_signing_key_id: str = Field(default="local-billing-v1", min_length=1, max_length=120)
    billing_provider_enabled: bool = False
    billing_provider_name: str = Field(default="external-erp", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
    billing_provider_base_url: str = ""
    billing_provider_api_token: str = ""
    billing_provider_verify_certs: bool = True
    billing_provider_ca_certs: str = ""
    billing_provider_connect_timeout_seconds: float = Field(default=5, ge=0.1, le=30)
    billing_provider_request_timeout_seconds: float = Field(default=30, ge=1, le=120)
    billing_provider_max_response_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)
    billing_provider_max_metadata_bytes: int = Field(default=16_384, ge=256, le=262_144)
    billing_provider_poll_seconds: float = Field(default=2, ge=0.1, le=300)
    billing_provider_batch_size: int = Field(default=50, ge=1, le=1000)
    billing_provider_lease_seconds: int = Field(default=120, ge=15, le=3600)
    billing_provider_max_attempts: int = Field(default=8, ge=1, le=100)
    billing_provider_retry_base_seconds: float = Field(default=2, ge=0.1, le=300)
    billing_provider_retry_max_seconds: float = Field(default=300, ge=1, le=86_400)
    billing_dispute_sla_hours: int = Field(default=120, ge=1, le=720)
    export_manifest_signing_secret: str = ""
    export_manifest_signing_key_id: str = Field(default="local-export-v1", min_length=1, max_length=120)
    export_reservation_lease_seconds: int = Field(default=7200, ge=300, le=43_200)
    export_read_page_size_max: int = Field(default=250, ge=10, le=1000)
    web_root: Path = Path("/app/web")

    @property
    def source_roots(self) -> list[Path]:
        return [Path(item.strip()) for item in self.source_roots_config.split(";") if item.strip()]

    @property
    def platform_operator_user_ids(self) -> frozenset[str]:
        values = [
            item.strip() for item in self.platform_operator_user_ids_config.replace(",", ";").split(";") if item.strip()
        ]
        if len(values) > 100:
            raise ValueError("PLATFORM_OPERATOR_USER_IDS cannot contain more than 100 user IDs")
        if any(len(value) > 200 for value in values):
            raise ValueError("PLATFORM_OPERATOR_USER_IDS contains an invalid user ID")
        return frozenset(values)

    @property
    def source_credential_env_allowlist(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.source_credential_env_allowlist_config.replace(",", ";").split(";")
            if item.strip()
        )

    @property
    def source_http_allowed_origins(self) -> frozenset[str]:
        return frozenset(
            item.strip().rstrip("/")
            for item in self.source_http_allowed_origins_config.replace(",", ";").split(";")
            if item.strip()
        )

    @property
    def source_s3_allowed_buckets(self) -> frozenset[str]:
        return frozenset(
            item.strip() for item in self.source_s3_allowed_buckets_config.replace(",", ";").split(";") if item.strip()
        )

    @property
    def source_sftp_allowed_origins(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.source_sftp_allowed_origins_config.replace(",", ";").split(";")
            if item.strip()
        )

    @property
    def source_smb_allowed_origins(self) -> frozenset[str]:
        return frozenset(
            item.strip() for item in self.source_smb_allowed_origins_config.replace(",", ";").split(";") if item.strip()
        )

    @property
    def mcp_trusted_proxy_cidrs(self) -> tuple[IPv4Network | IPv6Network, ...]:
        values = [
            item.strip() for item in self.mcp_trusted_proxy_cidrs_config.replace(",", ";").split(";") if item.strip()
        ]
        if len(values) > 32:
            raise ValueError("MCP_TRUSTED_PROXY_CIDRS cannot contain more than 32 networks")
        try:
            networks = tuple(ip_network(value, strict=False) for value in values)
        except ValueError as exc:
            raise ValueError("MCP_TRUSTED_PROXY_CIDRS contains an invalid network") from exc
        return tuple(dict.fromkeys(networks))

    @property
    def ai_auto_publish_fact_kinds(self) -> frozenset[str]:
        parsed = json.loads(self.ai_auto_publish_fact_kinds_json)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("AI_AUTO_PUBLISH_FACT_KINDS_JSON must be a JSON string array")
        return frozenset(parsed)

    @property
    def ai_allowed_response_models(self) -> frozenset[str]:
        parsed = json.loads(self.ai_allowed_response_models_json)
        if (
            not isinstance(parsed, list)
            or len(parsed) > 100
            or not all(isinstance(item, str) and item.strip() and len(item) <= 500 for item in parsed)
        ):
            raise ValueError("AI_ALLOWED_RESPONSE_MODELS_JSON must be a JSON string array of approved model IDs")
        return frozenset(item.strip() for item in parsed)

    @property
    def ai_fallback_providers(self) -> tuple[AIFallbackProviderSettings, ...]:
        try:
            parsed = json.loads(self.ai_fallback_providers_json)
        except json.JSONDecodeError as exc:
            raise ValueError("AI_FALLBACK_PROVIDERS_JSON must be a JSON array") from exc
        if not isinstance(parsed, list) or len(parsed) > 8:
            raise ValueError("AI_FALLBACK_PROVIDERS_JSON must contain at most 8 providers")

        providers: list[AIFallbackProviderSettings] = []
        names: set[str] = {"primary"}
        required_keys = {"name", "base_url", "api_key", "model"}
        optional_keys = {
            "response_format_mode",
            "thinking_mode",
            "include_schema_in_prompt",
            "max_output_tokens_per_segment",
            "request_timeout_seconds",
            "request_attempts",
        }
        for item in parsed:
            if (
                not isinstance(item, dict)
                or not required_keys <= set(item)
                or set(item) - required_keys - optional_keys
            ):
                raise ValueError(
                    "AI_FALLBACK_PROVIDERS_JSON entries require name, base_url, api_key, and model and contain "
                    "only approved provider options"
                )
            values = {key: item[key] for key in required_keys}
            if not all(isinstance(value, str) for value in values.values()):
                raise ValueError("AI_FALLBACK_PROVIDERS_JSON entries must contain string values")
            name = values["name"].strip()
            base_url = values["base_url"].strip()
            api_key = values["api_key"].strip()
            model = values["model"].strip()
            if (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}", name)
                or name in names
                or not base_url
                or not api_key
                or not model
                or len(model) > 500
            ):
                raise ValueError("AI_FALLBACK_PROVIDERS_JSON contains an invalid provider")
            _validate_remote_https_api_root(base_url, f"AI fallback provider {name}")
            response_format_mode = item.get("response_format_mode", self.ai_response_format_mode)
            thinking_mode = item.get("thinking_mode", self.ai_thinking_mode)
            include_schema_in_prompt = item.get(
                "include_schema_in_prompt",
                self.ai_include_schema_in_prompt,
            )
            max_output_tokens = item.get(
                "max_output_tokens_per_segment",
                self.ai_max_output_tokens_per_segment,
            )
            timeout_seconds = item.get("request_timeout_seconds", self.ai_request_timeout_seconds)
            request_attempts = item.get("request_attempts", self.ai_request_attempts)
            if response_format_mode not in {"json_schema", "json_object", "prompt_only"}:
                raise ValueError("AI fallback provider response_format_mode is invalid")
            if thinking_mode not in {"provider_default", "enabled", "disabled"}:
                raise ValueError("AI fallback provider thinking_mode is invalid")
            if not isinstance(include_schema_in_prompt, bool):
                raise ValueError("AI fallback provider include_schema_in_prompt must be a boolean")
            if response_format_mode != "json_schema" and not include_schema_in_prompt:
                raise ValueError("AI fallback prompt-only response modes require the schema in the prompt")
            if (
                not isinstance(max_output_tokens, int)
                or isinstance(max_output_tokens, bool)
                or not 256 <= max_output_tokens <= 131_072
            ):
                raise ValueError("AI fallback provider max_output_tokens_per_segment is invalid")
            if (
                not isinstance(timeout_seconds, int | float)
                or isinstance(timeout_seconds, bool)
                or not 1 <= float(timeout_seconds) <= 600
            ):
                raise ValueError("AI fallback provider request_timeout_seconds is invalid")
            if (
                not isinstance(request_attempts, int)
                or isinstance(request_attempts, bool)
                or not 1 <= request_attempts <= 8
            ):
                raise ValueError("AI fallback provider request_attempts is invalid")
            names.add(name)
            providers.append(
                AIFallbackProviderSettings(
                    name=name,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    response_format_mode=response_format_mode,
                    thinking_mode=thinking_mode,
                    include_schema_in_prompt=include_schema_in_prompt,
                    max_output_tokens_per_segment=max_output_tokens,
                    request_timeout_seconds=float(timeout_seconds),
                    request_attempts=request_attempts,
                )
            )
        return tuple(providers)

    @property
    def effective_export_manifest_signing_secret(self) -> str:
        if self.export_manifest_signing_secret:
            if len(self.export_manifest_signing_secret.encode("utf-8")) < 32:
                raise RuntimeError("EXPORT_MANIFEST_SIGNING_SECRET must contain at least 32 bytes")
            return self.export_manifest_signing_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("EXPORT_MANIFEST_SIGNING_SECRET is required in production")
        seed = f"pharma-intel:export-manifest:v1:{self.effective_internal_service_jwt_secret}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @property
    def human_oidc_role_mapping(self) -> dict[str, Literal["viewer", "analyst"]]:
        parsed = json.loads(self.human_oidc_role_mapping_json)
        if not isinstance(parsed, dict) or not all(
            isinstance(group, str) and role in {"viewer", "analyst"} for group, role in parsed.items()
        ):
            raise ValueError("HUMAN_OIDC_ROLE_MAPPING_JSON must map group names to viewer or analyst")
        return parsed

    def validate_production(self) -> None:
        self.validate_remote_ai_api()
        self.validate_remote_embedding_api()
        self.validate_ai_response_format()
        if self.app_env.lower() != "production":
            return
        if self.search_allow_non_authoritative_projection:
            raise RuntimeError("Non-authoritative search projections are forbidden in production")
        weak = {"change-me", ""}
        if (
            self.jwt_secret in weak
            or self.internal_service_jwt_secret in weak
            or self.api_key_hash_salt in weak
            or self.tenant_context_signing_secret in weak
            or self.mcp_cursor_signing_secret in weak
            or self.mcp_correlation_hmac_secret in weak
            or self.billing_statement_signing_secret in weak
            or (self.billing_provider_enabled and self.billing_provider_api_token in weak)
            or self.export_manifest_signing_secret in weak
            or (self.database_credentials_mode == "static" and self.postgres_runtime_password in weak)
        ):
            raise RuntimeError("Production secrets are not configured")
        if self.database_credentials_mode == "openbao_dynamic" and not self.database_url.startswith(
            "postgresql+psycopg://"
        ):
            raise RuntimeError("OpenBao dynamic database credentials require a PostgreSQL psycopg URL")
        if self.internal_service_jwt_secret == self.jwt_secret:
            raise RuntimeError("Human and internal JWT secrets must be different in production")
        if self.tenant_context_signing_secret in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
        }:
            raise RuntimeError("Tenant-context signing secret must be independent in production")
        if self.mcp_cursor_signing_secret in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
            self.tenant_context_signing_secret,
        }:
            raise RuntimeError("MCP cursor signing secret must be independent in production")
        if len(self.mcp_cursor_signing_secret.encode("utf-8")) < 32:
            raise RuntimeError("MCP cursor signing secret must contain at least 32 bytes in production")
        if self.mcp_correlation_hmac_secret in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
            self.tenant_context_signing_secret,
            self.mcp_cursor_signing_secret,
            self.billing_statement_signing_secret,
            self.export_manifest_signing_secret,
        }:
            raise RuntimeError("MCP correlation HMAC secret must be independent in production")
        if len(self.mcp_correlation_hmac_secret.encode("utf-8")) < 32:
            raise RuntimeError("MCP correlation HMAC secret must contain at least 32 bytes in production")
        if self.billing_statement_signing_secret in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
            self.tenant_context_signing_secret,
            self.mcp_cursor_signing_secret,
            self.mcp_correlation_hmac_secret,
        }:
            raise RuntimeError("Billing statement signing secret must be independent in production")
        if len(self.billing_statement_signing_secret.encode("utf-8")) < 32:
            raise RuntimeError("Billing statement signing secret must contain at least 32 bytes in production")
        if self.billing_provider_enabled:
            self._validate_billing_provider_production()
        if self.export_manifest_signing_secret in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
            self.tenant_context_signing_secret,
            self.mcp_cursor_signing_secret,
            self.mcp_correlation_hmac_secret,
            self.billing_statement_signing_secret,
        }:
            raise RuntimeError("Export manifest signing secret must be independent in production")
        if len(self.export_manifest_signing_secret.encode("utf-8")) < 32:
            raise RuntimeError("Export manifest signing secret must contain at least 32 bytes in production")
        if self.human_auth_mode != "oidc":
            raise RuntimeError("Production human authentication must use OIDC")
        human_oidc_endpoints = (
            self.human_oidc_issuer_url,
            self.human_oidc_authorization_url,
            self.human_oidc_token_url,
            self.human_oidc_jwks_url,
            self.human_oidc_redirect_uri,
        )
        if (
            not self.human_oidc_client_id
            or not all(human_oidc_endpoints)
            or not all(value.startswith("https://") for value in human_oidc_endpoints)
        ):
            raise RuntimeError("Production human OIDC endpoints are incomplete or do not use HTTPS")
        if not self.mcp_auth_enabled:
            raise RuntimeError("MCP authentication cannot be disabled in production")
        if not self.mcp_commercial_enforcement_enabled:
            raise RuntimeError("Commercial MCP enforcement cannot be disabled in production")
        if self.mcp_token_verifier_mode != "oidc" or not self.mcp_oidc_jwks_url:  # noqa: S105
            raise RuntimeError("Production MCP authentication must use an OIDC JWKS verifier")
        if not self.mcp_oidc_client_id_claim:
            raise RuntimeError("Production MCP client identity claim is not configured")
        if not self.mcp_require_token_confirmation:
            raise RuntimeError("Production MCP access tokens must require a confirmation key")
        if not self.mcp_dpop_required:
            raise RuntimeError("Production MCP access tokens must enforce DPoP sender constraints")
        redis_endpoint = urlsplit(self.redis_url)
        if (
            redis_endpoint.scheme != "rediss"
            or not redis_endpoint.hostname
            or redis_endpoint.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}
            or redis_endpoint.password is None
        ):
            raise RuntimeError("Production DPoP replay storage requires an authenticated rediss URL")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}", self.mcp_correlation_key_id) is None:
            raise RuntimeError("Production MCP correlation key ID is invalid")
        trusted_proxy_cidrs = self.mcp_trusted_proxy_cidrs
        if not trusted_proxy_cidrs or any(network.prefixlen == 0 for network in trusted_proxy_cidrs):
            raise RuntimeError("Production MCP trusted proxy CIDRs must be explicit and bounded")
        secure_urls = (
            self.mcp_auth_issuer_url,
            self.mcp_resource_server_url,
            self.mcp_oidc_jwks_url,
        )
        if not all(url.startswith("https://") for url in secure_urls):
            raise RuntimeError("Production MCP authorization URLs must use HTTPS")
        if self.object_store_backend != "s3":
            raise RuntimeError("Production raw evidence must use an S3-compatible object store")
        object_store_credentials = (
            self.object_store_s3_bucket,
            self.object_store_s3_access_key_id,
            self.object_store_s3_secret_access_key,
        )
        if not all(object_store_credentials):
            raise RuntimeError("Production object-store credentials are not configured")
        if not self.temporal_enabled:
            raise RuntimeError("Temporal durable workflows must be enabled in production")
        if not self.temporal_worker_enabled and not self.temporal_scheduler_enabled:
            raise RuntimeError("At least one Temporal process role must be enabled")
        if not self.source_roots or any(not root.is_absolute() for root in self.source_roots):
            raise RuntimeError("Production automatic ingestion requires absolute SOURCE_ROOTS")
        if not self.malware_scan_enabled or not self.clamav_host.strip():
            raise RuntimeError("Production automatic ingestion requires fail-closed ClamAV scanning")
        if self.parser_backend != "service":
            raise RuntimeError("Production document parsing must use the isolated parser service")
        parser_service_url = urlsplit(self.parser_service_url)
        if parser_service_url.scheme != "https" or not parser_service_url.hostname:
            raise RuntimeError("Production parser service must use HTTPS")
        if self.document_processing_credentials_required:
            if len(self.parser_service_token.encode("utf-8")) < 32:
                raise RuntimeError("Production parser service token must contain at least 32 bytes")
            if self.parser_service_token in {
                self.jwt_secret,
                self.internal_service_jwt_secret,
                self.tenant_context_signing_secret,
                self.mcp_cursor_signing_secret,
                self.mcp_correlation_hmac_secret,
                self.billing_statement_signing_secret,
                self.export_manifest_signing_secret,
            }:
                raise RuntimeError("Production parser service token must be independent")
        elif self.parser_service_token or self.ocr_service_token:
            raise RuntimeError("Non-ingestion processes must not receive document-processing service tokens")
        if self.parser_service_max_file_bytes < self.malware_scan_max_file_bytes:
            raise RuntimeError("Production parser service file limit cannot be lower than the malware scan limit")
        if not self.parser_service_verify_certs:
            raise RuntimeError("Production parser service HTTPS must verify certificates")
        if not self.parser_service_ca_certs or not Path(self.parser_service_ca_certs).is_absolute():
            raise RuntimeError("Production parser service requires an absolute CA certificate path")
        parser_client_paths = (self.parser_service_client_cert, self.parser_service_client_key)
        if not all(parser_client_paths) or any(not Path(path).is_absolute() for path in parser_client_paths):
            raise RuntimeError("Production parser service requires absolute mTLS client certificate and key paths")
        if self.ocr_backend != "service":
            raise RuntimeError("Production scanned-document ingestion requires the isolated OCR service")
        ocr_service_url = urlsplit(self.ocr_service_url)
        if ocr_service_url.scheme != "https" or not ocr_service_url.hostname:
            raise RuntimeError("Production OCR service must use HTTPS")
        if self.document_processing_credentials_required:
            if len(self.ocr_service_token.encode("utf-8")) < 32:
                raise RuntimeError("Production OCR service token must contain at least 32 bytes")
            if self.ocr_service_token == self.parser_service_token:
                raise RuntimeError("Production OCR and parser service tokens must be independent")
        if self.ocr_service_max_file_bytes < self.malware_scan_max_file_bytes:
            raise RuntimeError("Production OCR service file limit cannot be lower than the malware scan limit")
        if not self.ocr_service_verify_certs:
            raise RuntimeError("Production OCR service HTTPS must verify certificates")
        if not self.ocr_service_ca_certs or not Path(self.ocr_service_ca_certs).is_absolute():
            raise RuntimeError("Production OCR service requires an absolute CA certificate path")
        ocr_client_paths = (self.ocr_service_client_cert, self.ocr_service_client_key)
        if not all(ocr_client_paths) or any(not Path(path).is_absolute() for path in ocr_client_paths):
            raise RuntimeError("Production OCR service requires absolute mTLS client certificate and key paths")
        if self.source_http_allow_insecure_loopback:
            raise RuntimeError("Insecure loopback HTTP sources cannot be enabled in production")
        if any(not origin.startswith("https://") for origin in self.source_http_allowed_origins):
            raise RuntimeError("Production HTTP source origins must use HTTPS")
        if self.source_s3_allow_insecure_loopback:
            raise RuntimeError("Insecure loopback S3 sources cannot be enabled in production")
        if self.source_s3_endpoint_url and not self.source_s3_endpoint_url.startswith("https://"):
            raise RuntimeError("Production S3 source endpoint must use HTTPS")
        if self.source_sftp_allowed_origins and not self.source_sftp_known_hosts_path:
            raise RuntimeError("Production SFTP sources require SOURCE_SFTP_KNOWN_HOSTS_PATH")
        if self.source_sftp_allow_password_auth:
            raise RuntimeError("Production SFTP password authentication is disabled")
        if self.source_smb_allow_insecure_loopback:
            raise RuntimeError("Insecure loopback SMB sources cannot be enabled in production")
        if self.source_smb_allowed_origins and not self.source_smb_require_encryption:
            raise RuntimeError("Production SMB sources require SMB encryption")
        if not self.ai_governance_enabled or not self.ai_base_url or not self.ai_api_key or not self.ai_model:
            raise RuntimeError("Production AI governance is not configured")
        if self.ai_max_document_chars < self.ai_max_input_chars:
            raise RuntimeError("Production AI document character budget cannot be below the segment budget")
        if self.ai_max_document_output_tokens < self.ai_max_output_tokens_per_segment:
            raise RuntimeError("Production AI document output budget cannot be below the per-segment budget")
        if not self.ai_require_usage_metadata or not self.ai_require_provider_request_id:
            raise RuntimeError("Production AI governance requires usage metadata and provider request IDs")
        if not self.ai_allowed_response_models:
            raise RuntimeError("Production AI governance requires an explicit response model allowlist")
        if (
            self.ai_input_cost_per_million_tokens <= 0
            or self.ai_output_cost_per_million_tokens <= 0
            or self.ai_max_document_cost <= 0
        ):
            raise RuntimeError("Production AI governance requires positive token rates and a document cost budget")
        if self.search_backend != "opensearch":
            raise RuntimeError("Production entity and evidence search must use OpenSearch")
        if not self.search_projection_enabled:
            raise RuntimeError("Production OpenSearch projection worker must be enabled")
        if not self.opensearch_url.startswith("https://") or not self.opensearch_verify_certs:
            raise RuntimeError("Production OpenSearch must use verified TLS")
        if self.opensearch_index_replicas < 1:
            raise RuntimeError("Production OpenSearch indexes require at least one replica")
        if not self.search_semantic_enabled:
            raise RuntimeError("Production hybrid semantic search must be enabled")
        if not self.otel_enabled or not self.otel_exporter_otlp_endpoint:
            raise RuntimeError("Production OpenTelemetry OTLP export must be enabled and configured")

    def validate_remote_ai_api(self, *, require_configuration: bool = False) -> None:
        configured = (self.ai_base_url, self.ai_api_key, self.ai_model)
        if not self.ai_governance_enabled and not require_configuration:
            return
        if not all(configured):
            raise RuntimeError("AI governance requires a remote API URL, API key, and model")
        _validate_remote_https_api_root(self.ai_base_url, "AI governance")

    def validate_ai_response_format(self) -> None:
        if self.ai_response_format_mode != "json_schema" and not self.ai_include_schema_in_prompt:
            raise RuntimeError("Production AI prompt-only response modes require the schema in the prompt")

    def validate_remote_embedding_api(self, *, require_api_key: bool = False) -> None:
        if not self.search_semantic_enabled and not require_api_key:
            return
        if not self.search_embedding_base_url or not self.search_embedding_model:
            raise RuntimeError("Semantic search requires a remote embedding API URL and model")
        if require_api_key and not self.search_embedding_api_key:
            raise RuntimeError("Semantic search requires a remote embedding API key")
        _validate_remote_https_api_root(self.search_embedding_base_url, "Semantic search")

    def validate_billing_worker_production(self) -> None:
        if self.app_env.lower() != "production":
            return
        if not self.billing_provider_enabled:
            raise RuntimeError("Production billing worker must enable the billing provider")
        if self.database_credentials_mode == "openbao_dynamic" and not self.database_url.startswith(
            "postgresql+psycopg://"
        ):
            raise RuntimeError("OpenBao dynamic database credentials require a PostgreSQL psycopg URL")
        if self.database_credentials_mode == "static" and self.postgres_runtime_password in {"", "change-me"}:
            raise RuntimeError("Production database credentials are not configured")
        tenant_secret = self.tenant_context_signing_secret
        billing_secret = self.billing_statement_signing_secret
        if len(tenant_secret.encode("utf-8")) < 32:
            raise RuntimeError("Tenant-context signing secret must contain at least 32 bytes in production")
        if len(billing_secret.encode("utf-8")) < 32:
            raise RuntimeError("Billing statement signing secret must contain at least 32 bytes in production")
        if billing_secret == tenant_secret:
            raise RuntimeError("Billing statement signing secret must be independent in production")
        self._validate_billing_provider_production()
        if not self.otel_enabled or not self.otel_exporter_otlp_endpoint:
            raise RuntimeError("Production billing worker requires OpenTelemetry OTLP export")

    def _validate_billing_provider_production(self) -> None:
        billing_provider_url = urlsplit(self.billing_provider_base_url)
        if (
            billing_provider_url.scheme != "https"
            or not billing_provider_url.hostname
            or billing_provider_url.username is not None
            or billing_provider_url.password is not None
            or billing_provider_url.query
            or billing_provider_url.fragment
        ):
            raise RuntimeError("Production billing provider must use a credential-free HTTPS service root")
        if len(self.billing_provider_api_token.encode("utf-8")) < 32:
            raise RuntimeError("Billing provider API token must contain at least 32 bytes in production")
        if self.billing_provider_api_token in {
            self.jwt_secret,
            self.internal_service_jwt_secret,
            self.tenant_context_signing_secret,
            self.mcp_cursor_signing_secret,
            self.mcp_correlation_hmac_secret,
            self.billing_statement_signing_secret,
            self.export_manifest_signing_secret,
        }:
            raise RuntimeError("Billing provider API token must be independent in production")
        if not self.billing_provider_verify_certs:
            raise RuntimeError("Production billing provider HTTPS must verify certificates")
        if self.billing_provider_ca_certs and not Path(self.billing_provider_ca_certs).is_absolute():
            raise RuntimeError("Billing provider CA certificate path must be absolute")
        if self.billing_provider_max_metadata_bytes > self.billing_provider_max_response_bytes:
            raise RuntimeError("Billing provider metadata limit cannot exceed the response limit")
        minimum_billing_lease = (
            self.billing_provider_connect_timeout_seconds + self.billing_provider_request_timeout_seconds + 10
        )
        if self.billing_provider_lease_seconds < minimum_billing_lease:
            raise RuntimeError("Billing provider delivery lease must exceed the request timeout budget")

    @property
    def effective_internal_service_jwt_secret(self) -> str:
        if self.internal_service_jwt_secret:
            return self.internal_service_jwt_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("INTERNAL_SERVICE_JWT_SECRET is required in production")
        return self.jwt_secret

    @property
    def effective_tenant_context_signing_secret(self) -> str:
        if self.tenant_context_signing_secret:
            return self.tenant_context_signing_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("TENANT_CONTEXT_SIGNING_SECRET is required in production")
        return self.effective_internal_service_jwt_secret

    @property
    def effective_mcp_cursor_signing_secret(self) -> str:
        if self.mcp_cursor_signing_secret:
            if len(self.mcp_cursor_signing_secret.encode("utf-8")) < 32:
                raise RuntimeError("MCP_CURSOR_SIGNING_SECRET must contain at least 32 bytes")
            return self.mcp_cursor_signing_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("MCP_CURSOR_SIGNING_SECRET is required in production")
        seed = f"pharma-intel:mcp-cursor:v1:{self.effective_internal_service_jwt_secret}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @property
    def effective_mcp_correlation_hmac_secret(self) -> str:
        if self.mcp_correlation_hmac_secret:
            if len(self.mcp_correlation_hmac_secret.encode("utf-8")) < 32:
                raise RuntimeError("MCP_CORRELATION_HMAC_SECRET must contain at least 32 bytes")
            return self.mcp_correlation_hmac_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("MCP_CORRELATION_HMAC_SECRET is required in production")
        seed = f"pharma-intel:mcp-correlation:v1:{self.effective_internal_service_jwt_secret}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @property
    def effective_billing_statement_signing_secret(self) -> str:
        if self.billing_statement_signing_secret:
            if len(self.billing_statement_signing_secret.encode("utf-8")) < 32:
                raise RuntimeError("BILLING_STATEMENT_SIGNING_SECRET must contain at least 32 bytes")
            return self.billing_statement_signing_secret
        if self.app_env.lower() == "production":
            raise RuntimeError("BILLING_STATEMENT_SIGNING_SECRET is required in production")
        seed = f"pharma-intel:billing-statement:v1:{self.effective_internal_service_jwt_secret}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _validate_remote_https_api_root(value: str, boundary: str) -> None:
    endpoint = urlsplit(value)
    hostname = (endpoint.hostname or "").casefold().rstrip(".")
    local_hostname = hostname == "localhost" or hostname.endswith(".localhost")
    loopback_address = False
    if hostname:
        try:
            loopback_address = ip_address(hostname).is_loopback
        except ValueError:
            pass
    if (
        endpoint.scheme != "https"
        or not hostname
        or local_hostname
        or loopback_address
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise RuntimeError(
            f"{boundary} must use a credential-free HTTPS remote API root; local endpoints are prohibited"
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    settings.validate_remote_ai_api()
    return settings


@lru_cache
def get_billing_worker_settings() -> Settings:
    settings = Settings()
    settings.validate_billing_worker_production()
    return settings
