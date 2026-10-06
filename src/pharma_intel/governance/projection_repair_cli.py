from __future__ import annotations

import argparse
import re
import uuid

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.governance.chembl_projection_maintenance import ChemblProjectionMaintenance
from pharma_intel.object_store import build_object_store


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly apply proven legacy ChEMBL regional inference repairs"
    )
    parser.add_argument("--tenant-id", required=True, type=uuid.UUID)
    parser.add_argument("--data-source-id", required=True, type=uuid.UUID)
    parser.add_argument(
        "--apply", action="store_true", help="Explicit host-operator approval; never exposed as a Web shell"
    )
    parser.add_argument("--expected-plan-sha256", help="Exact checksum from an independently reviewed fresh preview")
    args = parser.parse_args()
    if args.apply and not re.fullmatch(r"[a-f0-9]{64}", args.expected_plan_sha256 or ""):
        parser.error("Apply requires the exact preview checksum")
    if not args.apply and args.expected_plan_sha256:
        parser.error("A checksum is only accepted with explicit --apply")
    try:
        settings = get_settings()
        with get_session_factory()() as session:
            if not args.apply and session.get_bind().dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION READ ONLY"))
            set_tenant_context(session, str(args.tenant_id))
            maintenance = ChemblProjectionMaintenance(
                session, build_object_store(settings), str(args.tenant_id), str(args.data_source_id)
            )
            result = maintenance.apply(args.expected_plan_sha256) if args.apply else maintenance.preview()
            print(result.model_dump_json(indent=2))
    except ValueError as exc:
        parser.exit(2, f"Projection maintenance refused: {exc}\n")
    except SQLAlchemyError:
        parser.exit(
            2, "Projection maintenance could not commit; review database locks/permissions and regenerate the preview\n"
        )


if __name__ == "__main__":
    run()
