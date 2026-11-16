import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
const API = "http://localhost:8001"; const PASSWORD = "TaskBrowserFixtureA1"; const STAFF_PASSWORD = "AdvisorBrowserFixtureA1";
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e for rollback-only staff fixtures");
const staffEmail = (label: string) => `advisor-browser-${tag}-${label}@example.test`;
const region = (page: Page) => page.getByRole("region", { name: "งานย่อยและผู้รับผิดชอบ", exact: true });
async function headers(page: Page) { return { Origin: "http://localhost:3000", "X-CSRF-Token": (await page.context().cookies(API)).find(c => c.name === "spms_csrf")?.value ?? "" }; }
async function login(page: Page, email: string, password = PASSWORD) { expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: await headers(page), data: { email, password } })).status()).toBe(200); }
async function register(page: Page, name = "นักศึกษาทดสอบงานย่อย") {
  const email = `task-browser-${randomUUID()}@example.test`;
  const response = await page.request.post(`${API}/api/v1/auth/register`, { headers: await headers(page), data: { full_name: name, email, password: PASSWORD } }); expect(response.status()).toBe(201);
  return { ...(await response.json()).data, email } as { id: string; email: string; full_name: string };
}
async function setup(page: Page, extraMember = false) {
  const user = await register(page); await login(page, user.email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมงานย่อย" } })).status()).toBe(201);
  const project = (await (await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: `โครงงาน Task ${randomUUID().slice(0, 8)}` } })).json()).data;
  const member = extraMember ? await register(page, "สมาชิกงานย่อย") : null;
  if (member) expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: member.email } })).status()).toBe(201);
  const response = await page.request.post(`${API}/api/v1/projects/me/milestones`, { headers: await headers(page), data: { name: "แผนงาน Task", due_date: "2099-12-31" } }); expect(response.status()).toBe(201);
  const milestone = (await response.json()).data;
  return { user, member, project, milestone, url: `/projects/milestones/${milestone.id}/tasks`, api: `${API}/api/v1/milestones/${milestone.id}/tasks` };
}
async function create(page: Page) {
  await page.getByRole("button", { name: "สร้างงานย่อย", exact: true }).click(); await page.getByLabel("ชื่องานย่อย", { exact: true }).fill("งานที่ทำผ่านเว็บ");
  await page.getByRole("button", { name: "บันทึกงานย่อย", exact: true }).click(); await expect(region(page).getByRole("status").filter({ hasText: "สร้างงานย่อยแล้ว" })).toBeVisible();
}
async function assignSelf(page: Page) {
  await page.getByLabel("เลือกผู้รับผิดชอบ", { exact: true }).selectOption({ label: "นักศึกษาทดสอบงานย่อย (คุณ)" }); await page.getByRole("button", { name: "มอบหมายงาน", exact: true }).click();
  await expect(region(page).getByRole("status").filter({ hasText: "มอบหมายงานแล้ว" })).toBeVisible();
}
async function status(page: Page, value: string) { await page.getByLabel("สถานะงานย่อย", { exact: true }).selectOption(value); await page.getByRole("button", { name: "บันทึกสถานะงาน", exact: true }).click(); await expect(region(page).getByRole("status").filter({ hasText: "เปลี่ยนสถานะงานแล้ว" })).toBeVisible(); }
function pdf() {
  let data = "%PDF-1.4\n"; const offsets = [0];
  for (const [index, body] of ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"].entries()) { offsets.push(Buffer.byteLength(data)); data += `${index + 1} 0 obj\n${body}\nendobj\n`; }
  const xref = Buffer.byteLength(data); data += "xref\n0 4\n0000000000 65535 f \n" + offsets.slice(1).map(n => `${String(n).padStart(10, "0")} 00000 n \n`).join("");
  return Buffer.from(data + `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}
test.beforeEach(async ({ page }) => { await page.route("**/api/v1/**", route => { if (new URL(route.request().url()).origin !== API) throw new Error("Unexpected API origin"); return route.continue(); }); });

test("fresh Project through real submission votes Task UI completion and Evaluation UI without SQL phase shortcuts", async ({ page }) => {
  const s = await setup(page);
  const candidates = (await (await page.request.get(`${API}/api/v1/projects/me/advisor-candidates`)).json()).data;
  const teacher = (label: string) => candidates.find((r: { full_name: string }) => r.full_name === `อาจารย์ทดสอบ ${label.toUpperCase()} ${tag!.slice(0, 6)}`);
  const invitation = (await (await page.request.post(`${API}/api/v1/projects/me/advisor-invitations`, { headers: await headers(page), data: { advisor_id: teacher("a").id } })).json()).data;
  await login(page, staffEmail("a"), STAFF_PASSWORD);
  expect((await page.request.post(`${API}/api/v1/advisor-invitations/${invitation.id}/respond`, { headers: await headers(page), data: { decision: "accepted" } })).status()).toBe(200);
  await login(page, s.user.email); await page.goto("/projects/submissions"); await page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true }).setInputFiles({ name: "proposal.pdf", mimeType: "application/pdf", buffer: pdf() });
  await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click(); await expect(page.getByRole("status")).toContainText("ส่งโครงงานแล้ว");
  const submission = (await (await page.request.get(`${API}/api/v1/projects/me/submissions`)).json()).data[0];
  await login(page, staffEmail("a"), STAFF_PASSWORD); await page.goto("/advisor/submissions"); const review = page.getByTestId(`submission-${submission.id}`);
  await review.getByRole("button", { name: "บันทึกผลตรวจ", exact: true }).click(); await review.getByRole("button", { name: "ยืนยันผลตรวจ", exact: true }).click(); await expect(review).toContainText("อาจารย์อนุมัติแล้ว");
  await login(page, staffEmail("coordinator"), STAFF_PASSWORD);
  for (const label of ["b", "c", "d"]) expect((await page.request.post(`${API}/api/v1/coordinator/projects/${s.project.id}/committee`, { headers: await headers(page), data: { advisor_id: teacher(label).id } })).status()).toBe(201);
  for (const label of ["b", "c", "d"]) { await login(page, staffEmail(label), STAFF_PASSWORD); expect((await page.request.post(`${API}/api/v1/committee/projects/${s.project.id}/topic-votes`, { headers: await headers(page), data: { submission_id: submission.id, vote: "approved", comment: null } })).status()).toBe(201); }
  await login(page, s.user.email); await page.goto("/projects/milestones"); await page.getByTestId(`milestone-${s.milestone.id}`).getByRole("link", { name: "งานย่อยและผู้รับผิดชอบ →", exact: true }).click();
  await create(page); await assignSelf(page); await status(page, "completed"); await expect(page.getByText("แผนงาน: เสร็จแล้ว", { exact: false })).toBeVisible();
  await login(page, staffEmail("b"), STAFF_PASSWORD); await page.goto(`/committee/projects/${s.project.id}/evaluations`);
  await expect(page.getByLabel("คะแนน (0–100)", { exact: true })).toBeVisible(); await page.getByLabel("คะแนน (0–100)", { exact: true }).fill("80"); await page.getByLabel("ความคิดเห็น", { exact: true }).fill("ทำครบผ่าน API และเว็บ");
  await page.getByRole("button", { name: "ตรวจสอบก่อนบันทึก", exact: true }).click(); await page.getByRole("button", { name: "ยืนยันบันทึกการประเมิน", exact: true }).click(); await expect(page.getByText("คะแนนของคุณ: 80 / 100", { exact: true })).toBeVisible();
  await login(page, s.user.email); await page.goto(s.url); await expect(page.getByRole("button", { name: "สร้างงานย่อย", exact: true })).toHaveCount(0); await expect(page.getByText("งานถูกล็อกหลังมีคะแนนประเมินแล้ว", { exact: true })).toBeVisible();
});

test("member changes status without assignment ownership but has no leader controls", async ({ page }) => {
  const s = await setup(page, true); await page.goto(s.url); await create(page); await assignSelf(page);
  await login(page, s.member!.email); await page.goto(s.url); await page.getByRole("button", { name: "ดูรายละเอียดงาน", exact: true }).click();
  await expect(page.getByRole("button", { name: "สร้างงานย่อย", exact: true })).toHaveCount(0); await expect(page.getByRole("button", { name: "แก้ไขงานย่อย", exact: true })).toHaveCount(0); await expect(page.getByLabel("เลือกผู้รับผิดชอบ", { exact: true })).toHaveCount(0);
  await status(page, "completed"); await expect(page.getByLabel("สถานะงานย่อย", { exact: true })).toHaveCount(0);
});

test("last active assignee conflict rolls back then real withdrawal records history", async ({ page }) => {
  const s = await setup(page); await page.goto(s.url); await create(page); await assignSelf(page); await status(page, "in_progress");
  await page.getByRole("button", { name: "ถอนผู้รับผิดชอบ", exact: true }).click(); await page.getByRole("button", { name: "ยืนยันถอนผู้รับผิดชอบ", exact: true }).click(); await expect(region(page).getByRole("alert")).toContainText("ต้องมีผู้รับผิดชอบ");
  await page.getByRole("button", { name: "โหลดข้อมูลงานอีกครั้ง", exact: true }).click(); await expect(page.getByRole("list", { name: "ผู้รับผิดชอบปัจจุบัน", exact: true }).getByRole("listitem")).toHaveCount(1);
  await status(page, "not_started"); await page.getByRole("button", { name: "ถอนผู้รับผิดชอบ", exact: true }).click(); await page.getByRole("button", { name: "ยืนยันถอนผู้รับผิดชอบ", exact: true }).click();
  await expect(region(page).getByRole("status").filter({ hasText: "ถอนผู้รับผิดชอบแล้ว" })).toBeVisible(); await expect(page.getByRole("list", { name: "ประวัติถอนผู้รับผิดชอบ", exact: true }).getByRole("listitem")).toHaveCount(1);
});

test("leader reopens completed Task before editing and confirms cascade deletion", async ({ page }) => {
  const s = await setup(page); await page.goto(s.url); await create(page); await assignSelf(page); await status(page, "completed");
  await expect(page.getByRole("button", { name: "แก้ไขงานย่อย", exact: true })).toHaveCount(0); await status(page, "in_progress");
  await page.getByRole("button", { name: "แก้ไขงานย่อย", exact: true }).click(); await page.getByLabel("คำอธิบายงาน (ไม่บังคับ)", { exact: true }).fill("ปรับงานที่เปิดกลับ"); await page.getByRole("button", { name: "บันทึกงานย่อย", exact: true }).click();
  await expect(region(page)).toContainText("ปรับงานที่เปิดกลับ"); await page.getByRole("button", { name: "ลบงานย่อย", exact: true }).click(); await page.getByRole("button", { name: "ยกเลิก", exact: true }).click();
  await expect(page.locator('[data-testid^="task-"]')).toHaveCount(1); await page.getByRole("button", { name: "ลบงานย่อย", exact: true }).click(); await page.getByRole("button", { name: "ยืนยันลบงานย่อย", exact: true }).click();
  await expect(page.locator('[data-testid^="task-"]')).toHaveCount(0); await expect(page.getByText("แผนงาน: ยังไม่เริ่ม", { exact: false })).toBeVisible();
});

test("lost create response blocks replay and reconciles using GET", async ({ page }) => {
  const s = await setup(page); let posts = 0; await page.route(s.api, async route => { if (route.request().method() !== "POST") return route.continue(); posts++; expect((await route.fetch()).status()).toBe(201); await route.abort(); });
  await page.goto(s.url); await page.getByRole("button", { name: "สร้างงานย่อย", exact: true }).click(); await page.getByLabel("ชื่องานย่อย", { exact: true }).fill("ผลตอบกลับหาย"); await page.getByRole("button", { name: "บันทึกงานย่อย", exact: true }).click();
  await expect(region(page).getByRole("alert")).toContainText("โหลดข้อมูล"); await expect(page.getByRole("button", { name: "บันทึกงานย่อย", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "โหลดข้อมูลงานอีกครั้ง", exact: true }).click(); await expect(page.locator('[data-testid^="task-"]')).toHaveCount(1); expect(posts).toBe(1);
});

test("malformed Task scope cannot become a create form", async ({ page }) => {
  const s = await setup(page); const data = (await (await page.request.get(s.api)).json()).data; data.milestone.project_id = "9223372036854775807";
  await page.route(s.api, route => route.fulfill({ status: 200, json: { data } })); await page.goto(s.url); await expect(page.getByRole("heading", { name: "ยังโหลดงานไม่ได้" })).toBeVisible(); await expect(page.getByRole("button", { name: "สร้างงานย่อย", exact: true })).toHaveCount(0);
  await page.unroute(s.api); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click(); await expect(page.getByRole("button", { name: "สร้างงานย่อย", exact: true })).toBeVisible();
});

test("mobile assignment is submitted once while pending without horizontal overflow", async ({ page }) => {
  const s = await setup(page); await page.setViewportSize({ width: 390, height: 844 }); await page.goto(s.url); await create(page);
  expect((await page.request.patch(`${API}/api/v1/milestones/${s.milestone.id}`, { headers: await headers(page), data: { name: "X".repeat(255) } })).status()).toBe(200);
  await page.getByRole("button", { name: "โหลดงานใหม่", exact: true }).click();
  const task = (await (await page.request.get(s.api)).json()).data.tasks[0]; let posts = 0; let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(`${API}/api/v1/tasks/${task.id}/assignees`, async route => { if (route.request().method() !== "POST") return route.continue(); posts++; await gate; await route.continue(); });
  await page.getByLabel("เลือกผู้รับผิดชอบ", { exact: true }).selectOption({ label: "นักศึกษาทดสอบงานย่อย (คุณ)" }); await page.getByRole("button", { name: "มอบหมายงาน", exact: true }).click();
  try { await expect(page.getByRole("button", { name: "มอบหมายงาน", exact: true })).toBeDisabled(); expect(posts).toBe(1); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); } finally { release(); }
  await expect(region(page).getByRole("status").filter({ hasText: "มอบหมายงานแล้ว" })).toBeVisible(); expect(posts).toBe(1);
});

test("anonymous wrong role and exited member cannot read old Tasks", async ({ page }) => {
  const s = await setup(page, true); await page.goto(s.url); await create(page);
  await login(page, s.member!.email); expect((await page.request.post(`${API}/api/v1/teams/me/leave`, { headers: await headers(page), data: {} })).status()).toBe(204); await page.goto(s.url); await expect(page.getByRole("heading", { name: "ยังโหลดงานไม่ได้" })).toBeVisible();
  await login(page, staffEmail("a"), STAFF_PASSWORD); await page.goto(s.url); await expect(page.getByRole("heading", { name: "หน้านี้สำหรับนักศึกษา" })).toBeVisible();
  await page.context().clearCookies(); await page.goto(s.url); await expect(page).toHaveURL(/\/login(?:\?|$)/);
});
