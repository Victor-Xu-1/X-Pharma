import { contractRequest } from "../contract";
import { type EnvironmentPlanCreate, EnvironmentService } from "../generated";

export const environmentKeys = { root: ["environment"] as const, snapshot: ["environment", "snapshot"] as const };
export function loadEnvironment(signal?: AbortSignal) {
  return contractRequest(EnvironmentService.readEnvironmentApiV1EnterpriseEnvironmentGet(), signal);
}
export function prepareEnvironmentPlan(requestBody: EnvironmentPlanCreate) {
  return contractRequest(
    EnvironmentService.prepareEnvironmentInstallationApiV1EnterpriseEnvironmentPlansPost({ requestBody }),
  );
}
