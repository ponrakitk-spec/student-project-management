import { expect, test, type Page } from "@playwright/test";

const API = "http://localhost:8001";
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e for rollback-only Evaluation fixtures");
const ORIGIN = { Origin: "http://localhost:3000" };
const name = (label: string) => `โครงงานประเมิน ${tag!.slice(0, 6)} ${label}`;
let unsafe = 0;
async function login(page: Page, label = "b") {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN,
    data: { email: `advisor-browser-${tag}-${label}@example.test`, password: "AdvisorBrowserFixtureA1" } })).status()).toBe(200);
}
async function student(page: Page, label: string) {
  expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: ORIGIN,
    data: { email: `evaluation-browser-${tag}-${label}@example.test`, password: "EvaluationBrowserFixtureA1" } })).status()).toBe(200);
}
async function headers(page: Page) {
  return { ...ORIGIN, "X-CSRF-Token": (await page.context().cookies(API)).find((row) => row.name === "spms_csrf")?.value ?? "" };
}
async function target(page: Page, label: string) {
  await login(page);
  const response = await page.request.get(`${API}/api/v1/committee/projects`);
  expect(response.status()).toBe(200);
  const row = (await response.json()).data.find((item: { name: string }) => item.name === name(label)) as { id: string; name: string };
  expect(row).toBeTruthy();
  return { ...row, api: `${API}/api/v1/committee/projects/${row.id}/evaluations`, url: `/committee/projects/${row.id}/evaluations` };
}
async function open(page: Page, row: { name: string; url: string }) {
  await page.goto(row.url);
  await expect(page.getByRole("heading", { name: row.name, exact: true, level: 1 })).toBeVisible();
}
async function choose(page: Page, score: string, comment: string) {
  await page.getByLabel("คะแนน (0–100)", { exact: true }).fill(score);
  await page.getByLabel("ความคิดเห็น", { exact: true }).fill(comment);
  await page.getByRole("button", { name: "ตรวจสอบก่อนบันทึก", exact: true }).click();
}
async function confirm(page: Page) {
  await page.getByRole("region", { name: "ยืนยันการประเมิน", exact: true }).getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "บันทึกการประเมินแล้ว" })).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  unsafe = 0;
  await page.route("**/api/v1/**", async (route) => {
    if (new URL(route.request().url()).origin !== API) { unsafe += 1; return route.abort(); }
    await route.continue();
  });
});
test.afterEach(() => { expect(unsafe).toBe(0); });

test("three scores release only approved projections after completion across all roles", async ({ page }, info) => {
  const row = await target(page, "flow");
  await page.goto("/committee/projects");
  await page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: row.name, exact: true }) }).getByRole("link", { name: "ประเมินโครงงาน", exact: true }).click();
  await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toBeVisible();
  let posts = 0;
  page.on("request", (request) => { if (request.url() === row.api && request.method() === "POST") { posts += 1; expect(Object.keys(request.postDataJSON()).sort()).toEqual(["comment", "score"]); } });
  await choose(page, "0", "Private score b");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click(); expect(posts).toBe(0);
  await page.getByRole("button", { name: "ตรวจสอบก่อนบันทึก", exact: true }).click();
  await page.screenshot({ path: info.outputPath("evaluation-confirm-desktop.png"), fullPage: true });
  await confirm(page);
  await expect(page.getByText("คะแนนของคุณ: 0 / 100", { exact: true })).toBeVisible();
  await student(page, "flow"); await page.goto("/projects");
  await page.getByRole("link", { name: "ผลประเมินโครงงาน →", exact: true }).click();
  await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toBeVisible();
  await expect(page.getByText("Private score b", { exact: true })).toHaveCount(0);
  await login(page, "a"); await page.goto("/advisor/projects");
  await page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: row.name, exact: true }) }).getByRole("link", { name: "ผลประเมินโครงงาน", exact: true }).click();
  await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toBeVisible();
  await login(page, "coordinator"); await page.goto(`/coordinator/projects/${row.id}/committee`);
  await page.getByRole("link", { name: "ผลประเมินโครงงาน →", exact: true }).click();
  await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toBeVisible();
  const before = (await (await page.request.get(`${API}/api/v1/coordinator/projects/${row.id}/evaluations`)).json()).data;
  expect(before.summary).toBeNull(); expect(before.evaluations).toEqual([]);
  for (const label of ["c", "d"]) {
    await login(page, label); await open(page, row);
    await expect(page.getByText("Private score b", { exact: true })).toHaveCount(0);
    await choose(page, "100", `Private score ${label}`); await confirm(page);
  }
  await student(page, "flow"); await page.goto("/projects/evaluations");
  const summary = page.getByRole("region", { name: "สรุปคะแนน", exact: true });
  await expect(summary.getByText("200", { exact: true })).toBeVisible();
  await expect(summary.getByText("67 / 100", { exact: true })).toBeVisible();
  await expect(page.getByText(/Private score/)).toHaveCount(0);
  const reader = (await (await page.request.get(`${API}/api/v1/projects/me/evaluations`)).json()).data;
  expect(Object.keys(reader).sort()).toEqual(["project", "summary"]);
  expect(reader.summary).toEqual({ total_score: "200", average_score: 67 });
  await page.screenshot({ path: info.outputPath("evaluation-team-summary-desktop.png"), fullPage: true });
  await login(page, "coordinator"); await page.goto(`/coordinator/projects/${row.id}/evaluations`);
  await expect(page.getByRole("list", { name: "ผลประเมินรายบุคคล", exact: true }).getByRole("listitem")).toHaveCount(3);
  await expect(page.getByText("Private score b", { exact: true })).toBeVisible();
});

