import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const TEAM = `${API}/api/v1/teams/me`;
const LEAVE = `${TEAM}/leave`;
const PASSWORD = "MembershipExitFixtureA1";
const ORIGIN = { Origin: "http://localhost:3000" };
const MEMBER_NAME = "สมาชิกทดสอบออกทีม";
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
  const email = `exit-${randomUUID()}@example.test`;
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
async function scenario(page: Page, mode: "leave" | "remove") {
  const leader = await register(page, "หัวหน้าทดสอบออกทีม"); await login(page, leader.email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมทดสอบออกสมาชิก" } })).status()).toBe(201);
  const member = await register(page, MEMBER_NAME);
  const added = await page.request.post(`${TEAM}/members`, { headers: await headers(page), data: { email: member.email } });
  expect(added.status()).toBe(201);
  const membership = (await added.json()).data as { id: string };
  expect((await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: "โครงงานคงเดิมหลังออกทีม" } })).status()).toBe(201);
  if (mode === "leave") await login(page, member.email);
  await page.goto("/teams");
  return { leader, member, membership, url: mode === "leave" ? LEAVE : `${TEAM}/members/${membership.id}/remove` };
}
async function confirm(page: Page, mode: "leave" | "remove", membership: { id: string }) {
  if (mode === "leave") await page.getByRole("button", { name: "ออกจากทีม", exact: true }).click();
  else await page.getByRole("button", { name: `ถอด ${MEMBER_NAME} (สมาชิก #${membership.id})`, exact: true }).click();
}
function confirmation(page: Page, mode: "leave" | "remove") { return page.getByRole("group", { name: mode === "leave" ? "ยืนยันการออกจากทีม" : "ยืนยันการถอดสมาชิก", exact: true }); }
function submit(page: Page, mode: "leave" | "remove") { return page.getByRole("button", { name: mode === "leave" ? "ยืนยันออกจากทีม" : "ยืนยันถอดสมาชิก", exact: true }); }

test("member cancels then really leaves with 204, remains logged in and loses Project access", async ({ page }, info) => {
  const { membership } = await scenario(page, "leave"); let writes = 0; let payload: unknown; let csrf = false;
  page.on("request", (request) => { if (request.url() === LEAVE && request.method() === "POST") { writes += 1; payload = request.postDataJSON(); csrf = Boolean(request.headers()["x-csrf-token"]); } });
  await confirm(page, "leave", membership);
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click(); expect(writes).toBe(0);
  await confirm(page, "leave", membership);
  await page.screenshot({ path: info.outputPath("membership-leave-desktop.png"), fullPage: true });
  const responsePromise = page.waitForResponse((response) => response.url() === LEAVE && response.request().method() === "POST");
  await submit(page, "leave").click();
  expect((await responsePromise).status()).toBe(204);
  await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "ออกจากทีมสำเร็จแล้ว" })).toBeVisible();
  expect((await page.request.get(`${API}/api/v1/auth/me`)).status()).toBe(200);
  expect((await page.request.get(`${API}/api/v1/projects/me`)).status()).toBe(404);
  expect((await page.request.get(`${TEAM}/members`)).status()).toBe(404);
  expect(writes).toBe(1); expect(payload).toEqual({}); expect(csrf).toBe(true);
  await page.reload(); await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toBeVisible();
});

test("leader removes member, refreshes list and revoked member session stays authenticated", async ({ page, browser }) => {
  const { member, membership, url } = await scenario(page, "remove");
  const removedContext = await browser.newContext();
  try {
    expect((await removedContext.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email: member.email, password: PASSWORD } })).status()).toBe(200);
    await confirm(page, "remove", membership);
    await expect(confirmation(page, "remove")).toContainText(MEMBER_NAME);
    const responsePromise = page.waitForResponse((response) => response.url() === url && response.request().method() === "POST");
    await submit(page, "remove").click(); expect((await responsePromise).status()).toBe(204);
    await expect(page.getByRole("status").filter({ hasText: "ถอดสมาชิกสำเร็จแล้ว" })).toBeVisible();
    await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" })).toBeVisible();
    await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" }).getByText(MEMBER_NAME, { exact: true })).toHaveCount(0);
    expect((await removedContext.request.get(`${API}/api/v1/auth/me`)).status()).toBe(200);
    expect((await removedContext.request.get(TEAM)).status()).toBe(404);
    expect((await removedContext.request.get(`${API}/api/v1/projects/me`)).status()).toBe(404);
    expect((await page.request.get(`${API}/api/v1/projects/me`)).status()).toBe(200);
  } finally { await removedContext.close(); }
});

