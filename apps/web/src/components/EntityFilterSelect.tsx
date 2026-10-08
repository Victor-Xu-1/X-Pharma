import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { getEntity, intelligenceKeys } from "../lib/contracts/intelligence";
import type { EntityType } from "../lib/generated";
import { useMessages } from "../lib/i18n";
import { entityFilterMessages } from "../lib/i18n/entityFilter";
import { EntityCandidateInput } from "./EntityCandidateInput";

export function EntityFilterSelect({
  label,
  entityType,
  value,
  onChange,
  onResolved,
  placeholder,
}: {
  label: string;
  entityType: EntityType | readonly EntityType[];
  value: string;
  onChange: (entityId: string, displayName?: string) => void;
  onResolved?: (entityId: string, displayName: string) => void;
  placeholder: string;
}) {
  const t = useMessages(entityFilterMessages);
  const entityTypes = useMemo(() => (typeof entityType === "string" ? [entityType] : entityType), [entityType]);
  const selected = useQuery({
    queryKey: intelligenceKeys.entity(value),
    queryFn: ({ signal }) => getEntity(value, signal),
    enabled: Boolean(value),
  });
  const invalidSelection = Boolean(
    selected.data && (selected.data.id !== value || !entityTypes.includes(selected.data.entity_type)),
  );
  const resolvedKey =
    selected.data && !selected.isError && !invalidSelection ? `${selected.data.id}:${selected.data.name}` : "";
  const emittedResolvedKey = useRef("");
  useEffect(() => {
    if (!onResolved || emittedResolvedKey.current === resolvedKey) return;
    emittedResolvedKey.current = resolvedKey;
    if (resolvedKey && selected.data) onResolved(selected.data.id, selected.data.name);
  }, [onResolved, resolvedKey, selected.data]);

  return (
    <fieldset className="entity-filter-select" aria-label={t("{label}检索与选择", { label })}>
      <span className="entity-filter-label">{label}</span>
      {value ? (
        <div className={`entity-filter-selection${invalidSelection || selected.isError ? " invalid" : ""}`}>
          <span>
            {selected.isFetching
              ? t("正在读取实体")
              : invalidSelection || selected.isError
                ? t("所选实体不可用")
                : selected.data?.name || value}
          </span>
          {selected.isError && !selected.isFetching ? (
            <button type="button" onClick={() => void selected.refetch()} aria-label={t("重试已选{label}", { label })}>
              {t("重试")}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onChange("")}
            title={t("清除{label}", { label })}
            aria-label={t("清除{label}", { label })}
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <EntityCandidateInput
          label={label}
          entityTypes={entityTypes}
          onSelect={(entity) => onChange(entity.id, entity.name)}
          placeholder={placeholder}
        />
      )}
    </fieldset>
  );
}