test("mobile validates integer comment and confirmation then submits score zero once", async ({ page }, info) => {
  const row = await target(page, "mobile");
  await page.setViewportSize({ width: 390, height: 844 }); await open(page, row);
  for (const score of ["", "1.5", "101"]) {
    await choose(page, score, "valid");
    await expect(page.getByRole("alert").filter({ hasText: "กรุณาระบุคะแนนจำนวนเต็ม 0–100" })).toBeVisible();
  }
  await choose(page, "0", " \t\n");
  await expect(page.getByRole("alert").filter({ hasText: "กรุณาระบุความคิดเห็น" })).toBeVisible();
  await choose(page, "0", "แนวทางการพัฒนาชัดเจน");
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await page.getByRole("button", { name: "ตรวจสอบก่อนบันทึก", exact: true }).click();
  await page.screenshot({ path: info.outputPath("evaluation-confirm-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  let posts = 0; let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(row.api, async (route) => { if (route.request().method() !== "POST") return route.continue(); posts += 1; await gate; await route.continue(); });
  await page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click();
  await expect(page.getByRole("button", { name: "ยกเลิก", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "กำลังบันทึก…", exact: true }).evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  await expect.poll(() => posts).toBe(1); release();
  await expect(page.getByText("คะแนนของคุณ: 0 / 100", { exact: true })).toBeVisible();
  await page.reload(); await expect(page.getByText("คะแนนของคุณ: 0 / 100", { exact: true })).toBeVisible();
  await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toHaveCount(0);
});

test("lost real 201 reconciles own score without replaying POST", async ({ page }) => {
  const row = await target(page, "lost"); await open(page, row);
  let posts = 0;
  await page.route(row.api, async (route) => { if (route.request().method() !== "POST") return route.continue(); posts += 1; expect((await route.fetch()).status()).toBe(201); await route.abort(); });
  await choose(page, "77", "Lost evaluation response");
  await page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ยังยืนยันผลไม่ได้" })).toBeVisible();
  await expect(page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByText("คะแนนของคุณ: 77 / 100", { exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "บันทึกการประเมินแล้ว" })).toHaveCount(0);
  expect(posts).toBe(1);
});

test("topic and completed milestone prerequisites disable forms and reject direct API writes", async ({ page }) => {
  for (const [label, code, text] of [["phase", "COMPLETED_MILESTONE_REQUIRED", "ต้องมี Milestone ที่เสร็จสมบูรณ์อย่างน้อย 1 รายการก่อนประเมิน"],
    ["topic", "TOPIC_NOT_APPROVED", "หัวข้อโครงงานยังไม่ผ่านการอนุมัติจากกรรมการ"]]) {
    const row = await target(page, label); await open(page, row);
    await expect(page.getByText(text, { exact: true })).toBeVisible();
    await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toHaveCount(0);
    const response = await page.request.post(row.api, { headers: await headers(page), data: { score: 80, comment: "valid" } });
    expect(response.status()).toBe(409); expect((await response.json()).error.code).toBe(code);
  }
});

test("partial scores stay hidden from every other role including coordinator", async ({ page }) => {
  const row = await target(page, "privacy"); await login(page, "c"); await open(page, row);
  await expect(page.getByText("Private evaluation browser feedback", { exact: true })).toHaveCount(0);
  const committee = (await (await page.request.get(row.api)).json()).data;
  expect(committee.own_evaluation).toBeNull(); expect(committee.summary).toBeNull();
  for (const mode of ["team", "advisor", "coordinator"]) {
    if (mode === "team") await student(page, "privacy"); else await login(page, mode === "advisor" ? "a" : "coordinator");
    await page.goto(mode === "team" ? "/projects/evaluations" : `/${mode}/projects/${row.id}/evaluations`);
    await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toBeVisible();
    await expect(page.getByText("Private evaluation browser feedback", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("list", { name: "ผลประเมินรายบุคคล", exact: true })).toHaveCount(0);
  }
});

test("stale eligible form gets real duplicate conflict and refreshes immutable original", async ({ page }) => {
  const row = await target(page, "privacy");
  const original = (await (await page.request.get(row.api)).json()).data;
  let posts = 0;
  await page.route(row.api, async (route) => {
    if (route.request().method() === "POST") { posts += 1; return route.continue(); }
    // Keep the stale snapshot through development-mode repeated reads until the write.
    if (posts === 0) return route.fulfill({ status: 200, json: { data: { ...original, can_evaluate: true, blocking_reason: null, own_evaluation: null } } });
    await route.continue();
  });
  await open(page, row); await choose(page, "99", "New stale evaluation");
  await page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "คุณประเมินโครงงานนี้แล้ว" })).toBeVisible();
  await expect(page.getByText("คะแนนของคุณ: 10 / 100", { exact: true })).toBeVisible();
  await expect(page.getByText("Private evaluation browser feedback", { exact: true })).toBeVisible(); expect(posts).toBe(1);
});

test("malformed GET shows an error and retry restores the actual form", async ({ page }) => {
  const row = await target(page, "error");
  const malformed = async (route: import("@playwright/test").Route) => route.fulfill({ status: 200, json: { data: { summary: null } } });
  await page.route(row.api, malformed); await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
  await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toHaveCount(0);
  await page.unroute(row.api, malformed); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toBeVisible();
});

test("invalid POST status and failed reconciliation never claim success or retry writes", async ({ page }) => {
  const row = await target(page, "error"); await open(page, row);
  let posts = 0;
  await page.route(row.api, async (route) => { if (route.request().method() !== "POST") return route.continue(); posts += 1; await route.fulfill({ status: 200, json: { data: {} } }); });
  await choose(page, "80", "valid"); await page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ข้อมูลตอบกลับไม่ถูกต้อง" })).toBeVisible();
  await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  const failure = async (route: import("@playwright/test").Route) => route.request().method() === "GET" ? route.abort() : route.continue();
  await page.route(row.api, failure); await page.getByRole("button", { name: "ตรวจข้อมูลอีกครั้ง", exact: true }).click();
  await expect(page.getByRole("heading", { name: "ยังโหลดข้อมูลไม่ได้", exact: true })).toBeVisible();
  await page.unroute(row.api, failure); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click();
  await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toHaveValue(""); expect(posts).toBe(1);
});

test("anonymous wrong roles and accepted advisor without assignment cannot evaluate", async ({ page }) => {
  const row = await target(page, "error");
  await page.context().clearCookies(); await page.goto(row.url); await expect(page).toHaveURL(/\/login\?reason=session$/);
  await login(page, "coordinator"); await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", exact: true })).toBeVisible();
  expect((await page.request.get(row.api)).status()).toBe(403);
  await login(page, "a"); await page.goto(row.url);
  await expect(page.getByRole("heading", { name: "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ", exact: true })).toBeVisible();
  await page.goto(`/advisor/projects/${row.id}/evaluations`);
  await expect(page.getByText("รอกรรมการประเมินครบทุกคน", { exact: true })).toBeVisible();
});

test("completed half average rounds in SQL and coordinator renders individual zero scores", async ({ page }) => {
  const row = await target(page, "half"); await open(page, row);
  await expect(page.getByText("คะแนนของคุณ: 0 / 100", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "สรุปคะแนน", exact: true }).getByText("1 / 100", { exact: true })).toBeVisible();
  await student(page, "half"); await page.goto("/projects/evaluations");
  await expect(page.getByRole("region", { name: "สรุปคะแนน", exact: true }).getByText("2", { exact: true })).toBeVisible();
  await expect(page.getByText(/Completed evaluation advice/)).toHaveCount(0);
  await login(page, "coordinator"); await page.goto(`/coordinator/projects/${row.id}/evaluations`);
  await expect(page.getByRole("list", { name: "ผลประเมินรายบุคคล", exact: true }).getByRole("listitem")).toHaveCount(4);
  await expect(page.getByText("คะแนน: 0 / 100", { exact: true })).toHaveCount(2);
});
