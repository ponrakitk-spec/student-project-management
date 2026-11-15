import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8001";
const ROOT = `${API}/api/v1/committee/projects`;
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e for rollback-only topic fixtures");
const ORIGIN = { Origin: "http://localhost:3000" };
const name = (label: string) => `โครงงานลงมติ ${tag!.slice(0, 6)} ${label}`;
let unsafe = 0;
async function login(page: Page, label = "b") {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN,
    data: { email: `advisor-browser-${tag}-${label}@example.test`, password: "AdvisorBrowserFixtureA1" } })).status()).toBe(200);
}
async function student(page: Page, label: string) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN,
    data: { email: `topic-browser-${tag}-${label}@example.test`, password: "TopicBrowserFixtureA1" } })).status()).toBe(200);
}
async function headers(page: Page) {
  return { ...ORIGIN, "X-CSRF-Token": (await page.context().cookies(API)).find((row) => row.name === "spms_csrf")?.value ?? "" };
}
async function target(page: Page, label: string) {
  await login(page);
  const response = await page.request.get(ROOT);
  expect(response.status()).toBe(200);
  const row = (await response.json()).data.find((item: { name: string }) => item.name === name(label)) as { id: string; name: string };
  expect(row).toBeTruthy();
  return { ...row, api: `${ROOT}/${row.id}/topic-votes`, url: `/committee/projects/${row.id}/topic-votes` };
}
async function open(page: Page, row: { name: string; url: string }) {
  await page.goto(row.url);
  await expect(page.getByRole("heading", { name: row.name, exact: true, level: 1 })).toBeVisible();
}
async function choose(page: Page, choice: "approved" | "revision_requested", comment = "") {
  await page.getByLabel("ผลการลงมติ", { exact: true }).selectOption(choice);
  await page.getByLabel("ความคิดเห็น", { exact: true }).fill(comment);
  await page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true }).click();
}
async function confirm(page: Page) {
  await page.getByRole("region", { name: "ยืนยันการลงมติ", exact: true }).getByRole("button", { name: "ยืนยันลงมติ", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "บันทึกการลงมติแล้ว" })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); });

test("three committee votes release anonymous results only when complete across all roles", async ({ page }, info) => {
  const row = await target(page, "flow");
  await page.goto("/"); await page.getByRole("link", { name: "งานกรรมการ →", exact: true }).click();
  await expect(page.getByRole("heading", { name: row.name, exact: true })).toBeVisible();
  await open(page, row);
  let posts = 0;
  page.on("request", (request) => { if (request.url() === row.api && request.method() === "POST") { posts += 1; expect(Object.keys(request.postDataJSON()).sort()).toEqual(["comment", "submission_id", "vote"]); } });
  await choose(page, "approved", "Zulu visible after complete");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click(); expect(posts).toBe(0);
  await page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true }).click();
  await page.screenshot({ path: info.outputPath("topic-confirm-desktop.png"), fullPage: true });
  await confirm(page);
  await login(page, "c"); await open(page, row);
  await expect(page.getByText("Zulu visible after complete", { exact: true })).toHaveCount(0);
  await choose(page, "revision_requested", "Alpha visible after complete"); await confirm(page);
  await student(page, "flow"); await page.goto("/projects");
  await page.getByRole("link", { name: "รายชื่อกรรมการและผลหัวข้อ →", exact: true }).click();
  await expect(page.getByRole("list", { name: "รายชื่อกรรมการ", exact: true }).getByRole("listitem")).toHaveCount(3);
  await expect(page.getByText("ผลสรุป: รอผลสรุปจากกรรมการ", { exact: true })).toBeVisible();
  await expect(page.getByText(/visible after complete/)).toHaveCount(0);
  await login(page, "d"); await open(page, row); await choose(page, "approved"); await confirm(page);
  await expect(page.getByText("ผลสรุป: ผ่าน", { exact: true })).toBeVisible();
  await expect(page.getByText(/visible after complete/)).toHaveCount(0);
  await student(page, "flow"); await page.goto("/projects/committee");
  await expect(page.getByText("ผลสรุป: ผ่าน", { exact: true })).toBeVisible();
  const comments = page.getByRole("list", { name: "ความคิดเห็นจากกรรมการ", exact: true }).getByRole("listitem");
  await expect(comments).toHaveText(["Alpha visible after complete", "Zulu visible after complete"]);
  const reader = (await (await page.request.get(`${API}/api/v1/projects/me/committee`)).json()).data;
  expect(Object.keys(reader.rounds[0]).sort()).toEqual(["comments", "decision", "submission"]);
  await page.screenshot({ path: info.outputPath("topic-team-summary-desktop.png"), fullPage: true });
  await login(page, "a"); await page.goto("/");
  await page.getByRole("link", { name: "โครงงานที่ปรึกษา →", exact: true }).click();
  await page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: row.name, exact: true }) }).getByRole("link", { name: "ดูรายชื่อกรรมการและผลหัวข้อ", exact: true }).click();
  await expect(page.getByText("ผลสรุป: ผ่าน", { exact: true })).toBeVisible();
  await login(page, "coordinator"); await page.goto(`/coordinator/projects/${row.id}/committee`);
  await page.getByRole("link", { name: "ดูการลงมติรายบุคคล →", exact: true }).click();
  await expect(page.getByRole("list", { name: "ผลลงมติรายบุคคล", exact: true }).getByRole("listitem")).toHaveCount(3);
});

