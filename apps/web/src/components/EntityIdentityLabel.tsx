import { entityIdentityNote, entityTypeLabel } from "../lib/entityPresentation";
import "./EntityIdentityLabel.css";

/** Identity labels and their qualifications come only from the existing presentation contract. */
export function EntityIdentityLabel({ entity }: { entity: Parameters<typeof entityTypeLabel>[0] & { name: string } }) {
  const note = entityIdentityNote(entity);
  return (
    <div className="entity-identity-label">
      <span>{entityTypeLabel(entity)}</span>
      {note ? (
        <details>
          <summary aria-label={`${entity.name} 的身份说明`}>身份说明</summary>
          <p>{note}</p>
        </details>
      ) : null}
    </div>
  );
}
