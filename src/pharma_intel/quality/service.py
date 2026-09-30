from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    AuditEvent,
    DataQualityIssue,
    DataQualityIssueEvent,
    DataQualitySnapshot,
    DataSource,
    DataSourceState,
    FactProvenanceLink,
    GovernanceStatus,
    IngestionRun,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceVersion,
    StagedFact,
    StageStatus,
    User,
    UserRole,
)

DEFINITIONS_VERSION = "quality-v1"
ACTIVE_ISSUE_STATUSES = {"open", "acknowledged", "ready_to_resolve"}


class DataQualityError(RuntimeError):
    pass


@dataclass(frozen=True)
class QualityRule:
    key: str
    label: str
    comparison: Literal["gte", "lte"]
    threshold: float
    severity: Literal["critical", "high", "medium", "low"]


class DataQualityService:
    def __init__(self, session: Session, settings: Settings, tenant_id: str):
        self.session = session
        self.settings = settings
        self.tenant_id = tenant_id
        set_tenant_context(session, tenant_id)

    def evaluate(self, *, trigger: str, actor_type: str, actor_id: str) -> DataQualitySnapshot:
        if trigger not in {"scheduled", "manual"}:
            raise DataQualityError("Unsupported data quality evaluation trigger")
        measured_at = datetime.now(UTC)
        window_start = measured_at - timedelta(hours=self.settings.data_quality_window_hours)
        previous = self.session.scalar(
            select(DataQualitySnapshot)
            .where(DataQualitySnapshot.tenant_id == self.tenant_id)
            .order_by(DataQualitySnapshot.measured_at.desc(), DataQualitySnapshot.id.desc())
            .limit(1)
        )
        metrics = self._measure(window_start, measured_at, previous)
        snapshot = DataQualitySnapshot(
            tenant_id=self.tenant_id,
            trigger=trigger,
            definitions_version=DEFINITIONS_VERSION,
            window_start=window_start,
            window_end=measured_at,
            measured_at=measured_at,
            metrics=metrics,
        )
        self.session.add(snapshot)
        self.session.flush()
        self._reconcile_issues(snapshot, actor_type, actor_id)
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="quality.snapshot.measured",
                resource_type="data_quality_snapshot",
                resource_id=snapshot.id,
                outcome="success",
                request_id=snapshot.id,
                details={
                    "trigger": trigger,
                    "definitions_version": DEFINITIONS_VERSION,
                    "failed_metrics": sorted(
                        key for key, metric in metrics.items() if metric.get("status") == "failed"
                    ),
                },
            )
        )
        self.session.commit()
        return snapshot

    def snapshots(self, limit: int = 90) -> list[DataQualitySnapshot]:
        return list(
            self.session.scalars(
                select(DataQualitySnapshot)
                .where(DataQualitySnapshot.tenant_id == self.tenant_id)
                .order_by(DataQualitySnapshot.measured_at.desc(), DataQualitySnapshot.id.desc())
                .limit(limit)
            )
        )

    def coverage(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return an auditable quality and authorization view for each registered source."""
        if limit < 1 or limit > 100:
            raise ValueError("Quality coverage limit must be between 1 and 100")
        measured_at = datetime.now(UTC)
        window_start = measured_at - timedelta(hours=self.settings.data_quality_window_hours)
        sources = list(
            self.session.scalars(
                select(DataSource)
                .where(
                    DataSource.tenant_id == self.tenant_id,
                    DataSource.state != DataSourceState.DISABLED,
                )
                .order_by(DataSource.dataset_key, DataSource.name, DataSource.id)
                .limit(limit)
            )
        )
        if not sources:
            return []
        source_ids = [source.id for source in sources]

        asset_counts = {
            source_id: int(count)
            for source_id, count in self.session.execute(
                select(SourceAsset.data_source_id, func.count(SourceAsset.id))
                .where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id.in_(source_ids),
                )
                .group_by(SourceAsset.data_source_id)
            )
        }
        active_asset_counts = {
            source_id: int(count)
            for source_id, count in self.session.execute(
                select(SourceAsset.data_source_id, func.count(SourceAsset.id))
                .where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id.in_(source_ids),
                    SourceAsset.state == SourceAssetState.ACTIVE,
                )
                .group_by(SourceAsset.data_source_id)
            )
        }
        parsed_asset_counts = {
            source_id: int(count)
            for source_id, count in self.session.execute(
                select(SourceAsset.data_source_id, func.count(SourceAsset.id))
                .join(SourceVersion, SourceVersion.id == SourceAsset.current_version_id)
                .where(
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id.in_(source_ids),
                    SourceAsset.state == SourceAssetState.ACTIVE,
                    SourceVersion.parse_status == StageStatus.SUCCEEDED,
                    SourceVersion.source_document_id.is_not(None),
                )
                .group_by(SourceAsset.data_source_id)
            )
        }
        fact_counts: dict[str, dict[str, int]] = {}
        for source_id, status, count in self.session.execute(
            select(
                SourceAsset.data_source_id,
                StagedFact.status,
                func.count(distinct(StagedFact.id)),
            )
            .join(FactProvenanceLink, FactProvenanceLink.source_asset_id == SourceAsset.id)
            .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
            .where(
                SourceAsset.tenant_id == self.tenant_id,
                FactProvenanceLink.tenant_id == self.tenant_id,
                StagedFact.tenant_id == self.tenant_id,
                SourceAsset.data_source_id.in_(source_ids),
            )
            .group_by(SourceAsset.data_source_id, StagedFact.status)
        ):
            status_key = status.value if isinstance(status, GovernanceStatus) else str(status)
            fact_counts.setdefault(source_id, {})[status_key] = int(count)

        terminal_states = [RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELED, RunState.PARTIAL]
        run_counts: dict[str, dict[str, int]] = {}
        for source_id, state, count in self.session.execute(
            select(IngestionRun.data_source_id, IngestionRun.state, func.count(IngestionRun.id))
            .where(
                IngestionRun.tenant_id == self.tenant_id,
                IngestionRun.data_source_id.in_(source_ids),
                IngestionRun.created_at >= window_start,
                IngestionRun.state.in_(terminal_states),
            )
            .group_by(IngestionRun.data_source_id, IngestionRun.state)
        ):
            state_key = state.value if isinstance(state, RunState) else str(state)
            run_counts.setdefault(source_id, {})[state_key] = int(count)

        failure_sla = timedelta(hours=self.settings.data_quality_issue_sla_hours)
        result: list[dict[str, Any]] = []
        for source in sources:
            active_assets = active_asset_counts.get(source.id, 0)
            parsed_assets = parsed_asset_counts.get(source.id, 0)
            source_facts = fact_counts.get(source.id, {})
            fact_count = sum(source_facts.values())
            published_count = source_facts.get(GovernanceStatus.PUBLISHED.value, 0)
            review_pending_count = source_facts.get(GovernanceStatus.REVIEW_PENDING.value, 0)
            conflict_count = source_facts.get(GovernanceStatus.CONFLICT.value, 0)
            rejected_count = source_facts.get(GovernanceStatus.REJECTED.value, 0)
            source_runs = run_counts.get(source.id, {})
            run_count = sum(source_runs.values())
            successful_runs = source_runs.get(RunState.SUCCEEDED.value, 0)
            failed_runs = source_runs.get(RunState.FAILED.value, 0)

            last_success_at = self._aware(source.last_success_at) if source.last_success_at else None
            freshness_age_seconds = (
                max(0, int((measured_at - last_success_at).total_seconds())) if last_success_at else None
            )
            if last_success_at is None:
                freshness_status = "never_succeeded"
            elif freshness_age_seconds is not None and freshness_age_seconds > source.expected_freshness_seconds:
                freshness_status = "stale"
            else:
                freshness_status = "fresh"

            authorization_valid_from = self._aware(source.authorization_valid_from)
            authorization_valid_until = (
                self._aware(source.authorization_valid_until) if source.authorization_valid_until else None
            )
            if not source.authorization_scopes:
                authorization_status = "missing_scope"
            elif measured_at < authorization_valid_from:
                authorization_status = "not_yet_valid"
            elif authorization_valid_until and measured_at >= authorization_valid_until:
                authorization_status = "expired"
            elif authorization_valid_until and authorization_valid_until - measured_at <= timedelta(days=7):
                authorization_status = "expiring"
            else:
                authorization_status = "valid"

            unavailable_since = self._aware(source.unavailable_since) if source.unavailable_since else None
            failure_age_seconds = (
                max(0, int((measured_at - unavailable_since).total_seconds())) if unavailable_since else None
            )
            if source.consecutive_failures == 0:
                failure_sla_status = "healthy"
            elif unavailable_since is not None and measured_at - unavailable_since > failure_sla:
                failure_sla_status = "breached"
            else:
                failure_sla_status = "at_risk"

            result.append(
                {
                    "source_id": source.id,
                    "name": source.name,
                    "source_type": source.source_type.value,
                    "dataset_key": source.dataset_key,
                    "owner": source.owner,
                    "state": source.state.value,
                    "data_classification": source.data_classification,
                    "authorization_scopes": list(source.authorization_scopes),
                    "authorization_valid_until": source.authorization_valid_until,
                    "authorization_status": authorization_status,
                    "asset_count": asset_counts.get(source.id, 0),
                    "active_asset_count": active_assets,
                    "parsed_asset_count": parsed_assets,
                    "parse_missing_count": max(active_assets - parsed_assets, 0),
                    "parse_coverage": round(self._ratio(parsed_assets, active_assets), 6),
                    "fact_count": fact_count,
                    "published_fact_count": published_count,
                    "review_pending_fact_count": review_pending_count,
                    "conflict_fact_count": conflict_count,
                    "rejected_fact_count": rejected_count,
                    "published_fact_coverage": round(self._ratio(published_count, fact_count), 6),
                    "conflict_rate": round(self._ratio(conflict_count, fact_count), 6),
                    "window_start": window_start,
                    "measured_at": measured_at,
                    "run_count": run_count,
                    "successful_run_count": successful_runs,
                    "failed_run_count": failed_runs,
                    "ingestion_success_rate": round(self._ratio(successful_runs, run_count), 6),
                    "last_scanned_at": source.last_scanned_at,
                    "last_success_at": source.last_success_at,
                    "expected_freshness_seconds": source.expected_freshness_seconds,
                    "freshness_age_seconds": freshness_age_seconds,
                    "freshness_status": freshness_status,
                    "consecutive_failures": source.consecutive_failures,
                    "failure_sla_age_seconds": failure_age_seconds,
                    "failure_sla_status": failure_sla_status,
                    "last_error_present": bool(source.last_error),
                }
            )
        return result

    def issues(self, status: str | None = None, limit: int = 500) -> list[DataQualityIssue]:
        statement = select(DataQualityIssue).where(DataQualityIssue.tenant_id == self.tenant_id)
        if status:
            statement = statement.where(DataQualityIssue.status == status)
        return list(
            self.session.scalars(
                statement.order_by(DataQualityIssue.sla_due_at, DataQualityIssue.created_at.desc()).limit(limit)
            )
        )

    def events(self, issue_id: str) -> list[DataQualityIssueEvent]:
        self._issue(issue_id)
        return list(
            self.session.scalars(
                select(DataQualityIssueEvent)
                .where(
                    DataQualityIssueEvent.tenant_id == self.tenant_id,
                    DataQualityIssueEvent.issue_id == issue_id,
                )
                .order_by(DataQualityIssueEvent.occurred_at, DataQualityIssueEvent.id)
            )
        )

    def act(
        self,
        issue_id: str,
        *,
        action: Literal["assign", "acknowledge", "resolve", "waive"],
        expected_version: int,
        actor_id: str,
        request_id: str,
        owner_user_id: str | None,
        notes: str | None,
    ) -> DataQualityIssue:
        issue = self.session.scalar(
            select(DataQualityIssue)
            .where(DataQualityIssue.tenant_id == self.tenant_id, DataQualityIssue.id == issue_id)
            .with_for_update()
        )
        if issue is None:
            raise LookupError("Data quality issue not found")
        if issue.version != expected_version:
            raise DataQualityError("Data quality issue changed; refresh before retrying")
        if issue.status not in ACTIVE_ISSUE_STATUSES:
            raise DataQualityError("Data quality issue is already closed")
        normalized_notes = (notes or "").strip() or None
        previous = issue.status
        now = datetime.now(UTC)
        details: dict[str, Any] = {}
        if action == "assign":
            if owner_user_id is None:
                raise DataQualityError("Issue assignment requires an owner")
            owner = self.session.scalar(
                select(User).where(
                    User.tenant_id == self.tenant_id,
                    User.id == owner_user_id,
                    User.active.is_(True),
                    User.role.in_([UserRole.ADMIN, UserRole.ANALYST]),
                )
            )
            if owner is None:
                raise DataQualityError("Issue owner must be an active tenant administrator or analyst")
            issue.owner_user_id = owner.id
            details["owner_user_id"] = owner.id
        elif action == "acknowledge":
            if issue.status != "open":
                raise DataQualityError("Only open issues can be acknowledged")
            if issue.owner_user_id is None:
                raise DataQualityError("Assign an owner before acknowledging the issue")
            issue.status = "acknowledged"
            issue.acknowledged_at = now
        elif action == "resolve":
            if issue.status != "ready_to_resolve":
                raise DataQualityError("Issue metrics must recover before resolution")
            if normalized_notes is None:
                raise DataQualityError("Issue resolution requires notes")
            issue.status = "resolved"
            issue.resolved_at = now
            issue.resolution_notes = normalized_notes
            issue.active_key = None
        else:
            if normalized_notes is None:
                raise DataQualityError("Issue waiver requires notes")
            issue.status = "waived"
            issue.resolved_at = now
            issue.resolution_notes = normalized_notes
            issue.active_key = None
        issue.version += 1
        self._event(issue, action, "user", actor_id, previous, details | {"notes": normalized_notes})
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type="user",
                actor_id=actor_id,
                action=f"quality.issue.{action}",
                resource_type="data_quality_issue",
                resource_id=issue.id,
                outcome="success",
                request_id=request_id,
                details={"previous_status": previous, "resulting_status": issue.status, **details},
            )
        )
        self.session.commit()
        return issue

    def _measure(
        self,
        window_start: datetime,
        measured_at: datetime,
        previous: DataQualitySnapshot | None,
    ) -> dict[str, dict[str, Any]]:
        rules = self._rules()
        active_assets = (
            SourceAsset.tenant_id == self.tenant_id,
            SourceAsset.state == SourceAssetState.ACTIVE,
            SourceAsset.processing_mode == "parse",
            DataSource.tenant_id == self.tenant_id,
            DataSource.state == DataSourceState.ACTIVE,
        )
        asset_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(SourceAsset)
                .join(DataSource, DataSource.id == SourceAsset.data_source_id)
                .where(*active_assets)
            )
            or 0
        )
        complete_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(SourceAsset)
                .join(DataSource, DataSource.id == SourceAsset.data_source_id)
                .join(SourceVersion, SourceVersion.id == SourceAsset.current_version_id)
                .where(
                    *active_assets,
                    SourceVersion.parse_status == StageStatus.SUCCEEDED,
                    SourceVersion.source_document_id.is_not(None),
                )
            )
            or 0
        )
        distinct_hashes = int(
            self.session.scalar(
                select(func.count(distinct(SourceVersion.content_sha256)))
                .select_from(SourceAsset)
                .join(DataSource, DataSource.id == SourceAsset.data_source_id)
                .join(SourceVersion, SourceVersion.id == SourceAsset.current_version_id)
                .where(*active_assets)
            )
            or 0
        )
        current_version_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(SourceAsset)
                .join(DataSource, DataSource.id == SourceAsset.data_source_id)
                .join(SourceVersion, SourceVersion.id == SourceAsset.current_version_id)
                .where(*active_assets)
            )
            or 0
        )
        published_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(StagedFact)
                .where(
                    StagedFact.tenant_id == self.tenant_id,
                    StagedFact.status == GovernanceStatus.PUBLISHED,
                )
            )
            or 0
        )
        cited_count = int(
            self.session.scalar(
                select(func.count(distinct(StagedFact.id)))
                .select_from(StagedFact)
                .join(FactProvenanceLink, FactProvenanceLink.staged_fact_id == StagedFact.id)
                .where(
                    StagedFact.tenant_id == self.tenant_id,
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    StagedFact.status == GovernanceStatus.PUBLISHED,
                )
            )
            or 0
        )
        sources = list(
            self.session.scalars(
                select(DataSource).where(
                    DataSource.tenant_id == self.tenant_id,
                    DataSource.state == DataSourceState.ACTIVE,
                )
            )
        )
        fresh_count = sum(
            source.last_success_at is not None
            and self._aware(source.last_success_at)
            >= measured_at - timedelta(seconds=source.expected_freshness_seconds)
            for source in sources
        )
        terminal_states = [RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELED, RunState.PARTIAL]
        run_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(IngestionRun)
                .where(
                    IngestionRun.tenant_id == self.tenant_id,
                    IngestionRun.created_at >= window_start,
                    IngestionRun.state.in_(terminal_states),
                )
            )
            or 0
        )
        successful_runs = int(
            self.session.scalar(
                select(func.count())
                .select_from(IngestionRun)
                .where(
                    IngestionRun.tenant_id == self.tenant_id,
                    IngestionRun.created_at >= window_start,
                    IngestionRun.state == RunState.SUCCEEDED,
                )
            )
            or 0
        )
        values = {
            "completeness": (complete_count, asset_count, self._ratio(complete_count, asset_count)),
            "duplicate_rate": (
                current_version_count - distinct_hashes,
                current_version_count,
                self._ratio(current_version_count - distinct_hashes, current_version_count),
            ),
            "citation_coverage": (cited_count, published_count, self._ratio(cited_count, published_count)),
            "freshness_coverage": (fresh_count, len(sources), self._ratio(fresh_count, len(sources))),
            "ingestion_success": (successful_runs, run_count, self._ratio(successful_runs, run_count)),
        }
        metrics = {
            key: self._metric(rule, numerator, denominator, value)
            for key, (numerator, denominator, value) in values.items()
            for rule in [rules[key]]
        }
        previous_values = {
            key: float(metric.get("value", 0))
            for key, metric in (previous.metrics if previous else {}).items()
            if key in values and isinstance(metric, dict) and metric.get("applicable") is True
        }
        comparable = [abs(values[key][2] - previous_values[key]) for key in values if key in previous_values]
        drift_value = max(comparable, default=0.0)
        metrics["drift"] = self._metric(
            rules["drift"],
            int(round(drift_value * 10_000)),
            10_000 if comparable else 0,
            drift_value,
        )
        return metrics

    def _rules(self) -> dict[str, QualityRule]:
        return {
            "completeness": QualityRule(
                "completeness", "解析完整率", "gte", self.settings.data_quality_completeness_min, "high"
            ),
            "duplicate_rate": QualityRule(
                "duplicate_rate", "重复率", "lte", self.settings.data_quality_duplicate_rate_max, "medium"
            ),
            "citation_coverage": QualityRule(
                "citation_coverage", "引用覆盖率", "gte", self.settings.data_quality_citation_coverage_min, "high"
            ),
            "freshness_coverage": QualityRule(
                "freshness_coverage",
                "来源新鲜度覆盖",
                "gte",
                self.settings.data_quality_freshness_coverage_min,
                "medium",
            ),
            "ingestion_success": QualityRule(
                "ingestion_success", "入库成功率", "gte", self.settings.data_quality_ingestion_success_min, "high"
            ),
            "drift": QualityRule("drift", "指标漂移", "lte", self.settings.data_quality_drift_max, "medium"),
        }

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _metric(rule: QualityRule, numerator: int, denominator: int, value: float) -> dict[str, Any]:
        applicable = denominator > 0
        passed = value >= rule.threshold if rule.comparison == "gte" else value <= rule.threshold
        return {
            "label": rule.label,
            "value": round(value, 6),
            "numerator": numerator,
            "denominator": denominator,
            "applicable": applicable,
            "threshold": rule.threshold,
            "comparison": rule.comparison,
            "status": "not_applicable" if not applicable else "passed" if passed else "failed",
            "severity": rule.severity,
        }

    def _reconcile_issues(self, snapshot: DataQualitySnapshot, actor_type: str, actor_id: str) -> None:
        for metric_key, metric in snapshot.metrics.items():
            active_key = f"global:{metric_key}"
            issue = self.session.scalar(
                select(DataQualityIssue).where(
                    DataQualityIssue.tenant_id == self.tenant_id,
                    DataQualityIssue.active_key == active_key,
                )
            )
            failed = metric["status"] == "failed"
            if failed and issue is None:
                issue = DataQualityIssue(
                    tenant_id=self.tenant_id,
                    active_key=active_key,
                    metric_key=metric_key,
                    scope_type="tenant",
                    status="open",
                    severity=str(metric["severity"]),
                    title=f"{metric['label']}未达到质量阈值",
                    description=self._description(metric),
                    actual_value=float(metric["value"]),
                    threshold_value=float(metric["threshold"]),
                    comparison=str(metric["comparison"]),
                    sla_due_at=snapshot.measured_at + timedelta(hours=self.settings.data_quality_issue_sla_hours),
                    detected_at=snapshot.measured_at,
                    version=1,
                    last_snapshot_id=snapshot.id,
                )
                self.session.add(issue)
                self.session.flush()
                self._event(issue, "opened", actor_type, actor_id, None, {"snapshot_id": snapshot.id})
                continue
            if issue is None:
                continue
            previous = issue.status
            issue.actual_value = float(metric["value"])
            issue.threshold_value = float(metric["threshold"])
            issue.last_snapshot_id = snapshot.id
            issue.description = self._description(metric)
            issue.version += 1
            if failed and issue.status == "ready_to_resolve":
                issue.status = "open"
                self._event(issue, "regressed", actor_type, actor_id, previous, {"snapshot_id": snapshot.id})
            elif not failed and metric["status"] == "passed" and issue.status in {"open", "acknowledged"}:
                issue.status = "ready_to_resolve"
                self._event(issue, "recovered", actor_type, actor_id, previous, {"snapshot_id": snapshot.id})

    @staticmethod
    def _description(metric: dict[str, Any]) -> str:
        relation = "至少" if metric["comparison"] == "gte" else "至多"
        return (
            f"当前值 {float(metric['value']):.2%}，要求{relation} {float(metric['threshold']):.2%}；"
            f"样本 {metric['numerator']}/{metric['denominator']}。"
        )

    def _event(
        self,
        issue: DataQualityIssue,
        action: str,
        actor_type: str,
        actor_id: str,
        previous_status: str | None,
        details: dict[str, Any],
    ) -> None:
        self.session.add(
            DataQualityIssueEvent(
                tenant_id=self.tenant_id,
                issue_id=issue.id,
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                previous_status=previous_status,
                resulting_status=issue.status,
                details=details,
            )
        )

    def _issue(self, issue_id: str) -> DataQualityIssue:
        issue = self.session.scalar(
            select(DataQualityIssue).where(
                DataQualityIssue.tenant_id == self.tenant_id,
                DataQualityIssue.id == issue_id,
            )
        )
        if issue is None:
            raise LookupError("Data quality issue not found")
        return issue