test("mobile comment validation confirmation cancel and pending submit send once", async ({ page }, info) => {
  const row = await target(page, "mobile");
  await page.setViewportSize({ width: 390, height: 844 }); await open(page, row);
  await page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "กรุณาเลือกผลการลงมติ" })).toBeVisible();
  await choose(page, "revision_requested", " \t\n");
  await expect(page.getByRole("alert").filter({ hasText: "กรุณาระบุความคิดเห็น" })).toBeVisible();
  await choose(page, "revision_requested", "ปรับรายละเอียดหัวข้อให้ชัดเจน");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true }).click();
  await page.screenshot({ path: info.outputPath("topic-confirm-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  let posts = 0; let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(row.api, async (route) => { if (route.request().method() !== "POST") return route.continue(); posts += 1; await gate; await route.continue(); });
  await page.getByRole("button", { name: "ยืนยันลงมติ", exact: true }).click();
  await expect(page.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "กำลังบันทึก…", exact: true }).evaluate((element: HTMLButtonElement) => { element.click(); element.click(); });
  await expect.poll(() => posts).toBe(1); release();
  await expect(page.getByRole("status").filter({ hasText: "บันทึกการลงมติแล้ว" })).toBeVisible();
  await page.reload(); await expect(page.getByRole("heading", { name: "การลงมติของคุณ", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true })).toHaveCount(0);
});

test("lost real 201 recovers own vote through GET without replaying POST", async ({ page }) => {
  const row = await target(page, "lost"); await open(page, row);
  let posts = 0;
  await page.route(row.api, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1; expect((await route.fetch()).status()).toBe(201); await route.abort();
  });
  await choose(page, "approved", "Lost response fixture");
  await page.getByRole("button", { name: "ยืนยันลงมติ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ยังยืนยันผลไม่ได้" })).toBeVisible();
  await expect(page.getByRole("button", { name: "ยืนยันลงมติ", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "การลงมติของคุณ", exact: true })).toBeVisible();
  expect(posts).toBe(1);
});

test("old snapshot token produces real stale conflict and no implicit vote on latest", async ({ page }) => {
  const row = await target(page, "stale"); await open(page, row);
  const data = (await (await page.request.get(row.api)).json()).data;
  let posts = 0;
  await page.route(row.api, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1; await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), submission_id: data.rounds[1].submission.id }) });
  });
  await choose(page, "approved"); await page.getByRole("button", { name: "ยืนยันลงมติ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "มีรอบส่งใหม่" })).toBeVisible();
  await expect(page.getByLabel("ผลการลงมติ", { exact: true })).toHaveValue("");
  expect((await (await page.request.get(row.api)).json()).data.rounds[0].own_vote).toBeNull();
  expect(posts).toBe(1);
});

