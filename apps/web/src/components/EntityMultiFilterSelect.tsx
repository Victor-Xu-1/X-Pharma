import { useQueries } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { getEntity, intelligenceKeys } from "../lib/contracts/intelligence";
import type { EntityType } from "../lib/generated";
import { useMessages } from "../lib/i18n";
import { entityFilterMessages } from "../lib/i18n/entityFilter";
import { EntityCandidateInput } from "./EntityCandidateInput";

export function EntityMultiFilterSelect({
  label,
  entityType,
  values,
  onChange,
  onResolved,
  placeholder,
  maxSelections = 20,
}: {
  label: string;
  entityType: EntityType;
  values: string[];
  onChange: (entityIds: string[], selectedId?: string, selectedName?: string) => void;
  onResolved?: (entityId: string, displayName: string) => void;
  placeholder: string;
  maxSelections?: number;
}) {
  const t = useMessages(entityFilterMessages);
  const selectedQueries = useQueries({
    queries: values.map((entityId) => ({
      queryKey: intelligenceKeys.entity(entityId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getEntity(entityId, signal),
    })),
  });
  const resolvedSelections = useMemo(
    () =>
      selectedQueries.flatMap((selected, index) =>
        selected.data &&
        !selected.isError &&
        selected.data.id === values[index] &&
        selected.data.entity_type === entityType
          ? [{ id: selected.data.id, name: selected.data.name }]
          : [],
      ),
    [entityType, selectedQueries, values],
  );
  const resolvedKey = resolvedSelections.map((item) => `${item.id}:${item.name}`).join("|");
  const emittedResolvedKey = useRef("");
  useEffect(() => {
    if (!onResolved || emittedResolvedKey.current === resolvedKey) return;
    emittedResolvedKey.current = resolvedKey;
    for (const item of resolvedSelections) onResolved(item.id, item.name);
  }, [onResolved, resolvedKey, resolvedSelections]);

  return (
    <fieldset className="entity-filter-select entity-multi-filter-select" aria-label={t("{label}多选", { label })}>
      <span className="entity-filter-label">
        {label}
        {values.length ? (
          <small>
            {values.length}/{maxSelections}
          </small>
        ) : null}
      </span>
      {values.length ? (
        <fieldset className="entity-multi-filter-selections" aria-label={t("已选{label}", { label })}>
          {values.map((entityId, index) => {
            const selected = selectedQueries[index];
            const invalid = Boolean(
              selected?.isError ||
                (selected?.data && (selected.data.id !== entityId || selected.data.entity_type !== entityType)),
            );
            return (
              <span className={`entity-filter-selection${invalid ? " invalid" : ""}`} key={entityId}>
                <span>
                  {selected?.isFetching
                    ? t("正在读取实体")
                    : invalid
                      ? t("所选实体不可用")
                      : selected?.data?.name || entityId}
                </span>
                {selected?.isError && !selected.isFetching ? (
                  <button
                    type="button"
                    onClick={() => void selected.refetch()}
                    aria-label={t("重试已选{label} {id}", { label, id: entityId })}
                  >
                    {t("重试")}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => onChange(values.filter((value) => value !== entityId))}
                  title={t("移除{name}", { name: selected?.data?.name ?? entityId })}
                  aria-label={t("移除{name}", { name: selected?.data?.name ?? entityId })}
                >
                  <X size={14} />
                </button>
              </span>
            );
          })}
        </fieldset>
      ) : null}
      {values.length < maxSelections ? (
        <EntityCandidateInput
          label={label}
          entityTypes={[entityType]}
          excludedIds={values}
          onSelect={(entity) => onChange([...values, entity.id], entity.id, entity.name)}
          placeholder={placeholder}
          multiple
        />
      ) : (
        <span className="entity-filter-limit" role="status">
          {t("已达到最多 {count} 项", { count: maxSelections })}
        </span>
      )}
    </fieldset>
  );
}
