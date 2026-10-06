import { entityIdentityNote } from "../lib/entityPresentation";
import type { Entity } from "../lib/types";

export function EntityIdentityNotice({ entity }: { entity: Pick<Entity, "entity_type" | "attributes"> }) {
  const note = entityIdentityNote(entity);
  if (!note) return null;
  return (
    <p className="inline-feedback" role="note" aria-label="来源名称范围">
      {note}
    </p>
  );
}
