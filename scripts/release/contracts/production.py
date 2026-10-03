from __future__ import annotations

PRODUCTION_GATE_SCHEMA = "pharma.production-gate-evidence.v2"


PRODUCTION_GATE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "category",
        "status",
        "environment_kind",
        "environment_id",
        "tested_at",
        "subject",
        "checks",
        "executor",
        "artifacts",
        "approvals",
    }
)


PRODUCTION_ARTIFACT_FIELDS = frozenset({"name", "path", "size", "sha256", "reference"})


PRODUCTION_APPROVAL_FIELDS = frozenset(
    {"role", "reference", "organization", "approved_at", "artifact_path", "artifact_size", "artifact_sha256"}
)


PRODUCTION_INTAKE_SCHEMA = "pharma.production-evidence-intake.v1"


PRODUCTION_INTAKE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "category",
        "environment_kind",
        "environment_id",
        "tested_at",
        "checks",
        "executor",
        "artifacts",
        "approvals",
    }
)


PRODUCTION_INTAKE_ARTIFACT_FIELDS = frozenset({"name", "source_path", "destination", "reference"})


PRODUCTION_INTAKE_APPROVAL_FIELDS = frozenset(
    {"role", "source_path", "destination", "reference", "organization", "approved_at"}
)


PRODUCTION_HANDOFF_SCHEMA = "pharma.production-evidence-handoff.v2"


PRODUCTION_HANDOFF_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "subject",
        "policy_sha256",
        "categories",
        "files",
        "signature",
    }
)


PRODUCTION_HANDOFF_SUBJECT_FIELDS = frozenset({"git_commit", "source_file_count", "source_tree_sha256"})


PRODUCTION_HANDOFF_CATEGORY_FIELDS = frozenset({"category", "requirements"})


PRODUCTION_HANDOFF_FILE_FIELDS = frozenset({"path", "size", "sha256"})


PRODUCTION_HANDOFF_SIGNATURE_FIELDS = frozenset({"present", "key_id", "public_key_sha256"})


PRODUCTION_BATCH_INTAKE_SCHEMA = "pharma.production-evidence-batch-intake.v1"


PRODUCTION_BATCH_INTAKE_FIELDS = frozenset({"schema", "schema_version", "requests"})


PRODUCTION_BATCH_ENTRY_FIELDS = frozenset({"category", "request_path"})


PRODUCTION_BATCH_MANIFEST_SCHEMA = "pharma.production-evidence-batch.v1"


PRODUCTION_BATCH_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "subject",
        "security_manifest_sha256",
        "categories",
    }
)


PRODUCTION_BATCH_CATEGORY_FIELDS = frozenset({"category", "statement", "statement_sha256"})


MAX_PRODUCTION_BATCH_CATEGORIES = 64


MAX_PRODUCTION_EVIDENCE_FILE_BYTES = 1024 * 1024 * 1024


MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES = 4 * 1024 * 1024 * 1024


MAX_PRODUCTION_INTAKE_BYTES = 1024 * 1024
