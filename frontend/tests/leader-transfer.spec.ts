import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const TEAM = `${API}/api/v1/teams/me`;
const TRANSFER = `${TEAM}/leader`;
const ORIGIN = { Origin: "http://localhost:3000" };
const PASSWORD = "LeaderTransferFixtureA1";
let unsafe = 0; let duplicateKeys = 0;
test.beforeEach(async ({ page }) => {
  unsafe = 0; duplicateKeys = 0;
  page.on("console", (message) => { if (message.text().includes("same key")) duplicateKeys += 1; });
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); expect(duplicateKeys).toBe(0); });

async function register(page: Page, name: string) {
  const email = `transfer-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: ORIGIN,
    data: { full_name: name, email, password: PASSWORD } });
  expect(response.status()).toBe(201);
  return (await response.json()).data as { id: string; email: string };
}
async function login(page: Page, email: string) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email, password: PASSWORD } })).status()).toBe(200);
}
async function headers(page: Page) {
  const csrf = (await page.context().cookies(API)).find((cookie) => cookie.name === "spms_csrf")?.value ?? "";
  return { ...ORIGIN, "X-CSRF-Token": csrf };
}
async function leader(page: Page) {
  const user = await register(page, "หัวหน้าเดิม"); await login(page, user.email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมโอนหัวหน้า" } })).status()).toBe(201);
  return user;
}
async function scenario(page: Page) {
  const user = await leader(page);
  const member = await register(page, "หัวหน้าคนใหม่");
  const response = await page.request.post(`${TEAM}/members`, { headers: await headers(page), data: { email: member.email } });
  expect(response.status()).toBe(201);
  const membership = (await response.json()).data as { id: string; user_id: string };
  await page.goto("/teams");
  await expect(page.getByLabel("สมาชิกที่จะเป็นหัวหน้าคนใหม่", { exact: true })).toBeVisible();
  return { user, member, membership };
}
function transferRegion(page: Page) { return page.getByRole("region", { name: "โอนหัวหน้าทีม", exact: true }); }
async function review(page: Page, membershipId: string) {
  await page.getByLabel("สมาชิกที่จะเป็นหัวหน้าคนใหม่", { exact: true }).selectOption(membershipId);
  await page.getByRole("button", { name: "ตรวจสอบการโอนหัวหน้า", exact: true }).click();
  await expect(page.getByRole("group", { name: "ยืนยันการโอนหัวหน้า", exact: true })).toContainText("หัวหน้าคนใหม่");
}

test("a sole leader cannot select or automatically create a transfer target", async ({ page }) => {
  await leader(page); await page.goto("/teams");
  await expect(transferRegion(page)).toContainText("ต้องมีสมาชิกอีกคนในทีมก่อน");
  await expect(page.getByLabel("สมาชิกที่จะเป็นหัวหน้าคนใหม่", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true })).toHaveCount(0);
});

test("confirmation can be cancelled then real transfer refreshes both leaders and preserves Project creator", async ({ page }, info) => {
  const { user, member, membership } = await scenario(page);
  const created = await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: "ผู้สร้างเดิม" } });
  expect(created.status()).toBe(201);
  let writes = 0; let body: unknown; let csrf = false;
  page.on("request", (request) => {
    if (request.url() === TRANSFER && request.method() === "POST") {
      writes += 1; body = request.postDataJSON(); csrf = Boolean(request.headers()["x-csrf-token"]);
    }
  });
  await review(page, membership.id); expect(writes).toBe(0);
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(page.getByRole("group", { name: "ยืนยันการโอนหัวหน้า", exact: true })).toHaveCount(0);
  expect(writes).toBe(0);
  await review(page, membership.id);
  await page.screenshot({ path: info.outputPath("leader-transfer-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "โอนหัวหน้าสำเร็จแล้ว" })).toBeVisible();
  await expect(page.getByRole("button", { name: "แก้ไขทีม", exact: true })).toHaveCount(0);
  await expect(transferRegion(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true })).toHaveCount(0);
  expect(writes).toBe(1); expect(csrf).toBe(true); expect(body).toEqual({ team_member_id: membership.id });
  expect((await (await page.request.get(TEAM)).json()).data.membership.role).toBe("member");
  await page.reload(); await expect(page.getByRole("button", { name: "แก้ไขทีม", exact: true })).toHaveCount(0);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("button", { name: "แก้ไขทีม", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "เพิ่มสมาชิก", exact: true })).toBeVisible();
  expect((await (await page.request.get(TEAM)).json()).data.membership.role).toBe("leader");
  const project = (await (await page.request.get(`${API}/api/v1/projects/me`)).json()).data;
  expect(project.created_by).toBe(user.id);
});

test("member has no transfer form and a forged leader request is rejected", async ({ page }) => {
  const { user, member, membership } = await scenario(page);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("heading", { name: "ทีมโอนหัวหน้า", exact: true })).toBeVisible();
  await expect(transferRegion(page)).toHaveCount(0);
  const response = await page.request.post(TRANSFER, { headers: { ...await headers(page), "X-User-ID": user.id, "X-Role": "leader" }, data: { team_member_id: membership.id } });
  expect(response.status()).toBe(403);
  expect((await response.json()).error.code).toBe("TEAM_LEADER_TRANSFER_FORBIDDEN");
});

test("lost transfer success requires GET reconciliation without another POST", async ({ page }) => {
  const { membership } = await scenario(page); let writes = 0;
  await page.route(TRANSFER, async (route) => {
    writes += 1; const applied = await route.fetch(); expect(applied.status()).toBe(200);
    await route.abort("failed");
  });
  await review(page, membership.id);
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  await expect(transferRegion(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันผลการทำรายการได้");
  await expect(page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true })).toBeDisabled();
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(transferRegion(page).getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(transferRegion(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "แก้ไขทีม", exact: true })).toHaveCount(0);
  expect((await (await page.request.get(TEAM)).json()).data.membership.role).toBe("member");
  expect(writes).toBe(1);
});

test("stale target feedback requires reloading membership before another attempt", async ({ page }) => {
  const { membership } = await scenario(page); let writes = 0;
  await page.route(TRANSFER, async (route) => {
    writes += 1;
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: { code: "TEAM_MEMBER_NOT_FOUND" } }) });
  });
  await review(page, membership.id);
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  await expect(transferRegion(page).getByRole("alert")).toContainText("ไม่พบสมาชิกที่เลือกในทีมของคุณ");
  await expect(page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("button", { name: "ตรวจสอบการโอนหัวหน้า", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("real CSRF rejection and session loss do not claim a successful transfer", async ({ page }) => {
  const { membership } = await scenario(page);
  const cookie = (await page.context().cookies(API)).find((item) => item.name === "spms_csrf")!;
  await page.context().addCookies([{ ...cookie, value: "invalid" }]);
  await review(page, membership.id);
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  await expect(transferRegion(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันคำขอได้");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  expect((await (await page.request.get(TEAM)).json()).data.membership.role).toBe("leader");
  await page.context().clearCookies();
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile confirmation is readable and pending transfer submits once", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { membership } = await scenario(page);
  await review(page, membership.id);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  let release!: () => void; let writes = 0;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(TRANSFER, async (route) => { writes += 1; await gate; await route.continue(); });
  await page.getByRole("button", { name: "ยืนยันโอนหัวหน้า", exact: true }).click();
  try {
    await expect(page.getByRole("button", { name: "กำลังโอนหัวหน้า…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
    await transferRegion(page).locator("form").dispatchEvent("submit");
    await page.screenshot({ path: info.outputPath("leader-transfer-mobile.png"), fullPage: true });
  } finally { release(); }
  await expect(page.getByRole("status").filter({ hasText: "โอนหัวหน้าสำเร็จแล้ว" })).toBeVisible();
  expect(writes).toBe(1);
});