test("leader must transfer before leaving and member cannot use removal endpoint", async ({ page }) => {
  const { member, url } = await scenario(page, "remove");
  await expect(page.getByText("โอนตำแหน่งหัวหน้าก่อน", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ออกจากทีม", exact: true })).toHaveCount(0);
  expect((await page.request.post(LEAVE, { headers: await headers(page), data: {} })).status()).toBe(409);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("button", { name: /^ถอด / })).toHaveCount(0);
  expect((await page.request.post(url, { headers: await headers(page), data: {} })).status()).toBe(403);
  await expect(page.getByRole("button", { name: "ออกจากทีม", exact: true })).toBeVisible();
});

for (const mode of ["leave", "remove"] as const) {
  test(`${mode} C-02 conflict keeps membership and exposes no Task details`, async ({ page }) => {
    const { membership, url } = await scenario(page, mode); let writes = 0;
    await page.route(url, async (route) => { writes += 1; await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "MEMBER_EXIT_BLOCKED_BY_TASK" } }) }); });
    await confirm(page, mode, membership); await submit(page, mode).click();
    await expect(page.getByRole("alert").filter({ hasText: "มีงานที่กำลังทำ" })).toBeVisible();
    expect((await page.request.get(TEAM)).status()).toBe(200); expect(writes).toBe(1);
    await expect(confirmation(page, mode)).toBeVisible();
  });

  test(`${mode} lost response reconciles with GET instead of retrying`, async ({ page }) => {
    const { membership, url } = await scenario(page, mode); let writes = 0;
    await page.route(url, async (route) => { writes += 1; const response = await route.fetch(); expect(response.status()).toBe(204); await route.abort("failed"); });
    await confirm(page, mode, membership); await submit(page, mode).click();
    await expect(page.getByRole("alert").filter({ hasText: "ไม่สามารถยืนยันผลการทำรายการได้" })).toBeVisible();
    await expect(submit(page, mode)).toBeDisabled();
    await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
    await expect(page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
    if (mode === "leave") await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toBeVisible();
    else {
      await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" })).toBeVisible();
      await expect(page.getByRole("list", { name: "รายชื่อสมาชิกทีม" }).getByText(MEMBER_NAME, { exact: true })).toHaveCount(0);
    }
    expect(writes).toBe(1);
  });
}

test("unexpected success and failed reconciliation never pretend membership is gone", async ({ page }) => {
  const { membership } = await scenario(page, "leave");
  await page.route(LEAVE, (route) => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
  await confirm(page, "leave", membership); await submit(page, "leave").click();
  await expect(page.getByRole("alert").filter({ hasText: "กรุณาตรวจสอบทีมอีกครั้ง" })).toBeVisible();
  await expect(submit(page, "leave")).toBeDisabled();
  await page.route(TEAM, (route) => route.abort("failed"));
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลทีมไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "สร้างทีมของคุณ", exact: true })).toHaveCount(0);
});

test("real CSRF denial and session loss do not report successful leave", async ({ page }) => {
  const { membership } = await scenario(page, "leave");
  const cookie = (await page.context().cookies(API)).find((item) => item.name === "spms_csrf")!;
  await page.context().addCookies([{ ...cookie, value: "invalid" }]);
  await confirm(page, "leave", membership); await submit(page, "leave").click();
  await expect(page.getByRole("alert").filter({ hasText: "ไม่สามารถยืนยันคำขอได้" })).toBeVisible();
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  expect((await page.request.get(TEAM)).status()).toBe(200);
  await page.context().clearCookies(); await submit(page, "leave").click();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile removal confirmation is readable and pending action submits once", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { membership, url } = await scenario(page, "remove"); await confirm(page, "remove", membership);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  let release!: () => void; let writes = 0;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(url, async (route) => { writes += 1; await gate; await route.continue(); });
  await submit(page, "remove").click();
  try {
    const pending = page.getByRole("button", { name: "กำลังดำเนินการ…", exact: true });
    await expect(pending).toBeDisabled(); await expect(page.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
    await pending.dispatchEvent("click");
    await page.screenshot({ path: info.outputPath("membership-remove-mobile.png"), fullPage: true });
  } finally { release(); }
  await expect(page.getByRole("status").filter({ hasText: "ถอดสมาชิกสำเร็จแล้ว" })).toBeVisible();
  expect(writes).toBe(1);
});
