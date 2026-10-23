import { entityIdentityNote } from "../lib/entityPresentation";
import { useLocale } from "../lib/i18n";
import { entityText as t } from "../lib/i18n/entity";
import type { Entity } from "../lib/types";

export function EntityIdentityNotice({ entity }: { entity: Pick<Entity, "entity_type" | "attributes"> }) {
  useLocale();
  const note = entityIdentityNote(entity);
  if (!note) return null;
  return (
    <p className="inline-feedback" role="note" aria-label={t("来源名称范围")}>
      {note}
    </p>
  );
}
