from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.risk_cursor import RiskCaseFilter, RiskCursorCodec
from pharma_intel.commercial.service import CommercialAccessDenied, CommercialUsageService
from pharma_intel.models import (
    AgentClient,
    AgentClientSubject,
    AuditEvent,
    BillingAccount,
    CommercialPolicyEvent,
    CommercialRiskCase,
    CommercialSubscription,
    DataExportJob,
    OutboxEvent,
    UsageReservation,
    UsageReservationState,
    new_uuid,
)
from pharma_intel.security import Principal

RiskCaseStatus = Literal["acknowledged", "resolved", "dismissed"]


@dataclass(frozen=True)
class RiskEventPage:
    items: tuple[dict[str, Any], ...]
    total_items: int
    next_cursor: str | None


class CommercialOperationsError(Exception):
    pass


class CommercialOperationsNotFound(CommercialOperationsError):
    pass


class CommercialOperationsConflict(CommercialOperationsError):
    pass


class CommercialOperationsService:
    def __init__(self, session: Session, principal: Principal) -> None:
        if principal.actor_type != "user":
            raise CommercialAccessDenied("Human workspace account required")
        self.session = session
        self.principal = principal

    def list_clients(self, *, limit: int = 200) -> list[dict[str, Any]]:
        self.principal.require("commercial:read")
        if not 1 <= limit <= 500:
            raise ValueError("Client list limit must be between 1 and 500")
        now = datetime.now(UTC)
        clients = self.session.scalars(
            select(AgentClient)
            .where(AgentClient.tenant_id == self.principal.tenant_id)
            .order_by(AgentClient.display_name)
            .limit(limit)
        ).all()
        return [self._client_view(client, now) for client in clients]

    def set_client_active(self, client_id: str, *, active: bool, reason: str) -> dict[str, Any]:
        self.principal.require("commercial:write")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("A client status change reason is required")
        client = self.session.scalar(
            select(AgentClient)
            .where(
                AgentClient.tenant_id == self.principal.tenant_id,
                AgentClient.id == client_id,
            )
            .with_for_update()
        )
        if client is None:
            raise CommercialOperationsNotFound("Agent client does not exist")
        if client.active == active:
            return self._client_view(client, datetime.now(UTC))
        released = 0
        affected_exports = 0
        if not active:
            reservations = self.session.scalars(
                select(UsageReservation).where(
                    UsageReservation.tenant_id == self.principal.tenant_id,
                    UsageReservation.agent_client_id == client.id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                )
            ).all()
            for reservation in reservations:
                actor = Principal(
                    tenant_id=reservation.tenant_id,
                    actor_id=reservation.subject_id,
                    actor_type=reservation.actor_type,  # type: ignore[arg-type]
                    scopes=frozenset(),
                    client_id=client.oauth_client_id,
                )
                CommercialUsageService(self.session, actor).release(
                    reservation.id,
                    reason=f"client revoked: {normalized_reason}"[:500],
                    request_id=new_uuid(),
                )
                released += 1
            now = datetime.now(UTC)
            jobs = self.session.scalars(
                select(DataExportJob).where(
                    DataExportJob.tenant_id == self.principal.tenant_id,
                    DataExportJob.agent_client_id == client.id,
                    DataExportJob.state.in_(["pending_approval", "queued", "running"]),
                )
            ).all()
            for job in jobs:
                if job.state == "running":
                    job.state = "cancel_requested"
                    job.cancel_requested_at = now
                else:
                    job.state = "cancelled"
                    job.cancel_requested_at = now
                    job.completed_at = now
                job.updated_at = now
                affected_exports += 1
        client = self.session.scalar(
            select(AgentClient)
            .where(AgentClient.tenant_id == self.principal.tenant_id, AgentClient.id == client_id)
            .with_for_update()
        )
        if client is None:
            raise CommercialOperationsNotFound("Agent client does not exist")
        client.active = active
        self._audit(
            action="commercial.client.activate" if active else "commercial.client.revoke",
            resource_type="agent_client",
            resource_id=client.id,
            outcome="success",
            details={
                "reason": normalized_reason,
                "released_reservations": released,
                "affected_exports": affected_exports,
            },
        )
        self._outbox(
            "agent_client",
            client.id,
            "commercial.client_activated.v1" if active else "commercial.client_revoked.v1",
            {"active": active, "released_reservations": released, "affected_exports": affected_exports},
        )
        self.session.commit()
        return self._client_view(client, datetime.now(UTC))

    def list_risk_events(
        self,
        *,
        status: Literal["all", "open", "acknowledged", "resolved", "dismissed"] = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self.principal.require("commercial:read")
        if not 1 <= limit <= 500:
            raise ValueError("Risk-event list limit must be between 1 and 500")
        statement = (
            select(CommercialPolicyEvent, AgentClient, CommercialRiskCase)
            .join(AgentClient, AgentClient.id == CommercialPolicyEvent.agent_client_id)
            .outerjoin(CommercialRiskCase, CommercialRiskCase.policy_event_id == CommercialPolicyEvent.id)
            .where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialPolicyEvent.decision == "deny",
            )
            .order_by(CommercialPolicyEvent.occurred_at.desc())
            .limit(limit)
        )
        if status == "open":
            statement = statement.where(CommercialRiskCase.id.is_(None))
        elif status != "all":
            statement = statement.where(CommercialRiskCase.status == status)
        return [
            self._risk_view(event, client, risk_case) for event, client, risk_case in self.session.execute(statement)
        ]

    def list_risk_event_page(
        self,
        *,
        status: RiskCaseFilter,
        limit: int,
        cursor: str | None,
        cursor_codec: RiskCursorCodec,
    ) -> RiskEventPage:
        self.principal.require("commercial:read")
        if not 1 <= limit <= 100:
            raise ValueError("Risk-event page limit must be between 1 and 100")

        statement = self._risk_event_statement(status)
        count_statement = (
            select(func.count())
            .select_from(CommercialPolicyEvent)
            .outerjoin(CommercialRiskCase, CommercialRiskCase.policy_event_id == CommercialPolicyEvent.id)
            .where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialPolicyEvent.decision == "deny",
            )
        )
        count_statement = self._apply_risk_status(count_statement, status)
        total_items = int(self.session.scalar(count_statement) or 0)

        if cursor:
            occurred_at, event_id = cursor_codec.verify(
                cursor,
                tenant_id=self.principal.tenant_id,
                actor_id=self.principal.actor_id,
                case_status=status,
                page_size=limit,
            )
            statement = statement.where(
                or_(
                    CommercialPolicyEvent.occurred_at < occurred_at,
                    and_(
                        CommercialPolicyEvent.occurred_at == occurred_at,
                        CommercialPolicyEvent.id < event_id,
                    ),
                )
            )

        rows = list(
            self.session.execute(
                statement.order_by(
                    CommercialPolicyEvent.occurred_at.desc(),
                    CommercialPolicyEvent.id.desc(),
                ).limit(limit + 1)
            )
        )
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        items = tuple(self._risk_view(event, client, risk_case) for event, client, risk_case in visible_rows)
        next_cursor = None
        if has_more and visible_rows:
            last_event = visible_rows[-1][0]
            next_cursor = cursor_codec.issue(
                tenant_id=self.principal.tenant_id,
                actor_id=self.principal.actor_id,
                case_status=status,
                page_size=limit,
                occurred_at=last_event.occurred_at,
                event_id=last_event.id,
            )
        return RiskEventPage(items=items, total_items=total_items, next_cursor=next_cursor)

    def _risk_event_statement(self, status: RiskCaseFilter) -> Any:
        statement = (
            select(CommercialPolicyEvent, AgentClient, CommercialRiskCase)
            .join(AgentClient, AgentClient.id == CommercialPolicyEvent.agent_client_id)
            .outerjoin(CommercialRiskCase, CommercialRiskCase.policy_event_id == CommercialPolicyEvent.id)
            .where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialPolicyEvent.decision == "deny",
            )
        )
        return self._apply_risk_status(statement, status)

    @staticmethod
    def _apply_risk_status(statement: Any, status: RiskCaseFilter) -> Any:
        if status == "open":
            return statement.where(CommercialRiskCase.id.is_(None))
        if status != "all":
            return statement.where(CommercialRiskCase.status == status)
        return statement

    def review_risk_event(
        self,
        event_id: str,
        *,
        status: RiskCaseStatus,
        notes: str,
    ) -> dict[str, Any]:
        self.principal.require("commercial:write")
        event = self.session.scalar(
            select(CommercialPolicyEvent)
            .where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialPolicyEvent.id == event_id,
                CommercialPolicyEvent.decision == "deny",
            )
            .with_for_update()
        )
        if event is None:
            raise CommercialOperationsNotFound("Commercial risk event does not exist")
        risk_case = self.session.scalar(
            select(CommercialRiskCase)
            .where(
                CommercialRiskCase.tenant_id == self.principal.tenant_id,
                CommercialRiskCase.policy_event_id == event.id,
            )
            .with_for_update()
        )
        if risk_case is not None and risk_case.status in {"resolved", "dismissed"} and risk_case.status != status:
            raise CommercialOperationsConflict("Closed risk cases cannot transition to another status")
        now = datetime.now(UTC)
        if risk_case is None:
            risk_case = CommercialRiskCase(
                tenant_id=self.principal.tenant_id,
                policy_event_id=event.id,
                status=status,
                notes=notes.strip(),
                reviewed_by=self.principal.actor_id,
                reviewed_at=now,
            )
            self.session.add(risk_case)
        else:
            risk_case.status = status
            risk_case.notes = notes.strip()
            risk_case.reviewed_by = self.principal.actor_id
            risk_case.reviewed_at = now
        self._audit(
            action="commercial.risk.review",
            resource_type="commercial_policy_event",
            resource_id=event.id,
            outcome="success",
            details={"status": status},
        )
        self._outbox(
            "commercial_policy_event",
            event.id,
            "commercial.risk_reviewed.v1",
            {"status": status},
        )
        self.session.commit()
        client = self.session.get(AgentClient, event.agent_client_id)
        if client is None:
            raise CommercialOperationsNotFound("Risk-event client is unavailable")
        return self._risk_view(event, client, risk_case)

    def _client_view(self, client: AgentClient, now: datetime) -> dict[str, Any]:
        subscription = self.session.scalar(
            select(CommercialSubscription).where(
                CommercialSubscription.tenant_id == self.principal.tenant_id,
                CommercialSubscription.agent_client_id == client.id,
            )
        )
        account = self.session.get(BillingAccount, subscription.billing_account_id) if subscription else None
        subjects = self.session.scalars(
            select(AgentClientSubject).where(
                AgentClientSubject.tenant_id == self.principal.tenant_id,
                AgentClientSubject.agent_client_id == client.id,
            )
        ).all()
        active_reservations = int(
            self.session.scalar(
                select(func.count())
                .select_from(UsageReservation)
                .where(
                    UsageReservation.tenant_id == self.principal.tenant_id,
                    UsageReservation.agent_client_id == client.id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at > now,
                )
            )
            or 0
        )
        since = now - timedelta(hours=24)
        denial_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(CommercialPolicyEvent)
                .where(
                    CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                    CommercialPolicyEvent.agent_client_id == client.id,
                    CommercialPolicyEvent.decision == "deny",
                    CommercialPolicyEvent.occurred_at >= since,
                )
            )
            or 0
        )
        last_event_at = self.session.scalar(
            select(func.max(CommercialPolicyEvent.occurred_at)).where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialPolicyEvent.agent_client_id == client.id,
            )
        )
        available_units = None
        if subscription:
            available_units = format(
                subscription.granted_units - subscription.consumed_units - subscription.reserved_units,
                "f",
            )
        return {
            "id": client.id,
            "client_key": client.client_key,
            "display_name": client.display_name,
            "active": client.active,
            "subjects": [
                {"actor_type": subject.actor_type, "subject_id": subject.subject_id, "active": subject.active}
                for subject in subjects
            ],
            "subscription_key": subscription.subscription_key if subscription else None,
            "subscription_status": subscription.status.value if subscription else None,
            "billing_account_key": account.account_key if account else None,
            "available_units": available_units,
            "active_reservations": active_reservations,
            "denial_count_24h": denial_count,
            "last_policy_event_at": last_event_at,
            "created_at": client.created_at,
        }

    @staticmethod
    def _risk_view(
        event: CommercialPolicyEvent,
        client: AgentClient,
        risk_case: CommercialRiskCase | None,
    ) -> dict[str, Any]:
        return {
            "id": event.id,
            "client_id": client.id,
            "client_key": client.client_key,
            "client_name": client.display_name,
            "actor_type": event.actor_type,
            "subject_id": event.subject_id,
            "entitlement_key": event.entitlement_key,
            "phase": event.phase,
            "reason_code": event.reason_code,
            "query_sha256": event.query_sha256,
            "page_depth": event.page_depth,
            "requested_records": event.requested_records,
            "existing_unique_records": event.existing_unique_records,
            "projected_unique_records": event.projected_unique_records,
            "request_id": event.request_id,
            "details": event.details,
            "occurred_at": event.occurred_at,
            "case_status": risk_case.status if risk_case else "open",
            "case_notes": risk_case.notes if risk_case else "",
            "reviewed_by": risk_case.reviewed_by if risk_case else None,
            "reviewed_at": risk_case.reviewed_at if risk_case else None,
        }

    def _audit(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: str,
        details: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.principal.tenant_id,
                actor_type="user",
                actor_id=self.principal.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                request_id=new_uuid(),
                details=details,
            )
        )

    def _outbox(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=self.principal.tenant_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        )
