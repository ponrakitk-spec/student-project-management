import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8001";
const ROOT = `${API}/api/v1/coordinator/projects`;
const ORIGIN = { Origin: "http://localhost:3000" };
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e for rollback-only committee fixtures");
const projectName = (label: string) => `โครงงานกรรมการ ${tag!.slice(0, 6)} ${label}`;
const advisorName = (label: string) => `อาจารย์ทดสอบ ${label.toUpperCase()} ${tag!.slice(0, 6)}`;
let unsafe = 0;
async function login(page: Page, label = "coordinator") {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN,
    data: { email: `advisor-browser-${tag}-${label}@example.test`, password: "AdvisorBrowserFixtureA1" } })).status()).toBe(200);
}
async function headers(page: Page) {
  return { ...ORIGIN, "X-CSRF-Token": (await page.context().cookies(API)).find((row) => row.name === "spms_csrf")?.value ?? "" };
}
async function project(page: Page, label = "eligible") {
  const response = await page.request.get(ROOT);
  expect(response.status()).toBe(200);
  const row = (await response.json()).data.find((item: { name: string }) => item.name === projectName(label));
  expect(row).toBeTruthy();
  return row as { id: string; name: string };
}
async function clean(page: Page) {
  await login(page);
  const target = await project(page);
  const data = (await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data;
  for (const row of data.assignments) {
    expect((await page.request.post(`${ROOT}/${target.id}/committee/${row.id}/remove`, { headers: await headers(page), data: {} })).status()).toBe(204);
  }
}
async function open(page: Page, label = "eligible") {
  const row = await project(page, label);
  await page.goto(`/coordinator/projects/${row.id}/committee`);
  await expect(page.getByRole("heading", { name: row.name, exact: true })).toBeVisible();
  return row;
}
async function add(page: Page, label = "b") {
  await page.getByLabel("เลือกอาจารย์เป็นกรรมการ", { exact: true }).selectOption({ label: advisorName(label) });
  await page.getByRole("button", { name: "เพิ่มกรรมการ", exact: true }).click();
  await expect(page.getByRole("heading", { name: advisorName(label), exact: true })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
  await clean(page);
});
test.afterEach(async ({ page }) => { await clean(page); expect(unsafe).toBe(0); });

test("coordinator lists eligible projects and adds replaces cancels removes with real API", async ({ page }, info) => {
  await page.goto("/");
  await page.getByRole("link", { name: "จัดการกรรมการโครงงาน →", exact: true }).click();
  await expect(page.getByRole("heading", { name: projectName("eligible"), exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: projectName("locked"), exact: true })).toBeVisible();
  await expect(page.getByText(projectName("hidden"), { exact: true })).toHaveCount(0);
  const target = await open(page);
  await expect(page.getByLabel("เลือกอาจารย์เป็นกรรมการ").getByRole("option", { name: advisorName("a"), exact: true })).toHaveCount(0);
  await add(page);
  const initial = (await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data.assignments[0];
  await page.reload();
  const card = page.getByTestId(`committee-${initial.id}`);
  await card.getByLabel(`เลือกอาจารย์แทน ${advisorName("b")}`, { exact: true }).selectOption({ label: advisorName("c") });
  await card.getByRole("button", { name: "เปลี่ยนกรรมการ", exact: true }).click();
  const confirm = page.getByRole("region", { name: "ยืนยันการเปลี่ยนรายชื่อ", exact: true });
  await confirm.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  expect((await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data.assignments[0].advisor.id).toBe(initial.advisor.id);
  await card.getByRole("button", { name: "เปลี่ยนกรรมการ", exact: true }).click();
  await page.screenshot({ path: info.outputPath("committee-replace-desktop.png"), fullPage: true });
  await confirm.getByRole("button", { name: "ยืนยันเปลี่ยนกรรมการ", exact: true }).click();
  await expect(card.getByRole("heading", { name: advisorName("c"), exact: true })).toBeVisible();
  const changed = (await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data.assignments[0];
  expect(changed.id).toBe(initial.id); expect(changed.assigned_at).toBe(initial.assigned_at);
  await card.getByRole("button", { name: "ถอดกรรมการ", exact: true }).click();
  await confirm.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "ถอดกรรมการ", exact: true }).click();
  await confirm.getByRole("button", { name: "ยืนยันถอดกรรมการ", exact: true }).click();
  await expect(page.getByText("ยังไม่มีกรรมการ", { exact: true })).toBeVisible();
});

test("first vote locks the real roster and API refuses mutation", async ({ page }) => {
  const target = await open(page, "locked");
  await expect(page.getByText("รายชื่อกรรมการล็อกแล้วหลังเริ่มลงมติ", { exact: true })).toBeVisible();
  await expect(page.getByRole("list", { name: "รายชื่อกรรมการ", exact: true }).getByRole("listitem")).toHaveCount(3);
  await expect(page.getByRole("button", { name: /เพิ่มกรรมการ|เปลี่ยนกรรมการ|ถอดกรรมการ/ })).toHaveCount(0);
  const options = (await (await page.request.get(`${ROOT}/${target.id}/committee-candidates`)).json()).data;
  const response = await page.request.post(`${ROOT}/${target.id}/committee`, { headers: await headers(page), data: { advisor_id: options[0].id } });
  expect(response.status()).toBe(409); expect((await response.json()).error.code).toBe("COMMITTEE_ROSTER_LOCKED");
});

test("anonymous and advisor users cannot enter coordinator UI or read its API", async ({ page }) => {
  await page.context().clearCookies(); await page.goto("/coordinator/projects");
  await expect(page).toHaveURL(/\/login\?reason=session$/);
  await login(page, "a"); await page.goto("/coordinator/projects");
  await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", exact: true })).toBeVisible();
  expect((await page.request.get(ROOT)).status()).toBe(403);
});

test("lost add response reconciles through GET without automatic retry", async ({ page }) => {
  const target = await open(page);
  let posts = 0;
  await page.route(`${ROOT}/${target.id}/committee`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    expect((await route.fetch()).status()).toBe(201);
    await route.abort();
  });
  await page.getByLabel("เลือกอาจารย์เป็นกรรมการ", { exact: true }).selectOption({ label: advisorName("b") });
  await page.getByRole("button", { name: "เพิ่มกรรมการ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ยังยืนยันผลไม่ได้" })).toBeVisible();
  await expect(page.getByRole("button", { name: "เพิ่มกรรมการ", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: advisorName("b"), exact: true })).toBeVisible();
  expect(posts).toBe(1);
});

