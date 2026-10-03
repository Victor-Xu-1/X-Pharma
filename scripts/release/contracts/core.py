from __future__ import annotations

import re

STATEMENT_SCHEMA = "pharma.release-gate-statement.v1"


BUNDLE_SCHEMA = "pharma.release-evidence-bundle.v1"


SIGNATURE_SCHEMA = "pharma.release-evidence-signature.v1"


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


COMMIT_PATTERN = re.compile(r"[0-9a-f]{40,64}")


CATEGORY_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,63}")


IMAGE_PATTERN = re.compile(r".+@sha256:([0-9a-f]{64})")


MAX_CAPTURE_LOG_BYTES = 64 * 1024 * 1024


MAX_RELEASE_STATEMENTS = 128


UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


ENVIRONMENT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}")


REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#@-]{2,499}")


UNITS_PATTERN = re.compile(r"[0-9]+\.[0-9]{8}")
