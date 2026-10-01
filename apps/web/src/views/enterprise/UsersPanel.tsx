import { KeyRound, Plus, ShieldCheck, UserRoundCog } from "lucide-react";
import { useState } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import type { EnterpriseOperation, EnterpriseUser } from "../../lib/contracts/enterprise";
import type { AuthMode } from "../../lib/contracts/session";
import type { UserRole } from "../../lib/types";
import { ModalShell } from "./ModalShell";
import type { UserAction } from "./types";

export const roleLabels: Record<UserRole, string> = { admin: "管理员", analyst: "分析师", viewer: "浏览者" };

export function UsersPanel({
  users,
  currentUserId,
  busy,
  onCreate,
  onAction,
}: {
  users: EnterpriseUser[];
  currentUserId: string;
  busy: string;
  onCreate: () => void;
  onAction: (action: UserAction) => void;
}) {
  return (
    <>
      <div className="section-toolbar">
        <span>{users.length} 个企业账户</span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          新建用户
        </button>
      </div>
      <div className="table-frame enterprise-table">
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>角色</th>
              <th>状态</th>
              <th>身份源</th>
              <th>最近登录</th>
              <th aria-label="操作" />
            </tr>
          </thead>
          <tbody>
            {users.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.display_name}</strong>
                  <span className="cell-subtitle">{item.email}</span>
                </td>
                <td>{roleLabels[item.role]}</td>
                <td>
                  <StatusBadge value={item.active ? "active" : "disabled"} />
                </td>
                <td>{item.oidc_issuer ? "OIDC" : "本地账户"}</td>
                <td>{formatDate(item.last_login_at, true)}</td>
                <td>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      type="button"
                      title="调整角色"
                      aria-label={`调整 ${item.display_name} 的角色`}
                      onClick={() => onAction({ user: item, kind: "role" })}
                      disabled={item.id === currentUserId || Boolean(busy)}
                    >
                      <UserRoundCog size={16} />
                    </button>
                    <button
                      className="icon-button"
                      type="button"
                      title={item.active ? "停用账户" : "启用账户"}
                      aria-label={`${item.active ? "停用" : "启用"} ${item.display_name}`}
                      onClick={() => onAction({ user: item, kind: "status" })}
                      disabled={item.id === currentUserId || Boolean(busy)}
                    >
                      <KeyRound size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function CreateUserModal({
  authMode,
  busy,
  close,
  submit,
}: {
  authMode: AuthMode;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [password, setPassword] = useState("");
  const [issuer, setIssuer] = useState("");
  const [subject, setSubject] = useState("");
  return (
    <ModalShell title="新建企业用户" close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit({
            kind: "create-user",
            requestBody: {
              email: email.trim(),
              display_name: displayName.trim(),
              role,
              initial_password: authMode === "local" ? password : null,
              oidc_issuer: authMode === "oidc" ? issuer.trim() : null,
              oidc_subject: authMode === "oidc" ? subject.trim() : null,
            },
          });
        }}
      >
        <label>
          邮箱
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          显示名称
          <input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
        </label>
        <label>
          企业角色
          <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
            <option value="viewer">浏览者</option>
            <option value="analyst">分析师</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        {authMode === "local" ? (
          <label>
            初始密码
            <input
              type="password"
              minLength={12}
              maxLength={200}
              required
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
        ) : (
          <>
            <label>
              OIDC Issuer
              <input type="url" required value={issuer} onChange={(event) => setIssuer(event.target.value)} />
            </label>
            <label>
              OIDC Subject
              <input required value={subject} onChange={(event) => setSubject(event.target.value)} />
            </label>
          </>
        )}
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            <ShieldCheck size={16} />
            创建用户
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

export function UserActionModal({
  action,
  busy,
  close,
  submit,
}: {
  action: UserAction;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [role, setRole] = useState<UserRole>(action.user.role);
  const [reason, setReason] = useState("");
  const title = action.kind === "role" ? "调整用户角色" : action.user.active ? "停用企业用户" : "启用企业用户";
  return (
    <ModalShell title={title} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const operation: EnterpriseOperation =
            action.kind === "role"
              ? {
                  kind: "update-user-role",
                  userId: action.user.id,
                  requestBody: { expected_token_version: action.user.token_version, role, reason: reason.trim() },
                }
              : {
                  kind: "update-user-status",
                  userId: action.user.id,
                  requestBody: {
                    expected_token_version: action.user.token_version,
                    active: !action.user.active,
                    reason: reason.trim(),
                  },
                };
          void submit(operation);
        }}
      >
        <p className="enterprise-modal-subject">
          {action.user.display_name}
          <span>{action.user.email}</span>
        </p>
        {action.kind === "role" ? (
          <label>
            新角色
            <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
              <option value="viewer">浏览者</option>
              <option value="analyst">分析师</option>
              <option value="admin">管理员</option>
            </select>
          </label>
        ) : null}
        <label>
          变更原因
          <textarea
            required
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            取消
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={busy || (action.kind === "role" && role === action.user.role)}
          >
            确认变更
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
