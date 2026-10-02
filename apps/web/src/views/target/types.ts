import type { EntityType } from "../../lib/generated";

export type TargetEntityOpener = (entityType: EntityType, entityId: string) => void;
