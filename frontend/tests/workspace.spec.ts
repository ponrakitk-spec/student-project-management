import { expect, test, type Page, type Route } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = "http://localhost:8001";
const TEAM = `${API}/api/v1/teams/me`;
const PROJECT = `${API}/api/v1/projects/me`;
const ME = `${API}/api/v1/auth/me`;
const ORIGIN = { Origin: "http://localhost:3000" };
const PASSWORD = "WorkspaceBrowserFixtureA1";
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e for rollback-only workspace tests");
let unsafe = 0;
async function student(page: Page, name = "นักศึกษาพื้นที่ทำงาน") {
  const email = `workspace-browser-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: ORIGIN, data: { full_name: name, email, password: PASSWORD } });
  expect(response.status()).toBe(201);
  return { email, name };
}
async function login(page: Page, email: string, password = PASSWORD) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN, data: { email, password } })).status()).toBe(200);
}
async function headers(page: Page) {
  return { ...ORIGIN, "X-CSRF-Token": (await page.context().cookies(API)).find((row) => row.name === "spms_csrf")?.value ?? "" };
}
async function setup(page: Page, { project = false, member = false } = {}) {
  const leader = await student(page, "หัวหน้าพื้นที่ทำงาน");
  const other = member ? await student(page, "สมาชิกพื้นที่ทำงาน") : null;
  await login(page, leader.email);
  const teamName = `ทีมพื้นที่ทำงาน ${randomUUID()}`;
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: teamName, description: "ทีมสำหรับทดสอบหน้าภาพรวม" } })).status()).toBe(201);
  if (other) expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: other.email } })).status()).toBe(201);
  const projectName = `โครงงานพื้นที่ทำงาน ${randomUUID()}`;
  if (project) expect((await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: projectName, description: "คำอธิบายโครงงาน\nข้อมูลที่อ่านจากระบบจริง" } })).status()).toBe(201);
  return { leader, other, teamName, projectName };
}
async function open(page: Page) {
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "พื้นที่ทำงาน", exact: true })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); });

test("anonymous is protected and an authenticated student without team enters from account", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login\?reason=session$/);
  const user = await student(page); await login(page, user.email); await page.goto("/");
  await expect(page.getByRole("heading", { name: `สวัสดี, ${user.name}`, exact: true })).toBeVisible();
  let projectReads = 0;
  page.on("request", (request) => { if (request.url() === PROJECT) projectReads += 1; });
  await page.getByRole("link", { name: "พื้นที่ทำงาน →", exact: true }).click();
  await expect(page.getByRole("heading", { name: "คุณยังไม่มีทีม", exact: true })).toBeVisible();
  expect(projectReads).toBe(0);
  await expect(page.getByRole("link", { name: "ไปสร้างโครงงาน →", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "เริ่มสร้างทีม →", exact: true }).click();
  await expect(page).toHaveURL(/\/teams$/);
});

test("leader with no Project sees the real Team and navigates to existing Project form", async ({ page }) => {
  const data = await setup(page); await open(page);
  await expect(page.getByRole("heading", { name: data.teamName, exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "ทีมของฉัน", exact: true }).getByText("หัวหน้าทีม", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ยังไม่มีโครงงานของทีม", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "ไปสร้างโครงงาน →", exact: true }).click();
  await expect(page.getByRole("heading", { name: "สร้างโครงงานของทีม", exact: true })).toBeVisible();
});

test("member waits for leader then refresh reads the newly created Project", async ({ page }) => {
  const data = await setup(page, { member: true }); await login(page, data.other!.email); await open(page);
  await expect(page.getByText("สมาชิกทีม", { exact: true })).toBeVisible();
  await expect(page.getByText("หัวหน้าทีมเป็นผู้สร้างโครงงาน", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "ไปสร้างโครงงาน →", exact: true })).toHaveCount(0);
  await login(page, data.leader.email);
  expect((await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: data.projectName } })).status()).toBe(201);
  await login(page, data.other!.email); await page.reload();
  await expect(page.getByRole("heading", { name: data.projectName, exact: true })).toBeVisible();
  await expect(page.getByText("สมาชิกทีม", { exact: true })).toBeVisible();
});

test("real Project overview is read-only, keyboard accessible and fits desktop and mobile", async ({ page }, info) => {
  const data = await setup(page, { project: true });
  let writes = 0;
  page.on("request", (request) => { if (request.url().startsWith(`${API}/api/v1/`) && !["GET", "OPTIONS"].includes(request.method())) writes += 1; });
  await open(page);
  await expect(page.getByRole("heading", { name: data.projectName, exact: true })).toBeVisible();
  await expect(page.getByText("คำอธิบายโครงงาน\nข้อมูลที่อ่านจากระบบจริง", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← กลับหน้าบัญชี", exact: true }).focus(); await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "โหลดข้อมูลใหม่", exact: true })).toBeFocused();
  await page.screenshot({ path: info.outputPath("workspace-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath("workspace-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.evaluate((value) => JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]).includes(value), data.teamName)).toBe(false);
  expect(writes).toBe(0);
  await page.getByRole("link", { name: "ดูโครงงานของทีม →", exact: true }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("heading", { name: data.projectName, exact: true })).toBeVisible();
});

for (const role of ["advisor", "coordinator"] as const) {
  test(`${role} sees only the approved work links without student API requests`, async ({ page }) => {
    const email = `advisor-browser-${tag}-${role === "advisor" ? "a" : "coordinator"}@example.test`;
    await login(page, email, "AdvisorBrowserFixtureA1");
    let studentReads = 0;
    page.on("request", (request) => { if ([TEAM, PROJECT].includes(request.url())) studentReads += 1; });
    await open(page);
    const nav = page.getByRole("navigation", { name: "ทางเข้างาน", exact: true });
    await expect(nav.getByRole("link")).toHaveCount(role === "advisor" ? 3 : 1);
    await expect(page.getByRole("region", { name: "ภาพรวมทีมและโครงงาน", exact: true })).toHaveCount(0);
    expect(studentReads).toBe(0);
    const link = role === "advisor" ? "โครงงานที่ปรึกษา" : "จัดการกรรมการโครงงาน";
    await nav.getByRole("link", { name: link }).click();
    await expect(page).toHaveURL(role === "advisor" ? /\/advisor\/projects$/ : /\/coordinator\/projects$/);
  });
}

test("generic 404 forbidden malformed and mismatched scopes never become empty or stale cards", async ({ page }) => {
  const data = await setup(page, { project: true });
  const team = (await (await page.request.get(TEAM)).json()).data;
  const project = (await (await page.request.get(PROJECT)).json()).data;
  for (const row of [
    { path: TEAM, status: 404, body: { error: { code: "GENERIC_NOT_FOUND" } } },
    { path: TEAM, status: 403, body: { error: { code: "ACCESS_FORBIDDEN" } } },
    { path: TEAM, status: 200, body: { data: {} } },
    { path: TEAM, status: 200, body: { data: { ...team, id: "0" } } },
    { path: PROJECT, status: 404, body: { error: { code: "TEAM_NOT_FOUND" } } },
    { path: PROJECT, status: 200, body: { data: {} } },
    { path: PROJECT, status: 200, body: { data: { ...project, team_id: "9223372036854775807" } } },
  ]) {
    const handler = (route: Route) => route.fulfill({ status: row.status, json: row.body });
    await page.route(row.path, handler); await page.goto("/workspace");
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByRole("heading", { name: data.teamName, exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: data.projectName, exact: true })).toHaveCount(0);
    await expect(page.getByText("คุณยังไม่มีทีม", { exact: true })).toHaveCount(0);
    await expect(page.getByText("ยังไม่มีโครงงานของทีม", { exact: true })).toHaveCount(0);
    await page.unroute(row.path, handler);
  }
});

test("Auth and business network errors retry safely and real Logout revokes the overview on focus", async ({ page }) => {
  const data = await setup(page, { project: true });
  let teamReads = 0;
  page.on("request", (request) => { if (request.url() === TEAM) teamReads += 1; });
  const fail = (route: Route) => route.abort();
  await page.route(ME, fail); await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "ยังเชื่อมต่อระบบไม่ได้", exact: true })).toBeVisible();
  expect(teamReads).toBe(0);
  await page.unroute(ME, fail); await page.route(TEAM, fail);
  await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
  await page.unroute(TEAM, fail); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: data.projectName, exact: true })).toBeVisible();
  expect((await page.request.post(`${API}/api/v1/auth/logout`, { headers: await headers(page) })).status()).toBe(204);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page).toHaveURL(/\/login\?reason=session$/);
  await expect(page.getByText(data.projectName, { exact: true })).toHaveCount(0);
});

test("switching accounts aborts an old pending Project response and clears the previous Team", async ({ page }) => {
  const data = await setup(page, { project: true });
  const next = await student(page, "บัญชีใหม่ไม่มีทีม");
  let release!: () => void; let waiting = false;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(PROJECT, async (route) => {
    const response = await route.fetch(); waiting = true; await gate;
    await route.fulfill({ response }).catch(() => {}); // The old request is intentionally aborted by account revalidation.
  });
  try {
    await page.goto("/workspace"); await expect.poll(() => waiting).toBe(true);
    await login(page, next.email); await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect(page.getByText(`สวัสดี, ${next.name}`, { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "คุณยังไม่มีทีม", exact: true })).toBeVisible();
    release();
    await expect(page.getByText(data.teamName, { exact: true })).toHaveCount(0);
    await expect(page.getByText(data.projectName, { exact: true })).toHaveCount(0);
  } finally { release(); }
});
