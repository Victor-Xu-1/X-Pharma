import { randomBytes, randomUUID } from "node:crypto";

import { expect, type Page, test } from "@playwright/test";

import { resolveBrowserCredentials } from "../src/lib/browserAcceptanceCredentials";

// These flows display a one-time secret; never retain a trace or screenshot of it.
test.use({ trace: "off", screenshot: "off" });

async function login(page: Page, email: string, password: string) {
  await page.getByLabel("工作邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "进入工作台", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "主导航" })).toBeAttached();
}

async function openNavigation(page: Page) {
  const opener = page.getByRole("button", { name: "打开导航", exact: true });
  if (await opener.isVisible()) await opener.click();
}

async function logout(page: Page, workbench: "research" | "internal") {
  await openNavigation(page);
  await page.getByRole("button", { name: "退出账号", exact: true }).click();
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe(`/workspace/${workbench}`);
  expect(new URL(page.url()).search).toBe("");
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
  await page.reload();
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
}

async function register(page: Page, email: string, password: string, invitation?: string) {
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await page.getByLabel("用户名", { exact: true }).fill("Account browser acceptance");
  await page.getByLabel("注册邮箱").fill(email);
  await page.getByLabel("设置密码").fill(password);
  await page.getByLabel("确认密码").fill(password);
  if (invitation) await page.getByLabel("管理员邀请码").fill(invitation);
  const submitted = page.waitForResponse((response) => response.url().endsWith("/api/v1/auth/register"));
  await page.getByRole("button", { name: "创建账号", exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(201);
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  await expect(page.getByLabel("密码", { exact: true })).toHaveValue("");
  return response.json() as Promise<{ role: string; tenant_id: string }>;
}

test("[account-registration][human-session] independently registers researchers and redeems governed internal invitations", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "A disposable local administrator fixture is required");
  if (!credentials) return;
  const policy = await page.request.get("/api/v1/auth/registration-policy");
  expect(policy.status()).toBe(200);
  expect(await policy.json()).toMatchObject({ research: "independent", internal: "invitation" });
  const password = randomBytes(32).toString("base64url");
  const researcher = `account-browser-research-${randomUUID()}@example.test`;
  await page.goto("/workspace/research");
  const independent = await register(page, researcher, password);
  expect(independent.role).toBe("viewer");
  await login(page, researcher, password);
  expect((await page.request.get("/api/v1/enterprise/account-invitations")).status()).toBe(403);
  await page.reload();
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(200);
  await logout(page, "research");

  await page.goto("/workspace/internal");
  await login(page, credentials.email, credentials.password);
  const administrator = await (await page.request.get("/api/v1/auth/me")).json();
  expect(administrator.role).toBe("admin");
  await openNavigation(page);
  await page.getByRole("button", { name: "企业管理", exact: true }).click();
  await page.getByRole("tab", { name: "注册邀请", exact: true }).click();
  const employee = `account-browser-internal-${randomUUID()}@example.test`;
  await page.getByLabel("受邀邮箱").fill(employee);
  await page.getByRole("button", { name: "生成注册邀请码" }).click();
  const dialog = page.getByRole("dialog", { name: "新生成的注册邀请码" });
  await expect(dialog).toBeVisible();
  const code = await dialog.getByLabel("一次性邀请码").inputValue();
  await expect(dialog.getByLabel("一次性邀请码")).toBeFocused();
  await dialog.getByRole("button", { name: "完成", exact: true }).click();
  expect(await (await page.request.get("/api/v1/enterprise/account-invitations")).text()).not.toContain(code);
  await logout(page, "internal");
  const invited = await register(page, employee, password, code);
  expect(invited.role).toBe("analyst");
  expect(invited.tenant_id).toBe(administrator.tenant_id);
  expect(invited.tenant_id).not.toBe(independent.tenant_id);
  await login(page, employee, password);
  await expect(page.getByRole("button", { name: "数据工厂", exact: true })).toBeAttached();
  expect((await page.request.get("/api/v1/enterprise/account-invitations")).status()).toBe(403);
  await page.reload();
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(200);
  await logout(page, "internal");
});
