import { contractRequest } from "../contract";
import { AuthenticationService, type OrganizationRead } from "../generated";

export const organizationKeys = { own: ["session", "organizations"] as const };

export function loadOrganizations(signal?: AbortSignal): Promise<OrganizationRead[]> {
  return contractRequest(AuthenticationService.listOrganizationsApiV1AuthOrganizationsGet(), signal);
}

export function switchOrganization(organizationId: string) {
  return contractRequest(
    AuthenticationService.switchOrganizationApiV1AuthOrganizationsSwitchPost({
      requestBody: { organization_id: organizationId },
    }),
  );
}

export function joinOrganization(code: string) {
  return contractRequest(
    AuthenticationService.joinOrganizationApiV1AuthOrganizationsJoinPost({
      requestBody: { invitation_code: code, confirmed: true },
    }),
  );
}

export function acceptInvitationWithCredentials(email: string, password: string, code: string) {
  return contractRequest(
    AuthenticationService.acceptInvitationWithCredentialsApiV1AuthInvitationsAcceptPost({
      requestBody: { email: email.trim(), password, invitation_code: code, confirmed: true },
    }),
  );
}

export function startOidcInvitation(code: string) {
  return contractRequest(
    AuthenticationService.startOidcInvitationApiV1AuthOidcInvitationPost({
      requestBody: { invitation_code: code, confirmed: true },
    }),
  );
}
