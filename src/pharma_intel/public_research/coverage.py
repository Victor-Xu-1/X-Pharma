from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.models import DataSource, Entity, EntityType, ReviewStatus
from pharma_intel.schemas.public_research import PublicResearchCoverage


def local_coverage(session: Session, tenant_id: str) -> PublicResearchCoverage:
    counts = {
        kind: count
        for kind, count in session.execute(
            select(Entity.entity_type, func.count())
            .where(
                Entity.tenant_id == tenant_id,
                Entity.review_status == ReviewStatus.VERIFIED,
            )
            .group_by(Entity.entity_type)
        ).all()
    }
    sources = list(
        session.scalars(
            select(DataSource.name)
            .where(
                DataSource.tenant_id == tenant_id,
                DataSource.data_classification == "public",
            )
            .order_by(DataSource.name)
            .limit(20)
        )
    )
    return PublicResearchCoverage(
        observed_at=datetime.now(UTC),
        entity_counts={kind.value: int(counts.get(kind, 0)) for kind in EntityType},
        public_source_names=sources,
        scope_note="计数为当前组织本地已审核实体，不是全球数据库覆盖量或已确认事实数。来源登记不等于同步成功。"
        "公开在线结果不自动入库、不会改成verified；断网时仍可查询已入库内容。",
    )
