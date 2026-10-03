import { ArrowRight, X } from "lucide-react";
import { createPortal } from "react-dom";
import type { IntelligenceEntity } from "../lib/contracts/intelligence";
import { entityLabels, matchExplanation, publicIdentifiers } from "../lib/entityPresentation";
import { publicEntityAttributeLabels, publicEntityAttributes } from "../lib/publicEntity";
import type { Entity } from "../lib/types";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";

function readableAttribute(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function EntityPreviewDrawer({
  active,
  entity,
  invalidId,
  loading,
  error,
  onClose,
  onOpenEntity,
  onOpenTargetPipeline,
}: {
  active: boolean;
  entity: IntelligenceEntity | Entity | null;
  invalidId: boolean;
  loading: boolean;
  error: string;
  onClose: () => void;
  onOpenEntity: (entity: Entity) => void;
  onOpenTargetPipeline?: (entityId: string) => void;
}) {
  const drawerRef = useModalFocus<HTMLElement>(active, onClose);
  if (!active) return null;
  const identifiers = entity ? publicIdentifiers(entity) : [];
  const attributes = entity ? publicEntityAttributes(entity).slice(0, 12) : [];
  const explanation = entity ? matchExplanation(entity) : null;
  return createPortal(
    <div className="drawer-scrim" role="presentation">
      <aside
        ref={drawerRef}
        className="entity-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="entity-detail-title"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <span>{entity ? (entityLabels[entity.entity_type] ?? entity.entity_type) : "基础查询"}</span>
            <h2 id="entity-detail-title">{entity?.name ?? "实体详情"}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            aria-label="关闭实体详情"
            data-modal-autofocus="true"
          >
            <X size={19} />
          </button>
        </header>
        {invalidId || error ? (
          <ErrorState message={invalidId ? "实体标识无效，无法打开快速详情" : error} />
        ) : loading && !entity ? (
          <Spinner label="正在加载实体详情" />
        ) : entity ? (
          <>
            <div className="entity-governance-line">
              <span>更新于 {formatDate(entity.updated_at)}</span>
            </div>
            {explanation ? <p className="entity-match-detail">{explanation}</p> : null}
            <section>
              <h3>实体摘要</h3>
              <p>{entity.description || "暂无摘要"}</p>
            </section>
            <section>
              <h3>外部数据库标识</h3>
              <dl>
                {identifiers.map(([key, value]) => (
                  <div className="entity-detail-row" key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
                {!identifiers.length ? (
                  <div className="entity-detail-row">
                    <dd>暂无外部标识</dd>
                  </div>
                ) : null}
              </dl>
            </section>
            <section>
              <h3>补充信息</h3>
              <dl>
                {attributes.map(([key, value]) => (
                  <div className="entity-detail-row" key={key}>
                    <dt>{publicEntityAttributeLabels[key] ?? key}</dt>
                    <dd>{readableAttribute(value)}</dd>
                  </div>
                ))}
                {!attributes.length ? (
                  <div className="entity-detail-row">
                    <dd>暂无补充信息</dd>
                  </div>
                ) : null}
              </dl>
            </section>
            <footer>
              {entity.entity_type === "target" && onOpenTargetPipeline ? (
                <>
                  <button className="primary-button" type="button" onClick={() => onOpenTargetPipeline(entity.id)}>
                    查看研发项目
                    <ArrowRight size={16} />
                  </button>
                  <button className="secondary-button" type="button" onClick={() => onOpenEntity(entity)}>
                    打开靶点全景
                  </button>
                </>
              ) : (
                <button className="primary-button" type="button" onClick={() => onOpenEntity(entity)}>
                  {entity.entity_type === "target" ? "打开靶点全景" : "打开领域档案"}
                  <ArrowRight size={16} />
                </button>
              )}
            </footer>
          </>
        ) : (
          <EmptyState title="实体不存在或当前无权访问" />
        )}
      </aside>
    </div>,
    document.body,
  );
}
