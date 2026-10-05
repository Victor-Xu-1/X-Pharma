import { contractRequest } from "../contract";
import { type PublicResearchQuery, PublicResearchService } from "../generated";

export const loadPublicCoverage = (signal?: AbortSignal) =>
  contractRequest(PublicResearchService.publicCoverageApiV1PublicResearchCoverageGet(), signal);

export const searchPublicResearch = (input: PublicResearchQuery, signal?: AbortSignal) =>
  contractRequest(PublicResearchService.publicResearchApiV1PublicResearchSearchPost({ requestBody: input }), signal);

export type PublicResearchTopic = NonNullable<PublicResearchQuery["topic"]>;
