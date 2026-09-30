from __future__ import annotations

import argparse

from pharma_intel.config import get_settings
from pharma_intel.job_roles import enabled_job_role_specs
from pharma_intel.runtime_heartbeat import RuntimeHeartbeatError, verify_runtime_heartbeat


def verify_jobs_health() -> None:
    settings = get_settings()
    roles = enabled_job_role_specs(settings)
    if not roles:
        raise RuntimeHeartbeatError("no unified jobs roles are enabled")
    process_ids: set[int] = set()
    for role in roles:
        status = verify_runtime_heartbeat(
            role.heartbeat_service,
            max_age_seconds=role.heartbeat_max_age_seconds,
        )
        process_ids.add(status.pid)
    if len(process_ids) != 1:
        raise RuntimeHeartbeatError("unified jobs role heartbeats do not belong to one process")


def run() -> None:
    parser = argparse.ArgumentParser(description="Verify every role in the unified jobs process")
    try:
        verify_jobs_health()
    except RuntimeHeartbeatError as exc:
        parser.error(str(exc))
