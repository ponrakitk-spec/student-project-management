import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const TEAM = `${API}/api/v1/teams/me`;
const ORIGIN = { Origin: "http://localhost:3000" };
const PASSWORD = "TeamUpdateBrowserFixtureA1";
let unsafe = 0;
let duplicateKeys = 0;
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  duplicateKeys = 0;
  page.on("console", (message) => { if (message.text().includes("same key")) duplicateKeys += 1; });
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); expect(duplicateKeys).toBe(0); });

async function register(page: Page) {
  const email = `team-update-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: ORIGIN,
    data: { full_name: "นักศึกษาทดสอบแก้ไขทีม", email, password: PASSWORD } });
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
async function edit(page: Page) {
  const user = await register(page); await login(page, user.email);
  const response = await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมเดิม", description: "คำอธิบายทีมเดิม" } });
  expect(response.status()).toBe(201);
  const team = (await (await page.request.get(TEAM)).json()).data;
  await page.goto("/teams");
  await page.getByRole("button", { name: "แก้ไขทีม", exact: true }).click();
  await expect(form(page)).toHaveCount(1);
  return { user, team };
}
function form(page: Page) { return page.getByRole("region", { name: "แก้ไขทีม", exact: true }); }

test("leader cancels without writes then patches only the changed field and refreshes", async ({ page }, info) => {
  const { team } = await edit(page);
  let writes = 0; let body: unknown; let csrf = false;
  page.on("request", (request) => {
    if (request.method() === "PATCH" && request.url() === TEAM) {
      writes += 1; body = request.postDataJSON(); csrf = Boolean(request.headers()["x-csrf-token"]);
    }
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ชื่อที่ยกเลิก");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมเดิม", exact: true })).toBeVisible();
  expect(writes).toBe(0);
  await page.getByRole("button", { name: "แก้ไขทีม", exact: true }).click();
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("  ทีมที่แก้ไขแล้ว  ");
  await page.screenshot({ path: info.outputPath("team-edit-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ทีมที่แก้ไขแล้ว", exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "แก้ไขทีมสำเร็จแล้ว" })).toBeVisible();
  expect(body).toEqual({ name: "ทีมที่แก้ไขแล้ว" }); expect(csrf).toBe(true); expect(writes).toBe(1);
  expect((await (await page.request.get(TEAM)).json()).data).toEqual({ ...team, name: "ทีมที่แก้ไขแล้ว" });
  await page.reload();
  await expect(page.getByRole("heading", { name: "ทีมที่แก้ไขแล้ว", exact: true })).toBeVisible();
  await expect(page.getByText("คำอธิบายทีมเดิม", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "โครงงานของทีม →", exact: true })).toBeVisible();
});

test("clear description preserves membership and member cannot edit", async ({ page }) => {
  const member = await register(page);
  const { user, team } = await edit(page);
  let body: unknown;
  page.on("request", (request) => { if (request.method() === "PATCH") body = request.postDataJSON(); });
  await page.getByLabel("คำอธิบายทีม", { exact: false }).fill("  ");
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(page.getByText("ยังไม่มีคำอธิบายทีม", { exact: true })).toBeVisible();
  expect(body).toEqual({ description: null });
  expect((await (await page.request.get(TEAM)).json()).data.membership).toEqual(team.membership);
  expect((await page.request.post(`${TEAM}/members`, { headers: await headers(page), data: { email: member.email } })).status()).toBe(201);
  await login(page, member.email); await page.reload();
  await expect(page.getByRole("heading", { name: "ทีมเดิม", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "แก้ไขทีม", exact: true })).toHaveCount(0);
  const denied = await page.request.patch(TEAM, { headers: await headers(page), data: { name: "Forbidden" } });
  expect(denied.status()).toBe(403);
  await login(page, user.email);
  expect((await (await page.request.get(TEAM)).json()).data.name).toBe("ทีมเดิม");
});

test("blank and overlong names are rejected before a write", async ({ page }) => {
  await edit(page); let writes = 0;
  page.on("request", (request) => { if (request.method() === "PATCH") writes += 1; });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("  ");
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(page.getByText("กรุณากรอกชื่อทีม", { exact: true })).toBeVisible();
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("x".repeat(256));
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(page.getByText("ชื่อทีมต้องยาวไม่เกิน 255 ตัวอักษร", { exact: true })).toBeVisible();
  expect(writes).toBe(0);
});

test("locked phase feedback keeps current metadata and never automatically retries", async ({ page }) => {
  await edit(page); let writes = 0;
  await page.route(TEAM, async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    writes += 1;
    await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "TEAM_METADATA_LOCKED" } }) });
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("Blocked");
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(form(page).getByRole("alert")).toContainText("ยังแก้ไขข้อมูลทีมในขั้นตอนนี้ไม่ได้");
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  expect((await (await page.request.get(TEAM)).json()).data.name).toBe("ทีมเดิม");
});

test("lost success response reconciles through GET and prevents another write", async ({ page }) => {
  await edit(page); let writes = 0;
  await page.route(TEAM, async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    writes += 1; const applied = await route.fetch(); expect(applied.status()).toBe(200);
    await route.abort("failed");
  });
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("Saved before disconnect");
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(form(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันผลการทำรายการได้");
  await expect(page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true })).toBeDisabled();
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "ตรวจสอบทีมอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Saved before disconnect", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});

test("real CSRF rejection and session loss never show a saved team", async ({ page }) => {
  await edit(page);
  const cookie = (await page.context().cookies(API)).find((item) => item.name === "spms_csrf")!;
  await page.context().addCookies([{ ...cookie, value: "invalid" }]);
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("Denied");
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(form(page).getByRole("alert")).toContainText("ไม่สามารถยืนยันคำขอได้");
  await expect(page.getByRole("link", { name: "เข้าสู่ระบบใหม่", exact: true })).toBeVisible();
  expect((await (await page.request.get(TEAM)).json()).data.name).toBe("ทีมเดิม");
  await page.context().clearCookies();
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  await expect(page).toHaveURL(/\/login\?reason=session$/);
});

test("mobile editing fits viewport and submits only one pending PATCH", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await edit(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel("ชื่อทีม", { exact: true }).fill("ทีมบนโทรศัพท์");
  let release!: () => void; let writes = 0;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(TEAM, async (route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    writes += 1; await gate; await route.continue();
  });
  await page.getByRole("button", { name: "บันทึกการแก้ไข", exact: true }).click();
  try {
    await expect(page.getByRole("button", { name: "กำลังบันทึก…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
    await form(page).locator("form").dispatchEvent("submit");
    await page.screenshot({ path: info.outputPath("team-edit-mobile.png"), fullPage: true });
  } finally { release(); }
  await expect(page.getByRole("heading", { name: "ทีมบนโทรศัพท์", exact: true })).toBeVisible();
  expect(writes).toBe(1);
});