test("incomplete committee and later pending revision round keep forms disabled", async ({ page }) => {
  const row = await target(page, "incomplete"); await open(page, row);
  await expect(page.getByText("ต้องมีกรรมการอย่างน้อย 3 คนก่อนลงมติ", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true })).toHaveCount(0);
  const data = (await (await page.request.get(row.api)).json()).data;
  expect((await page.request.post(row.api, { headers: await headers(page), data: { submission_id: data.latest_submission_id, vote: "approved" } })).status()).toBe(409);
  const revision = await target(page, "revision"); await open(page, revision);
  await expect(page.getByText("รอบล่าสุดยังไม่ผ่านการอนุมัติจากอาจารย์", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ตรวจสอบก่อนลงมติ", exact: true })).toHaveCount(0);
  const latest = (await (await page.request.get(revision.api)).json()).data.latest_submission_id;
  await login(page, "coordinator");
  const coordinator = (await (await page.request.get(`${API}/api/v1/coordinator/projects/${revision.id}/topic-votes`)).json()).data;
  expect(coordinator.rounds).toHaveLength(1); expect(coordinator.rounds[0].submission.id).not.toBe(latest);
});

test("before completion private comments stay hidden from committee team and accepted advisor", async ({ page }) => {
  const row = await target(page, "private"); await login(page, "d"); await open(page, row);
  await expect(page.getByText(/Private topic comment/)).toHaveCount(0);
  expect(JSON.stringify((await (await page.request.get(row.api)).json()).data)).not.toContain("Private topic comment");
  await student(page, "private"); await page.goto("/projects/committee");
  await expect(page.getByText("ผลสรุป: รอผลสรุปจากกรรมการ", { exact: true })).toBeVisible();
  await expect(page.getByText(/Private topic comment/)).toHaveCount(0);
  await login(page, "a"); await page.goto(`/advisor/projects/${row.id}/committee`);
  await expect(page.getByText(/Private topic comment/)).toHaveCount(0);
  await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ", exact: true })).toBeVisible();
  await login(page, "coordinator"); await page.goto(`/coordinator/projects/${row.id}/topic-votes`);
  await expect(page.getByText("Private topic comment b", { exact: true })).toBeVisible();
  await expect(page.getByText("Private topic comment c", { exact: true })).toBeVisible();
});

test("malformed reads anonymous sessions and wrong roles never expose a vote form", async ({ page }) => {
  const row = await target(page, "error");
  const malformed = async (route: import("@playwright/test").Route) => route.fulfill({ status: 200, json: { data: { rounds: [] } } });
  await page.route(row.api, malformed); await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByLabel("ผลการลงมติ", { exact: true })).toHaveCount(0);
  await page.unroute(row.api, malformed);
  await page.context().clearCookies(); await page.goto(row.url); await expect(page).toHaveURL(/\/login\?reason=session$/);
  await login(page, "coordinator"); await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", exact: true })).toBeVisible();
});

test("unexpected success status and failed GET preserve uncertainty instead of fake success", async ({ page }) => {
  const row = await target(page, "error"); await open(page, row);
  let posts = 0;
  await page.route(row.api, async (route) => { if (route.request().method() !== "POST") return route.continue(); posts += 1; await route.fulfill({ status: 200, json: { data: {} } }); });
  await choose(page, "approved"); await page.getByRole("button", { name: "ยืนยันลงมติ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ข้อมูลตอบกลับไม่ถูกต้อง" })).toBeVisible();
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  const failure = async (route: import("@playwright/test").Route) => route.request().method() === "GET" ? route.abort() : route.continue();
  await page.route(row.api, failure); await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "การลงมติของคุณ", exact: true })).toHaveCount(0);
  await page.unroute(row.api, failure); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByLabel("ผลการลงมติ", { exact: true })).toHaveValue(""); expect(posts).toBe(1);
});

test("a completed fifty percent tie stays revision and duplicate anonymous comments remain", async ({ page }) => {
  const row = await target(page, "tie"); await open(page, row);
  await expect(page.getByText("ผลสรุป: ขอแก้ไข", { exact: true })).toBeVisible();
  await student(page, "tie"); await page.goto("/projects/committee");
  await expect(page.getByText("ผลสรุป: ขอแก้ไข", { exact: true })).toBeVisible();
  await expect(page.getByRole("list", { name: "ความคิดเห็นจากกรรมการ", exact: true }).getByRole("listitem")).toHaveText(Array(4).fill("Same revision advice"));
});
