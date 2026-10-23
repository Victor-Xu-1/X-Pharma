import { entityIdentityNote, entityTypeLabel } from "../lib/entityPresentation";
import { useLocale } from "../lib/i18n";
import { entityText as t } from "../lib/i18n/entity";
import "./EntityIdentityLabel.css";

/** Identity labels and their qualifications come only from the existing presentation contract. */
export function EntityIdentityLabel({ entity }: { entity: Parameters<typeof entityTypeLabel>[0] & { name: string } }) {
  useLocale();
  const note = entityIdentityNote(entity);
  return (
    <div className="entity-identity-label">
      <span>{entityTypeLabel(entity)}</span>
      {note ? (
        <details>
          <summary aria-label={t("{name} 的身份说明", { name: entity.name })}>{t("身份说明")}</summary>
          <p>{note}</p>
        </details>
      ) : null}
    </div>
  );
}
