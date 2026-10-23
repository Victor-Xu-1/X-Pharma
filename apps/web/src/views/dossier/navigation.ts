import type { EntityType } from "../../lib/generated";
import type { DossierEntityOpener } from "./types";
export function openDossierEntity(
  fallback: (entityId: string) => void,
  typed: DossierEntityOpener | undefined,
  entityType: EntityType,
  entityId: string,
) {
  if (typed) {
    typed(entityType, entityId);
    return;
  }
  fallback(entityId);
}
