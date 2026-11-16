import { test, expect, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
const API = "http://localhost:8001"; const ROOT = `${API}/api/v1/projects/me/milestones`; const PASSWORD = "MilestoneUiFixtureA1";
const alerts = (page: Page) => page.getByRole("region", { name: "แผนงานโครงงาน", exact: true }).getByRole("alert");
async function headers(page: Page) { return { Origin: "http://localhost:3000", "X-CSRF-Token": (await page.context().cookies(API)).find(c => c.name === "spms_csrf")?.value ?? "" }; }
async function login(page: Page, email: string) { expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: await headers(page), data: { email, password: PASSWORD } })).status()).toBe(200); }
async function register(page: Page) { const email = `milestone-ui-${randomUUID()}@example.test`; expect((await page.request.post(`${API}/api/v1/auth/register`, { headers: await headers(page), data: { full_name: "นักศึกษาทดสอบแผนงาน", email, password: PASSWORD } })).status()).toBe(201); return email; }
async function setup(page: Page, member = false) {
  const email = await register(page); await login(page, email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมแผนงาน" } })).status()).toBe(201);
  expect((await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: "โครงงานแผนงาน" } })).status()).toBe(201);
  const other = member ? await register(page) : null;
  if (other) expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: other } })).status()).toBe(201);
  return { email, other };
}
async function create(page: Page, name = "แผนงานทดสอบ") {
  await page.getByRole("button", { name: "สร้างแผนงาน", exact: true }).click(); await page.getByLabel("ชื่อแผนงาน", { exact: true }).fill(name);
  await page.getByLabel("วันกำหนดส่ง", { exact: true }).fill("2099-12-31"); await page.getByRole("button", { name: "บันทึกแผนงาน", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("สร้างแผนงานแล้ว"); return (await (await page.request.get(ROOT)).json()).data.milestones[0] as { id: string };
}
test("leader creates edits cancels and confirms deletion while preserving Project", async ({ page }) => {
  await setup(page); await page.goto("/projects"); await page.getByRole("link", { name: "แผนงานโครงงาน →", exact: true }).click(); const row = await create(page);
  await page.reload(); const card = page.getByTestId(`milestone-${row.id}`); await expect(card).toContainText("ยังไม่เริ่ม");
  await card.getByRole("button", { name: "แก้ไขแผนงาน", exact: true }).click(); await page.getByLabel("คำอธิบายแผนงาน (ไม่บังคับ)", { exact: true }).fill("รายละเอียดใหม่");
  let patch: unknown; page.on("request", r => { if (r.url() === `${API}/api/v1/milestones/${row.id}` && r.method() === "PATCH") patch = r.postDataJSON(); });
  await page.getByRole("button", { name: "บันทึกแผนงาน", exact: true }).click(); await expect(card).toContainText("รายละเอียดใหม่"); expect(patch).toEqual({ description: "รายละเอียดใหม่" });
  await card.getByRole("button", { name: "ลบแผนงาน", exact: true }).click(); await card.getByRole("button", { name: "ยกเลิก", exact: true }).click(); await expect(card).toBeVisible();
  await card.getByRole("button", { name: "ลบแผนงาน", exact: true }).click(); await card.getByRole("button", { name: "ยืนยันลบแผนงาน", exact: true }).click();
  await expect(card).toHaveCount(0); expect((await page.request.get(`${API}/api/v1/projects/me`)).status()).toBe(200);
});
test("members read without controls and client validates before writes", async ({ page }) => {
  const owner = await setup(page, true); await page.goto("/projects/milestones"); await page.getByRole("button", { name: "สร้างแผนงาน", exact: true }).click();
  await page.getByRole("button", { name: "บันทึกแผนงาน", exact: true }).click(); await expect(alerts(page)).toContainText("1–255");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click(); const row = await create(page);
  await login(page, owner.other!); await page.goto("/projects/milestones"); await expect(page.getByTestId(`milestone-${row.id}`)).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างแผนงาน", exact: true })).toHaveCount(0); await expect(page.getByRole("button", { name: "แก้ไขแผนงาน", exact: true })).toHaveCount(0);
});
test("lost real create response requires GET reconciliation and never repeats POST", async ({ page }) => {
  await setup(page); let writes = 0; await page.route(ROOT, async route => { if (route.request().method() !== "POST") return route.continue(); writes++; expect((await route.fetch()).status()).toBe(201); await route.abort(); });
  await page.goto("/projects/milestones"); await page.getByRole("button", { name: "สร้างแผนงาน", exact: true }).click(); await page.getByLabel("ชื่อแผนงาน", { exact: true }).fill("ผลตอบกลับหาย"); await page.getByLabel("วันกำหนดส่ง", { exact: true }).fill("2099-12-31");
  await page.getByRole("button", { name: "บันทึกแผนงาน", exact: true }).click(); await expect(alerts(page)).toContainText("โหลดรายการ");
  await expect(page.getByRole("button", { name: "บันทึกแผนงาน", exact: true })).toBeDisabled(); await page.getByRole("button", { name: "โหลดรายการอีกครั้ง", exact: true }).click();
  await expect(page.locator('[data-testid^="milestone-"]')).toHaveCount(1); expect(writes).toBe(1);
});
test("task conflict and unexpected DELETE success do not claim removal", async ({ page }) => {
  await setup(page); await page.goto("/projects/milestones"); const row = await create(page); const card = page.getByTestId(`milestone-${row.id}`);
  const endpoint = `${API}/api/v1/milestones/${row.id}`;
  await page.route(endpoint, route => route.fulfill({ status: 409, json: { error: { code: "MILESTONE_HAS_TASKS" } } }));
  await card.getByRole("button", { name: "ลบแผนงาน", exact: true }).click(); await card.getByRole("button", { name: "ยืนยันลบแผนงาน", exact: true }).click(); await expect(alerts(page)).toContainText("มีงานย่อย");
  await page.getByRole("button", { name: "โหลดรายการอีกครั้ง", exact: true }).click(); await page.unroute(endpoint);
  await page.route(endpoint, route => route.fulfill({ status: 200, json: { data: null } }));
  await card.getByRole("button", { name: "ลบแผนงาน", exact: true }).click(); await card.getByRole("button", { name: "ยืนยันลบแผนงาน", exact: true }).click();
  await expect(alerts(page)).toBeVisible(); await expect(card).toBeVisible(); expect((await page.request.get(endpoint)).status()).toBe(200);
});
test("failed or mismatched list never enables creation", async ({ page }) => {
  await setup(page); await page.route(ROOT, route => route.fulfill({ status: 200, json: { data: { project_id: "9223372036854775807", can_manage: true, milestones: [] } } }));
  await page.goto("/projects/milestones"); await expect(page.getByRole("heading", { name: "ยังโหลดแผนงานไม่ได้" })).toBeVisible(); await expect(page.getByRole("button", { name: "สร้างแผนงาน", exact: true })).toHaveCount(0);
  await page.unroute(ROOT); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click(); await expect(page.getByRole("button", { name: "สร้างแผนงาน", exact: true })).toBeVisible();
});
test("mobile form and confirmation fit and submit only once while pending", async ({ page }) => {
  await setup(page); await page.setViewportSize({ width: 390, height: 844 }); let writes = 0; let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(ROOT, async route => { if (route.request().method() !== "POST") return route.continue(); writes++; await gate; await route.continue(); });
  await page.goto("/projects/milestones"); await page.getByRole("button", { name: "สร้างแผนงาน", exact: true }).click(); await page.getByLabel("ชื่อแผนงาน", { exact: true }).fill("แผนงานมือถือ"); await page.getByLabel("วันกำหนดส่ง", { exact: true }).fill("2099-12-31");
  await page.getByRole("button", { name: "บันทึกแผนงาน", exact: true }).click();
  try { await expect(page.getByRole("button", { name: "กำลังบันทึก…", exact: true })).toBeDisabled(); expect(writes).toBe(1); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); } finally { release(); }
  await expect(page.getByRole("status")).toContainText("สร้างแผนงานแล้ว"); expect(writes).toBe(1);
});
