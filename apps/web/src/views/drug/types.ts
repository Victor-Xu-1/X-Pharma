import type { DrugDossier } from "../../lib/contracts/drugDossier";
import type { EntityType } from "../../lib/generated";

export type DrugEntityKind = Extract<EntityType, "target" | "disease" | "organization">;

export type DrugEntityOpener = (entityType: EntityType, entityId: string) => void;

export type DrugClinicalTrial = DrugDossier["clinical_trials"][number];

export type DrugProgram = DrugDossier["programs"][number];

export type DrugDeal = DrugDossier["deals"][number];

export type EntityLink = { id: string; name: string; kind: DrugEntityKind };

export type DrugCoverageDomain = DrugDossier["coverage"][number]["domain"];
