import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { AccountInvitationPanel } from "../components/AccountInvitationPanel";
import { useAccountInvitations } from "../components/accountInvitations/useAccountInvitations";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import {
  type EnterpriseApiKeySecret,
  type EnterpriseAuditFilters,
  enterpriseKeys,
  loadEnterpriseAccess,
  loadEnterpriseAudit,
  loadEnterpriseGroups,
  loadEnterpriseModels,
  loadEnterpriseOverview,
  loadEnterpriseUsers,
} from "../lib/contracts/enterprise";
import type { AuthMode } from "../lib/contracts/session";
import { useLocale } from "../lib/i18n";
import { type EnterpriseMessageKey, enterpriseWorkspaceText as t } from "../lib/i18n/enterpriseWorkspace";
import type { User } from "../lib/types";
import { AccessActionModal, AccessPanel } from "./enterprise/AccessPanel";
import { ApiKeyActionModal, ApiKeySecretModal } from "./enterprise/ApiKeys";
import { AuditPanel } from "./enterprise/AuditPanel";
import { FeatureQuery } from "./enterprise/FeatureQuery";
import { CreateGroupModal, GroupActionModal, GroupsPanel } from "./enterprise/GroupsPanel";
import { LLMProviderModal } from "./enterprise/LLMProviderModal";
import { ModalShell } from "./enterprise/ModalShell";
import { LLMProvidersPanel } from "./enterprise/ModelsPanel";
import { EnterpriseOverview } from "./enterprise/OverviewPanel";
import type { AccessAction, ApiKeyAction, EnterpriseTab, GroupAction, LLMAction, UserAction } from "./enterprise/types";
import { CreateUserModal, UserActionModal, UsersPanel } from "./enterprise/UsersPanel";
import { useEnterpriseCommands } from "./enterprise/useEnterpriseCommands";
import {
  EnterpriseOperationContext,
  useEnterpriseOperationBoundary,
} from "./enterprise/useEnterpriseOperationBoundary";
import { governanceReadDenied } from "./governance/governanceQueryState";

const enterpriseTabs: Array<ResearchTabOption<EnterpriseTab>> = [
  { key: "overview", label: "租户概况" },
  { key: "users", label: "用户与角色" },
  { key: "invites", label: "注册邀请" },
  { key: "groups", label: "用户组" },
  { key: "access", label: "访问与生命周期" },
  { key: "models", label: "模型设置" },
  { key: "audit", label: "审计日志" },
];

