from __future__ import annotations

import sys
from pathlib import Path

# Direct CLI execution resolves only its own trusted checkout, not caller input.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release import (  # noqa: E402 - trusted standalone CLI bootstrap above.
    ReleaseEvidenceError as ReleaseEvidenceError,
)
from scripts.release import (
    _atomic_write as _atomic_write,
)
from scripts.release import (
    _canonical_json as _canonical_json,
)
from scripts.release import (
    assemble_bundle as assemble_bundle,
)
from scripts.release import (
    audit_release as audit_release,
)
from scripts.release import (
    capture_gate as capture_gate,
)
from scripts.release import (
    load_policy as load_policy,
)
from scripts.release import (
    repository_subject as repository_subject,
)
from scripts.release import (
    validate_security_evidence as validate_security_evidence,
)
from scripts.release.cli import run  # noqa: E402

if __name__ == "__main__":
    run()
