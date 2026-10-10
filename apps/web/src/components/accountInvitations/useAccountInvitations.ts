import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { ApiError } from "../../lib/api";
import { accountInvitations, issueAccountInvitation, revokeAccountInvitation } from "../../lib/contracts/accounts";
import type { AuthMode } from "../../lib/contracts/session";
import type { InvitationIssued } from "../../lib/generated";
import type {
  EnterpriseFailure,
  EnterpriseOperationBoundary,
} from "../../views/enterprise/useEnterpriseOperationBoundary";

const key = ["enterprise", "account-invitations"] as const;
const readDenied = (error: unknown) => error instanceof ApiError && [401, 403].includes(error.status);
function invitationFailure(error: unknown): EnterpriseFailure {
  return error instanceof ApiError && [403, 409].includes(error.status)
    ? { raw: error.message }
    : { key: "邀请操作失败，请稍后重试" };
}

/** The mounted workspace owns the draft; the active invitation panel alone may issue/display a code. */
export function useAccountInvitations(authMode: AuthMode, active: boolean, boundary: EnterpriseOperationBoundary) {
  const client = useQueryClient();
  const mounted = useRef(true),
    activePanel = useRef(active);
  activePanel.current = active;
  const [email, setEmail] = useState("");
  const [validHours, setValidHours] = useState(24);
  const [issued, setIssued] = useState<InvitationIssued | null>(null);
  const invitations = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => accountInvitations(signal),
    enabled: active && authMode === "local",
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!active || authMode !== "local" || readDenied(invitations.error)) setIssued(null);
  }, [active, authMode, invitations.error]);
  const readReady = invitations.isSuccess && !invitations.error && !invitations.isFetching;
  function ready() {
    if (boundary.isLocked() || !mounted.current || !activePanel.current || authMode !== "local") return false;
    const state = client.getQueryState(key);
    if (state?.status !== "success" || state.error || state.fetchStatus === "fetching") {
      boundary.failCurrentRead();
      return false;
    }
    return true;
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !ready() ||
      !event.currentTarget.checkValidity() ||
      !Number.isInteger(validHours) ||
      validHours < 1 ||
      validHours > 168
    )
      return;
    const payload = { email: email.trim(), valid_hours: validHours };
    const result = await boundary.run(
      "invitation:issue",
      () => issueAccountInvitation(payload),
      "邀请操作失败，请稍后重试",
      invitationFailure,
    );
    if (result && mounted.current && activePanel.current && !readDenied(client.getQueryState(key)?.error))
      setIssued(result.value);
  }
  async function revoke(invitationId: string) {
    if (!ready() || !invitations.data?.some((item) => item.id === invitationId && item.status === "active")) return;
    await boundary.run(
      `invitation:revoke:${invitationId}`,
      () => revokeAccountInvitation(invitationId),
      "邀请操作失败，请稍后重试",
      invitationFailure,
    );
  }
  return {
    authMode,
    invitations,
    email,
    setEmail,
    validHours,
    setValidHours,
    issued,
    closeSecret: () => setIssued(null),
    readReady,
    pending: Boolean(boundary.busy),
    issuing: boundary.busy === "invitation:issue",
    actionError: boundary.actionError,
    submit,
    revoke,
  };
}
export type AccountInvitationWorkspace = ReturnType<typeof useAccountInvitations>;
