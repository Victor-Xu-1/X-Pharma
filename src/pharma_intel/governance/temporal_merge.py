from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.models import DevelopmentPhase


def _validated_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GovernanceError("Validated governance date is not ISO 8601") from exc
    raise GovernanceError("Validated governance date has an invalid type")


def _required_datetime(value: Any, field_name: str) -> datetime:
    parsed = _validated_datetime(value)
    if parsed is None:
        raise GovernanceError(f"{field_name} is required")
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _should_update_temporal_state(current_at: datetime | None, incoming_at: datetime | None) -> bool:
    return current_at is None or (incoming_at is not None and _as_utc(incoming_at) >= _as_utc(current_at))


def _merge_program_status_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_phase: str,
    current_status: str | None,
    current_status_at: datetime | None,
    current_geography: str | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        phase = str(raw_event.get("phase") or "").strip()
        effective_at = _validated_datetime(raw_event.get("effective_at"))
        if not phase or effective_at is None:
            continue
        timestamp = effective_at.isoformat()
        status = str(raw_event.get("status") or "").strip()
        geography = str(raw_event.get("geography") or "").strip()
        event = {
            "phase": phase,
            "status": status or None,
            "effective_at": timestamp,
            "geography": geography or None,
            "reason": raw_event.get("reason"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(phase, status, timestamp, geography)] = event
    if current_status_at:
        timestamp = current_status_at.isoformat()
        status = (current_status or "").strip()
        geography = (current_geography or "").strip()
        events.setdefault(
            (current_phase, status, timestamp, geography),
            {
                "phase": current_phase,
                "status": status or None,
                "effective_at": timestamp,
                "geography": geography or None,
                "reason": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(
        events.values(),
        key=lambda event: (event["effective_at"], event["phase"], event.get("geography") or ""),
    )[-500:]


def _merge_program_milestones(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        milestone_type = str(raw_event.get("milestone_type") or "").strip()
        title = str(raw_event.get("title") or "").strip()
        occurred_at = _validated_datetime(raw_event.get("occurred_at"))
        if not milestone_type or not title or occurred_at is None:
            continue
        timestamp = occurred_at.isoformat()
        geography = str(raw_event.get("geography") or "").strip()
        event = {
            "milestone_type": milestone_type,
            "title": title,
            "occurred_at": timestamp,
            "geography": geography or None,
            "description": raw_event.get("description"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(milestone_type, title, timestamp, geography)] = event
    return sorted(
        events.values(),
        key=lambda event: (event["occurred_at"], event["milestone_type"], event["title"]),
    )[-500:]


def _merge_strings(existing: list[str], incoming: list[str], *, limit: int) -> list[str]:
    values = {str(value).strip() for value in [*existing, *incoming] if str(value).strip()}
    return sorted(values, key=str.casefold)[:limit]


def _merge_patent_publications(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any] | str],
) -> list[dict[str, Any]]:
    publications: dict[str, dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        item = {"publication_number": raw} if isinstance(raw, str) else dict(raw)
        publication_number = str(item.get("publication_number") or "").strip()
        if not publication_number:
            continue
        normalized = {
            "publication_number": publication_number,
            "application_number": item.get("application_number"),
            "jurisdiction": item.get("jurisdiction"),
            "publication_date": _iso_datetime(item.get("publication_date")),
            "grant_date": _iso_datetime(item.get("grant_date")),
        }
        previous = publications.get(publication_number)
        publications[publication_number] = {
            key: value if value is not None else (previous or {}).get(key) for key, value in normalized.items()
        }
    return sorted(publications.values(), key=lambda item: item["publication_number"])[:500]


def _merge_patent_legal_events(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_status: str | None,
    current_status_at: datetime | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        event_type = str(raw.get("event_type") or "").strip()
        occurred_at = _validated_datetime(raw.get("occurred_at"))
        if not event_type or occurred_at is None:
            continue
        status = str(raw.get("status") or "").strip()
        jurisdiction = str(raw.get("jurisdiction") or "").strip()
        timestamp = occurred_at.isoformat()
        event = {
            "event_type": event_type,
            "status": status or None,
            "occurred_at": timestamp,
            "jurisdiction": jurisdiction or None,
            "publication_number": raw.get("publication_number"),
            "description": raw.get("description"),
            "source_document_id": raw.get("source_document_id") or source_document_id,
        }
        events[(event_type, status, timestamp, jurisdiction)] = event
    if current_status and current_status_at:
        timestamp = current_status_at.isoformat()
        events.setdefault(
            ("status_update", current_status, timestamp, ""),
            {
                "event_type": "status_update",
                "status": current_status,
                "occurred_at": timestamp,
                "jurisdiction": None,
                "publication_number": None,
                "description": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(events.values(), key=lambda event: (event["occurred_at"], event["event_type"]))[-1000:]


def _merge_patent_claims(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    claims: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in [*existing, *incoming]:
        claim_number = str(raw.get("claim_number") or "").strip()
        claim_type = str(raw.get("claim_type") or "").strip()
        summary = str(raw.get("summary") or "").strip()
        if not claim_number or not claim_type or not summary:
            continue
        claims[(claim_number, claim_type)] = {
            "claim_number": claim_number,
            "claim_type": claim_type,
            "summary": summary,
            "scope": raw.get("scope"),
            "source_document_id": raw.get("source_document_id") or source_document_id,
        }
    return sorted(claims.values(), key=lambda claim: (claim["claim_number"], claim["claim_type"]))[:100]


def _iso_datetime(value: Any) -> str | None:
    parsed = _validated_datetime(value)
    return parsed.isoformat() if parsed is not None else None


def _merge_trial_status_history(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    current_status: str | None,
    current_status_at: datetime | None,
    source_document_id: str | None,
) -> list[dict[str, Any]]:
    events: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_event in [*existing, *incoming]:
        status = str(raw_event.get("status") or "").strip()
        effective_at = _validated_datetime(raw_event.get("effective_at"))
        if not status or effective_at is None:
            continue
        timestamp = effective_at.isoformat()
        event = {
            "status": status,
            "effective_at": timestamp,
            "reason": raw_event.get("reason"),
            "source_document_id": raw_event.get("source_document_id") or source_document_id,
        }
        events[(status, timestamp)] = event
    if current_status and current_status_at:
        timestamp = current_status_at.isoformat()
        events.setdefault(
            (current_status, timestamp),
            {
                "status": current_status,
                "effective_at": timestamp,
                "reason": None,
                "source_document_id": source_document_id,
            },
        )
    return sorted(events.values(), key=lambda event: (event["effective_at"], event["status"]))[-500:]


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError) as exc:
        raise GovernanceError("Validated governance number has an invalid value") from exc


def _normalize_phase(value: str) -> DevelopmentPhase | None:
    chinese_value = re.sub(r"\s+", "", value).casefold()
    chinese_aliases = {
        "药物发现": DevelopmentPhase.DISCOVERY,
        "发现": DevelopmentPhase.DISCOVERY,
        "临床前": DevelopmentPhase.PRECLINICAL,
        "临床前研究": DevelopmentPhase.PRECLINICAL,
        "申报临床": DevelopmentPhase.IND,
        "临床申请": DevelopmentPhase.IND,
        "i期临床": DevelopmentPhase.PHASE_1,
        "ⅰ期临床": DevelopmentPhase.PHASE_1,
        "一期临床": DevelopmentPhase.PHASE_1,
        "i/ii期临床": DevelopmentPhase.PHASE_1_2,
        "i-ii期临床": DevelopmentPhase.PHASE_1_2,
        "ⅰ/ⅱ期临床": DevelopmentPhase.PHASE_1_2,
        "一期/二期临床": DevelopmentPhase.PHASE_1_2,
        "ii期临床": DevelopmentPhase.PHASE_2,
        "ⅱ期临床": DevelopmentPhase.PHASE_2,
        "二期临床": DevelopmentPhase.PHASE_2,
        "ii/iii期临床": DevelopmentPhase.PHASE_2_3,
        "ii-iii期临床": DevelopmentPhase.PHASE_2_3,
        "ⅱ/ⅲ期临床": DevelopmentPhase.PHASE_2_3,
        "二期/三期临床": DevelopmentPhase.PHASE_2_3,
        "iii期临床": DevelopmentPhase.PHASE_3,
        "ⅲ期临床": DevelopmentPhase.PHASE_3,
        "三期临床": DevelopmentPhase.PHASE_3,
        "申请上市": DevelopmentPhase.FILED,
        "申报上市": DevelopmentPhase.FILED,
        "上市申请": DevelopmentPhase.FILED,
        "批准上市": DevelopmentPhase.APPROVED,
        "已批准": DevelopmentPhase.APPROVED,
        "已上市": DevelopmentPhase.APPROVED,
        "停止": DevelopmentPhase.DISCONTINUED,
        "停止研发": DevelopmentPhase.DISCONTINUED,
        "终止": DevelopmentPhase.DISCONTINUED,
        "撤回": DevelopmentPhase.DISCONTINUED,
    }
    if chinese_value in chinese_aliases:
        return chinese_aliases[chinese_value]
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    aliases = {
        "discovery": DevelopmentPhase.DISCOVERY,
        "research": DevelopmentPhase.DISCOVERY,
        "preclinical": DevelopmentPhase.PRECLINICAL,
        "pre_clinical": DevelopmentPhase.PRECLINICAL,
        "ind": DevelopmentPhase.IND,
        "phase_1": DevelopmentPhase.PHASE_1,
        "phase_i": DevelopmentPhase.PHASE_1,
        "phase_1_2": DevelopmentPhase.PHASE_1_2,
        "phase_i_ii": DevelopmentPhase.PHASE_1_2,
        "phase_2": DevelopmentPhase.PHASE_2,
        "phase_ii": DevelopmentPhase.PHASE_2,
        "phase_2_3": DevelopmentPhase.PHASE_2_3,
        "phase_ii_iii": DevelopmentPhase.PHASE_2_3,
        "phase_3": DevelopmentPhase.PHASE_3,
        "phase_iii": DevelopmentPhase.PHASE_3,
        "filed": DevelopmentPhase.FILED,
        "registration": DevelopmentPhase.FILED,
        "nda_bla_filed": DevelopmentPhase.FILED,
        "approved": DevelopmentPhase.APPROVED,
        "marketed": DevelopmentPhase.APPROVED,
        "discontinued": DevelopmentPhase.DISCONTINUED,
        "terminated": DevelopmentPhase.DISCONTINUED,
        "withdrawn": DevelopmentPhase.DISCONTINUED,
    }
    return aliases.get(normalized)
