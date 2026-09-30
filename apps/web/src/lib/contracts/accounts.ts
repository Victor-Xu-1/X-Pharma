import { contractRequest } from "../contract";
import { AuthenticationService, type InvitationCreate, type RegistrationRequest } from "../generated";

export function registrationPolicy(signal?: AbortSignal) {
  return contractRequest(AuthenticationService.registrationPolicyApiV1AuthRegistrationPolicyGet(), signal);
}

export function registerAccount(payload: RegistrationRequest) {
  return contractRequest(AuthenticationService.registerAccountApiV1AuthRegisterPost({ requestBody: payload }));
}

export function accountInvitations(signal?: AbortSignal) {
  return contractRequest(AuthenticationService.listAccountInvitationsApiV1EnterpriseAccountInvitationsGet(), signal);
}

export function issueAccountInvitation(payload: InvitationCreate) {
  return contractRequest(
    AuthenticationService.createAccountInvitationApiV1EnterpriseAccountInvitationsPost({ requestBody: payload }),
  );
}

export function revokeAccountInvitation(invitationId: string) {
  return contractRequest(
    AuthenticationService.revokeAccountInvitationApiV1EnterpriseAccountInvitationsInvitationIdDelete({ invitationId }),
  );
}
