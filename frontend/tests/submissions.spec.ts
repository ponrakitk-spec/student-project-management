import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
const API = "http://localhost:8001"; const ROOT = `${API}/api/v1/projects/me/submissions`;
const PASSWORD = "SubmissionUiFixtureA1"; const STAFF_PASSWORD = "AdvisorBrowserFixtureA1";
const tag = process.env.SPMS_ADVISOR_FIXTURE_TAG;
if (!tag || !/^[a-f0-9]{32}$/.test(tag)) throw new Error("Use npm run test:e2e with rollback fixtures");
const advisor = `advisor-browser-${tag}-a@example.test`;
const alerts = (page: Page) => page.getByRole("region", { name: "การส่งโครงงานของทีม", exact: true }).getByRole("alert");
function pdf() {
  let data = "%PDF-1.4\n"; const offsets = [0];
  for (const [index, body] of ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"].entries()) {
    offsets.push(Buffer.byteLength(data)); data += `${index + 1} 0 obj\n${body}\nendobj\n`;
  }
  const xref = Buffer.byteLength(data); data += "xref\n0 4\n0000000000 65535 f \n";
  data += offsets.slice(1).map(n => `${String(n).padStart(10, "0")} 00000 n \n`).join("");
  return Buffer.from(data + `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}
async function headers(page: Page) { return { Origin: "http://localhost:3000", "X-CSRF-Token": (await page.context().cookies(API)).find(c => c.name === "spms_csrf")?.value ?? "" }; }
async function login(page: Page, email: string, password = PASSWORD) { expect((await page.request.post(`${API}/api/v1/auth/login`, { headers: await headers(page), data: { email, password } })).status()).toBe(200); }
async function register(page: Page) {
  const email = `submission-ui-${randomUUID()}@example.test`;
  expect((await page.request.post(`${API}/api/v1/auth/register`, { headers: await headers(page), data: { full_name: "นักศึกษาทดสอบส่งโครงงาน", email, password: PASSWORD } })).status()).toBe(201);
  return email;
}
async function setup(page: Page, withMember = false, accepted = true) {
  const email = await register(page); await login(page, email);
  expect((await page.request.post(`${API}/api/v1/teams`, { headers: await headers(page), data: { name: "ทีมส่งโครงงาน" } })).status()).toBe(201);
  const project = (await (await page.request.post(`${API}/api/v1/projects`, { headers: await headers(page), data: { name: `หัวข้อส่งจริง ${randomUUID().slice(0, 8)}`, description: "แนวคิด ณ เวลาส่ง" } })).json()).data;
  const member = withMember ? await register(page) : null;
  if (member) expect((await page.request.post(`${API}/api/v1/teams/me/members`, { headers: await headers(page), data: { email: member } })).status()).toBe(201);
  if (accepted) {
    const options = (await (await page.request.get(`${API}/api/v1/projects/me/advisor-candidates`)).json()).data;
    const chosen = options.find((r: { full_name: string }) => r.full_name === `อาจารย์ทดสอบ A ${tag!.slice(0, 6)}`);
    const invitation = (await (await page.request.post(`${API}/api/v1/projects/me/advisor-invitations`, { headers: await headers(page), data: { advisor_id: chosen.id } })).json()).data;
    await login(page, advisor, STAFF_PASSWORD);
    expect((await page.request.post(`${API}/api/v1/advisor-invitations/${invitation.id}/respond`, { headers: await headers(page), data: { decision: "accepted" } })).status()).toBe(200);
    await login(page, email);
  }
  return { email, member, project };
}
async function choose(page: Page, buffer = pdf(), name = "proposal.pdf") { await page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true }).setInputFiles({ name, mimeType: "application/pdf", buffer }); }
async function upload(page: Page) {
  await choose(page); await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("ส่งโครงงานแล้ว");
  return (await (await page.request.get(ROOT)).json()).data[0] as { id: string; snapshot_name: string };
}
test.beforeEach(async ({ page }) => { await page.route("**/api/v1/**", route => { if (new URL(route.request().url()).origin !== API) throw new Error("Unexpected API origin"); return route.continue(); }); });

test("real upload snapshot download advisor revision and new round survive refresh", async ({ page }) => {
  const owner = await setup(page);
  await page.goto("/projects"); await page.getByRole("link", { name: "ส่งโครงงานและประวัติ →", exact: true }).click();
  const first = await upload(page); const card = page.getByTestId(`submission-${first.id}`);
  await expect(card).toContainText(owner.project.name); await page.reload(); await expect(card).toContainText("รออาจารย์ตรวจ");
  const downloadEvent = page.waitForEvent("download"); await card.getByRole("button", { name: "ดาวน์โหลดไฟล์" }).click();
  const download = await downloadEvent; expect(download.suggestedFilename()).toBe(`submission-${first.id}.pdf`);
  expect(await readFile((await download.path())!)).toEqual(pdf());
  await login(page, advisor, STAFF_PASSWORD); await page.goto("/"); await page.getByRole("link", { name: "ตรวจโครงงานที่ปรึกษา →", exact: true }).click();
  const review = page.getByTestId(`submission-${first.id}`);
  await review.getByLabel("ผลตรวจ", { exact: true }).selectOption("revision_requested");
  await review.getByRole("button", { name: "บันทึกผลตรวจ", exact: true }).click(); await expect(review.getByRole("alert")).toContainText("กรุณาระบุคำแนะนำ");
  await review.getByLabel("คำแนะนำ (จำเป็น)", { exact: true }).fill("ปรับขอบเขตแล้วส่งรอบใหม่");
  await review.getByRole("button", { name: "บันทึกผลตรวจ", exact: true }).click();
  await review.getByRole("button", { name: "ยกเลิก", exact: true }).click(); await expect(review.getByRole("button", { name: "ยืนยันผลตรวจ" })).toHaveCount(0);
  await review.getByRole("button", { name: "บันทึกผลตรวจ", exact: true }).click(); await review.getByRole("button", { name: "ยืนยันผลตรวจ", exact: true }).click();
  await expect(review).toContainText("ขอแก้ไข"); await expect(review.getByRole("button", { name: "บันทึกผลตรวจ" })).toHaveCount(0);
  await login(page, owner.email); await page.goto("/projects/submissions"); const second = await upload(page);
  expect(second.id).not.toBe(first.id); await expect(page.getByTestId(`submission-${first.id}`)).toContainText("ปรับขอบเขตแล้วส่งรอบใหม่");
});

test("advisor approval closes upload and a member reads without an upload form", async ({ page }) => {
  const owner = await setup(page, true); await page.goto("/projects/submissions"); const row = await upload(page);
  await login(page, advisor, STAFF_PASSWORD); await page.goto("/advisor/submissions"); const card = page.getByTestId(`submission-${row.id}`);
  await card.getByRole("button", { name: "บันทึกผลตรวจ", exact: true }).click(); await card.getByRole("button", { name: "ยืนยันผลตรวจ" }).click();
  await expect(card).toContainText("อาจารย์อนุมัติแล้ว");
  await login(page, owner.member!); await page.goto("/projects/submissions"); await expect(page.getByTestId(`submission-${row.id}`)).toContainText("อาจารย์อนุมัติแล้ว");
  await expect(page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true })).toHaveCount(0);
  await expect(page.getByText("เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ส่งโครงงานได้", { exact: true })).toBeVisible();
});

test("missing prerequisites and wrong roles never expose write forms", async ({ page }) => {
  const email = await register(page); await login(page, email); await page.goto("/projects/submissions"); await expect(page.getByRole("heading", { name: "ต้องมีทีมก่อนส่งโครงงาน" })).toBeVisible();
  await setup(page, false, false); await page.goto("/projects/submissions"); await expect(page.getByText("ยังส่งรอบใหม่ไม่ได้", { exact: false })).toBeVisible();
  await expect(page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true })).toHaveCount(0);
  await login(page, advisor, STAFF_PASSWORD); await page.goto("/projects/submissions"); await expect(page.getByRole("heading", { name: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้" })).toBeVisible();
});

test("client size checks and real invalid content never write a submission", async ({ page }) => {
  await setup(page); await page.goto("/projects/submissions");
  await choose(page, Buffer.alloc(4_000_001)); await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click(); await expect(alerts(page)).toContainText("1–4,000,000");
  await choose(page, Buffer.from("%PDF-fake")); await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click(); await expect(alerts(page)).toContainText("ไฟล์ไม่ใช่เอกสาร");
  expect((await (await page.request.get(ROOT)).json()).data).toEqual([]);
  await expect(page.getByRole("button", { name: "ส่งโครงงาน", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ตรวจประวัติอีกครั้ง", exact: true }).click(); await expect(page.getByRole("button", { name: "ส่งโครงงาน", exact: true })).toBeEnabled();
});

test("lost upload response reconciles with history without replaying the POST", async ({ page }) => {
  await setup(page); let writes = 0;
  await page.route(ROOT, async route => { if (route.request().method() !== "POST") return route.continue(); writes++; expect((await route.fetch()).status()).toBe(201); await route.abort(); });
  await page.goto("/projects/submissions"); await choose(page); await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click();
  await expect(alerts(page)).toContainText("ตรวจประวัติ"); await expect(page.getByRole("button", { name: "ส่งโครงงาน", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "ตรวจประวัติอีกครั้ง", exact: true }).click(); await expect(page.locator('[data-testid^="submission-"]')).toHaveCount(1); expect(writes).toBe(1);
});

test("failed or malformed history does not become an empty upload screen", async ({ page }) => {
  await setup(page); await page.route(ROOT, route => route.fulfill({ status: 200, json: { data: [{ id: "not-a-submission" }] } }));
  await page.goto("/projects/submissions"); await expect(page.getByRole("heading", { name: "ยังโหลดประวัติไม่ได้" })).toBeVisible(); await expect(page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true })).toHaveCount(0);
  await page.unroute(ROOT); await page.getByRole("button", { name: "ลองอีกครั้ง", exact: true }).click(); await expect(page.getByLabel("ไฟล์โครงงาน PDF หรือ PPTX", { exact: true })).toBeVisible();
});

test("mobile pending upload sends once and fits the viewport", async ({ page }) => {
  await setup(page); await page.setViewportSize({ width: 390, height: 844 }); let writes = 0; let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(ROOT, async route => { if (route.request().method() !== "POST") return route.continue(); writes++; await gate; await route.continue(); });
  await page.goto("/projects/submissions"); await choose(page); await page.getByRole("button", { name: "ส่งโครงงาน", exact: true }).click();
  try { await expect(page.getByRole("button", { name: "กำลังส่ง…", exact: true })).toBeDisabled(); expect(writes).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally { release(); }
  await expect(page.getByRole("status")).toContainText("ส่งโครงงานแล้ว"); expect(writes).toBe(1);
});
