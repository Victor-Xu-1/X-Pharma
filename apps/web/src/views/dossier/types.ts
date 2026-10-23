import type { EntityDossier } from "../../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { EntityType } from "../../lib/generated";
export type DossierEntityOpener = (entityType: EntityType, entityId: string) => void;
export type DossierSectionProps = { data: EntityDossier; onOpen: (selection: ProvenanceSelection) => void };
