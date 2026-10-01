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
  await expect(page.getByRole("navigation", { name: "主导航" })).toBeAttached();
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

test("[multi-organization][organization-isolation][session-context] joins an existing identity only after consent and switches without sharing private research", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "A disposable local administrator fixture is required");
  if (!credentials) return;
  const password = randomBytes(32).toString("base64url");
  const email = `account-browser-member-${randomUUID()}@example.test`;
  await page.goto("/workspace/research");
  await register(page, email, password);
  await login(page, email, password);
  const original = await (await page.request.get("/api/v1/auth/me")).json();
  const ownOrganizations = await (await page.request.get("/api/v1/auth/organizations")).json();
  expect(ownOrganizations).toHaveLength(1);
  const privateName = `Private research ${randomUUID()}`;
  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_csrf")?.value;
  const collection = await page.request.post("/api/v1/comparison-sets", {
    headers: { "X-CSRF-Token": csrf ?? "" },
    data: { name: privateName },
  });
  expect(collection.status()).toBe(201);
  await logout(page, "research");

  await page.goto("/workspace/internal");
  await login(page, credentials.email, credentials.password);
  const administrator = await (await page.request.get("/api/v1/auth/me")).json();
  await openNavigation(page);
  await page.getByRole("button", { name: "企业管理", exact: true }).click();
  await page.getByRole("tab", { name: "注册邀请", exact: true }).click();
  await page.getByLabel("受邀邮箱").fill(email);
  await page.getByRole("button", { name: "生成注册邀请码" }).click();
  const issued = page.getByRole("dialog", { name: "新生成的注册邀请码" });
  const code = await issued.getByLabel("一次性邀请码").inputValue();
  await issued.getByRole("button", { name: "完成", exact: true }).click();
  await logout(page, "internal");

  await page.goto("/workspace/research");
  await login(page, email, password);
  expect(await (await page.request.get("/api/v1/auth/organizations")).json()).toHaveLength(1);
  await openNavigation(page);
  await page.getByRole("button", { name: "组织与账号", exact: true }).click();
  const organizations = page.getByRole("dialog", { name: "组织与账号", exact: true });
  await organizations.getByLabel("管理员邀请码").fill(code);
  const accept = organizations.getByRole("button", { name: "确认加入组织" });
  await expect(accept).toBeDisabled();
  await organizations.getByRole("checkbox").check();
  const joined = page.waitForResponse((response) => response.url().endsWith("/api/v1/auth/organizations/join"));
  await accept.click();
  expect((await joined).status()).toBe(201);
  await expect(organizations.getByText("已加入组织，请从上方选择切换。")).toBeVisible();
  const otherTab = await page.context().newPage();
  await otherTab.goto("/workspace/research?view=collections");
  await expect(
    otherTab.getByRole("button").filter({ has: otherTab.getByText(privateName, { exact: true }) }),
  ).toBeVisible();
  const previousCookie = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_session")?.value;
  await organizations.getByRole("button", { name: "切换到 Disposable account acceptance", exact: true }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索", exact: true })).toBeVisible();
  const selected = await (await page.request.get("/api/v1/auth/me")).json();
  expect(selected).toMatchObject({ id: original.id, tenant_id: administrator.tenant_id, role: "analyst" });
  await expect(otherTab.getByRole("heading", { name: "全局情报检索", exact: true })).toBeVisible();
  await expect(otherTab.getByText(privateName)).toHaveCount(0);
  expect(await (await otherTab.request.get("/api/v1/auth/me")).json()).toMatchObject({
    tenant_id: administrator.tenant_id,
  });
  expect(
    (await page.request.get("/api/v1/auth/me", { headers: { Cookie: `pharma_session=${previousCookie}` } })).status(),
  ).toBe(401);
  await page.reload();
  await expect(page.getByRole("heading", { name: "全局情报检索", exact: true })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("button", { name: "对比列表", exact: true }).click();
  await expect(page.getByRole("heading", { name: "对比列表", level: 1 })).toBeVisible();
  await expect(page.getByText(privateName)).toHaveCount(0);
  const otherCollections = await (await page.request.get("/api/v1/comparison-sets")).json();
  expect(JSON.stringify(otherCollections)).not.toContain(privateName);

  await openNavigation(page);
  await page.getByRole("button", { name: "组织与账号", exact: true }).click();
  await page
    .getByRole("dialog", { name: "组织与账号" })
    .getByRole("button", { name: `切换到 ${ownOrganizations[0].name}`, exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "全局情报检索", exact: true })).toBeVisible();
  expect(await (await page.request.get("/api/v1/auth/me")).json()).toMatchObject({
    id: original.id,
    tenant_id: original.tenant_id,
    role: "viewer",
  });
  await openNavigation(page);
  await page.getByRole("button", { name: "对比列表", exact: true }).click();
  await expect(page.getByRole("button").filter({ has: page.getByText(privateName, { exact: true }) })).toBeVisible();
  await otherTab.close();
  await logout(page, "research");
});
