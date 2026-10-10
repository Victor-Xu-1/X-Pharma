import { createTranslator } from "./translator";
export const accountInvitationMessages = {
  有效: "Active",
  已使用: "Used",
  已撤销: "Revoked",
  已过期: "Expired",
  "邀请操作失败，请稍后重试": "Could not complete the invitation. Try again later.",
  邀请码已复制: "Invitation code copied",
  "无法写入剪贴板，请选中邀请码手动复制": "Clipboard access failed. Select and copy the invitation code manually.",
  新生成的注册邀请码: "New registration invitation code",
  注册邀请码: "Registration invitation code",
  关闭邀请码: "Close invitation code",
  "绑定邮箱：": "Bound email: ",
  "有效期至：": "Expires at: ",
  一次性邀请码: "One-time invitation code",
  "邀请码仅显示这一次。请私下交给绑定邮箱的用户；注册后立即失效。":
    "This code is shown only once. Share it privately with its bound email owner; it expires after registration.",
  复制邀请码: "Copy invitation code",
  完成: "Done",
  "当前使用企业身份系统，请在组织身份系统创建账号并绑定已有企业身份。":
    "This organization uses enterprise identity. Create the account in its identity service and link an existing organization identity.",
  注册邀请码管理: "Registration invitation management",
  内部账号注册邀请: "Internal registration invitations",
  "只有管理员可以发放邀请码。新账号以内部分析员身份加入当前企业，不自动获得管理员权限；已有邮箱账号不自动迁移企业。":
    "Only administrators issue invitation codes. New accounts join this organization as internal analysts, not administrators. Existing email accounts are not automatically moved between organizations.",
  受邀邮箱: "Invited email",
  有效小时: "Validity (hours)",
  "生成中…": "Issuing…",
  "正在提交邀请操作…": "Submitting invitation operation…",
  生成注册邀请码: "Issue registration invitation",
  正在读取注册邀请: "Loading registration invitations",
  注册邀请读取失败: "Could not load registration invitations",
  注册邀请记录滚动区域: "Scrollable registration invitations",
  注册邀请记录: "Registration invitations",
  邮箱: "Email",
  状态: "Status",
  有效期: "Expires at",
  操作: "Actions",
  撤销邀请: "Revoke invitation",
  暂无注册邀请: "No registration invitations",
  "生成邀请码后，受邀用户可在内部工作台的注册入口设置自己的密码。":
    "After a code is issued, the invited user can set their password through internal workbench registration.",
} as const;
export type AccountInvitationMessageKey = keyof typeof accountInvitationMessages;
export const accountInvitationText = createTranslator(accountInvitationMessages);