export function EnterpriseView({ user, authMode }: { user: User; authMode: AuthMode }) {
  useLocale();
  const queryClient = useQueryClient();
  const boundary = useEnterpriseOperationBoundary();
  const { runOperation, runApiKeyOperation, runLlmOperation } = useEnterpriseCommands(boundary);
  const { busy, actionError } = boundary;
  const [tab, setTab] = useState<EnterpriseTab>("overview");
  const invitationWorkspace = useAccountInvitations(authMode, tab === "invites", boundary);
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [createGroupOpen, setCreateGroupOpen] = useState(false);
  const [userAction, setUserAction] = useState<UserAction | null>(null);
  const [groupAction, setGroupAction] = useState<GroupAction | null>(null);
  const [accessAction, setAccessAction] = useState<AccessAction | null>(null);
  const [apiKeyAction, setApiKeyAction] = useState<ApiKeyAction | null>(null);
  const [apiKeySecret, setApiKeySecret] = useState<EnterpriseApiKeySecret | null>(null);
  const [llmAction, setLlmAction] = useState<LLMAction | null>(null);
  const [auditFilters, setAuditFilters] = useState<EnterpriseAuditFilters>({});
  const [auditDraftAction, setAuditDraftAction] = useState("");

  const overviewQuery = useQuery({
    queryKey: enterpriseKeys.overview,
    queryFn: ({ signal }) => loadEnterpriseOverview(signal),
    enabled: tab === "overview",
  });
  const usersQuery = useQuery({
    queryKey: enterpriseKeys.users,
    queryFn: ({ signal }) => loadEnterpriseUsers(signal),
    enabled: tab === "users" || groupAction?.kind === "members",
  });
  const groupsQuery = useQuery({
    queryKey: enterpriseKeys.groups,
    queryFn: ({ signal }) => loadEnterpriseGroups(signal),
    enabled: tab === "groups",
  });
  const accessQuery = useQuery({
    queryKey: enterpriseKeys.access,
    queryFn: ({ signal }) => loadEnterpriseAccess(signal),
    enabled: tab === "access",
  });
  useEffect(() => {
    if (governanceReadDenied(accessQuery.error)) setApiKeySecret(null);
  }, [accessQuery.error]);
  const modelsQuery = useQuery({
    queryKey: enterpriseKeys.models,
    queryFn: ({ signal }) => loadEnterpriseModels(signal),
    enabled: tab === "models",
  });
  const auditQuery = useQuery({
    queryKey: enterpriseKeys.audit(auditFilters),
    queryFn: ({ signal }) => loadEnterpriseAudit(auditFilters, signal),
    enabled: tab === "audit",
  });
  const activeQuery = {
    overview: overviewQuery,
    users: usersQuery,
    groups: groupsQuery,
    access: accessQuery,
    models: modelsQuery,
    audit: auditQuery,
    invites: invitationWorkspace.invitations,
  }[tab];

  return (
    <EnterpriseOperationContext.Provider value={boundary}>
      <section className="enterprise-workbench">
        <div className="enterprise-toolbar">
          <span>{overviewQuery.data?.tenant.name ?? t("企业管理")}</span>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void queryClient.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" })}
            disabled={Boolean(busy) || activeQuery?.isFetching}
          >
            <RefreshCw size={16} />
            {t("刷新")}
          </button>
        </div>
        {actionError &&
        tab !== "invites" &&
        !(
          createUserOpen ||
          createGroupOpen ||
          userAction ||
          groupAction ||
          accessAction ||
          apiKeyAction ||
          apiKeySecret ||
          llmAction
        ) ? (
          <p className="inline-error" role="alert">
            {actionError}
          </p>
        ) : null}
        <ResearchTabList
          tabs={enterpriseTabs.map((option) => ({
            ...option,
            label: t(option.label as EnterpriseMessageKey),
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          }))}
          activeTab={tab}
          onChange={(value) => {
            if (!boundary.isLocked()) {
              boundary.clearFailure();
              setTab(value);
            }
          }}
          ariaLabel={t("企业管理视图")}
          idPrefix="enterprise"
        />

        <div id={`enterprise-panel-${tab}`} role="tabpanel" aria-labelledby={`enterprise-tab-${tab}`}>
          {tab === "invites" ? <AccountInvitationPanel workspace={invitationWorkspace} /> : null}
          {tab === "overview" ? (
            <FeatureQuery query={overviewQuery}>
              {(overview) => <EnterpriseOverview overview={overview} />}
            </FeatureQuery>
          ) : null}
          {tab === "users" ? (
            <FeatureQuery query={usersQuery}>
              {(users) => (
                <UsersPanel
                  users={users}
                  currentUserId={user.id}
                  busy={busy}
                  onCreate={() => setCreateUserOpen(true)}
                  onAction={setUserAction}
                />
              )}
            </FeatureQuery>
          ) : null}
          {tab === "groups" ? (
            <FeatureQuery query={groupsQuery}>
              {(groups) => (
                <GroupsPanel
                  groups={groups}
                  busy={busy}
                  onCreate={() => setCreateGroupOpen(true)}
                  onAction={setGroupAction}
                />
              )}
            </FeatureQuery>
          ) : null}
          {tab === "access" ? (
            <FeatureQuery query={accessQuery}>
              {(workspace) => (
                <AccessPanel
                  workspace={workspace}
                  onAction={setAccessAction}
                  onApiKeyAction={setApiKeyAction}
                  busy={busy}
                />
              )}
            </FeatureQuery>
          ) : null}
          {tab === "models" ? (
            <FeatureQuery query={modelsQuery}>
              {(providers) => (
                <LLMProvidersPanel
                  providers={providers}
                  busy={busy}
                  onCreate={() => setLlmAction({ kind: "create" })}
                  onEdit={(provider) => setLlmAction({ kind: "edit", provider })}
                  onPrimary={(provider) => setLlmAction({ kind: "primary", provider })}
                  onTest={(provider) =>
                    void runLlmOperation(
                      `llm:test:${provider.id}`,
                      { kind: "test-llm-provider", providerId: provider.id },
                      "模型连接测试失败",
                    )
                  }
                />
              )}
            </FeatureQuery>
          ) : null}
          {tab === "audit" ? (
            <AuditPanel
              filters={auditFilters}
              draftAction={auditDraftAction}
              setDraftAction={setAuditDraftAction}
              setFilters={setAuditFilters}
              page={auditQuery.error ? undefined : auditQuery.data}
              loading={auditQuery.isFetching}
              error={auditQuery.error}
              retry={() => void auditQuery.refetch()}
            />
          ) : null}
        </div>

        {createUserOpen && !governanceReadDenied(usersQuery.error) ? (
          <CreateUserModal
            authMode={authMode}
            busy={Boolean(busy)}
            close={() => setCreateUserOpen(false)}
            submit={async (operation) => {
              if (await runOperation("user:create", operation, "用户创建失败")) setCreateUserOpen(false);
            }}
          />
        ) : null}
        {userAction && !governanceReadDenied(usersQuery.error) ? (
          <UserActionModal
            action={userAction}
            busy={Boolean(busy)}
            close={() => setUserAction(null)}
            submit={async (operation) => {
              if (await runOperation(`user:${userAction.user.id}`, operation, "用户更新失败")) setUserAction(null);
            }}
          />
        ) : null}
        {createGroupOpen && !governanceReadDenied(groupsQuery.error) ? (
          <CreateGroupModal
            busy={Boolean(busy)}
            close={() => setCreateGroupOpen(false)}
            submit={async (operation) => {
              if (await runOperation("group:create", operation, "用户组创建失败")) setCreateGroupOpen(false);
            }}
          />
        ) : null}
        {groupAction && !governanceReadDenied(groupsQuery.error) && !governanceReadDenied(usersQuery.error) ? (
          groupAction.kind === "members" ? (
            <ModalShell title={t("管理用户组成员")} close={() => setGroupAction(null)}>
              <FeatureQuery query={usersQuery}>
                {(users) => (
                  <GroupActionModal
                    action={groupAction}
                    users={users}
                    busy={Boolean(busy)}
                    close={() => setGroupAction(null)}
                    embedded
                    submit={async (operation) => {
                      if (await runOperation(`group:${groupAction.group.id}`, operation, "用户组更新失败"))
                        setGroupAction(null);
                    }}
                  />
                )}
              </FeatureQuery>
            </ModalShell>
          ) : (
            <GroupActionModal
              action={groupAction}
              users={[]}
              busy={Boolean(busy)}
              close={() => setGroupAction(null)}
              submit={async (operation) => {
                if (await runOperation(`group:${groupAction.group.id}`, operation, "用户组更新失败")) {
                  setGroupAction(null);
                }
              }}
            />
          )
        ) : null}
        {accessAction && !governanceReadDenied(accessQuery.error) ? (
          <AccessActionModal
            action={accessAction}
            busy={Boolean(busy)}
            close={() => setAccessAction(null)}
            submit={async (operation) => {
              if (await runOperation(`access:${accessAction.kind}`, operation, "访问治理操作失败")) {
                setAccessAction(null);
              }
            }}
          />
        ) : null}
        {apiKeyAction && accessQuery.data && !governanceReadDenied(accessQuery.error) ? (
          <ApiKeyActionModal
            action={apiKeyAction}
            catalog={accessQuery.data.apiKeyCatalog}
            busy={Boolean(busy)}
            close={() => setApiKeyAction(null)}
            submit={async (operation) => {
              const result = await runApiKeyOperation(`api-key:${apiKeyAction.kind}`, operation, "API 密钥操作失败");
              if (result) {
                setApiKeyAction(null);
                if ("secret" in result) setApiKeySecret(result);
              }
            }}
          />
        ) : null}
        {apiKeySecret && !governanceReadDenied(accessQuery.error) ? (
          <ApiKeySecretModal item={apiKeySecret} close={() => setApiKeySecret(null)} />
        ) : null}
        {llmAction && !governanceReadDenied(modelsQuery.error) ? (
          <LLMProviderModal
            action={llmAction}
            busy={Boolean(busy)}
            close={() => setLlmAction(null)}
            submit={async (operation) => {
              if (await runLlmOperation(`llm:${llmAction.kind}`, operation, "模型设置保存失败")) {
                setLlmAction(null);
              }
            }}
          />
        ) : null}
      </section>
    </EnterpriseOperationContext.Provider>
  );
}