test("unexpected remove success status preserves error recovery even after cancel", async ({ page }) => {
  const target = await open(page); await add(page);
  const row = (await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data.assignments[0];
  await page.route(`${ROOT}/${target.id}/committee/${row.id}/remove`, (route) => route.fulfill({ status: 200, json: {} }));
  await page.getByRole("button", { name: "ถอดกรรมการ", exact: true }).click();
  await page.getByRole("button", { name: "ยืนยันถอดกรรมการ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ข้อมูลตอบกลับไม่ถูกต้อง" })).toBeVisible();
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByTestId(`committee-${row.id}`)).toBeVisible();
});

test("malformed and failed project reads do not fabricate an empty list", async ({ page }) => {
  for (const response of [{ status: 200, json: { data: {} } }, { status: 500, json: { error: { code: "INTERNAL_ERROR" } } }]) {
    await page.route(ROOT, (route) => route.fulfill(response));
    await page.goto("/coordinator/projects");
    await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
    await expect(page.getByText("ยังไม่มีโครงงานที่มีหัวข้อผ่านการอนุมัติจากอาจารย์", { exact: true })).toHaveCount(0);
    await page.unroute(ROOT);
  }
});

test("stale editable UI receives real roster locked conflict and reloads readonly", async ({ page }) => {
  const target = await project(page, "locked");
  let stale = true;
  await page.route(`${ROOT}/${target.id}/committee`, async (route) => {
    if (route.request().method() === "POST") { stale = false; return route.continue(); }
    const response = await route.fetch(); const json = await response.json();
    if (stale) json.data.roster_locked = false;
    await route.fulfill({ response, json });
  });
  await open(page, "locked");
  await page.getByLabel("เลือกอาจารย์เป็นกรรมการ", { exact: true }).selectOption({ label: advisorName("e") });
  await page.getByRole("button", { name: "เพิ่มกรรมการ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "รายชื่อกรรมการล็อกแล้ว" })).toBeVisible();
  await expect(page.getByRole("button", { name: "เพิ่มกรรมการ", exact: true })).toHaveCount(0);
});

test("mobile pending removal submits once and confirmation fits", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const target = await open(page); await add(page);
  const row = (await (await page.request.get(`${ROOT}/${target.id}/committee`)).json()).data.assignments[0];
  let requests = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`${ROOT}/${target.id}/committee/${row.id}/remove`, async (route) => {
    requests += 1; await gate; await route.continue();
  });
  await page.getByRole("button", { name: "ถอดกรรมการ", exact: true }).click();
  const confirm = page.getByRole("region", { name: "ยืนยันการเปลี่ยนรายชื่อ", exact: true });
  await page.screenshot({ path: info.outputPath("committee-remove-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await confirm.getByRole("button", { name: "ยืนยันถอดกรรมการ", exact: true }).click();
  await expect(confirm.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
  await confirm.getByRole("button", { name: "กำลังบันทึก…", exact: true }).evaluate((element: HTMLButtonElement) => { element.click(); element.click(); });
  expect(requests).toBe(1); release();
  await expect(page.getByText("ยังไม่มีกรรมการ", { exact: true })).toBeVisible();
});
