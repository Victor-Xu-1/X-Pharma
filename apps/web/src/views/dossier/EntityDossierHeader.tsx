import { Network } from "lucide-react";
import { formatDate } from "../../components/common";
import { EntityNames } from "../../components/EntityNames";
import type { EntityDossier } from "../../lib/contracts/entityDossier";
import { entityTypeLabel } from "../../lib/entityPresentation";
import { useMessages } from "../../lib/i18n";
import { dossierRecordMessages } from "../../lib/i18n/dossierRecords";
import "./EntityDossierHeader.css";

/** Presentation only: retain the complete identity and server coverage facts. */
export function EntityDossierHeader({
  data,
}: {
  data: Pick<EntityDossier, "entity" | "coverage" | "relationships" | "as_of">;
}) {
  const text = useMessages(dossierRecordMessages);
  const totalRecords = data.coverage.reduce((sum, item) => sum + item.total, 0);
  const availableDomains = data.coverage.filter((item) => item.total > 0).length;
  return (
    <>
      <header className="entity-dossier-title">
        <div className="entity-dossier-symbol">
          <Network size={23} aria-hidden="true" />
        </div>
        <div>
          <span>{entityTypeLabel(data.entity)}</span>
          <h2>{data.entity.name}</h2>
          <p>{data.entity.description ?? text("暂无实体摘要")}</p>
        </div>
      </header>
      <EntityNames entity={data.entity} />
      <dl className="dossier-metrics entity-dossier-metrics">
        <div>
          <dt>{text("关联记录")}</dt>
          <dd>{totalRecords}</dd>
        </div>
        <div>
          <dt>{text("有数据领域")}</dt>
          <dd>
            {availableDomains} / {data.coverage.length}
          </dd>
        </div>
        <div>
          <dt>{text("直接关系")}</dt>
          <dd>{data.relationships.length}</dd>
        </div>
        <div>
          <dt>{text("查询时间")}</dt>
          <dd title={text("本次档案查询时间不代表所有来源的最后更新时间")}>{formatDate(data.as_of, true)}</dd>
        </div>
      </dl>
    </>
  );
}
