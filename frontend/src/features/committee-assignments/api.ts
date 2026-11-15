export type Advisor = { id: string; full_name: string };
export type Project = { id: string; name: string; description: string | null; team: { id: string; name: string } };
export type Assignment = { id: string; advisor: Advisor; assigned_at: string };
export type Detail = { project: Project; roster_locked: boolean; assignments: Assignment[] };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ROOT = "/api/v1/coordinator/projects";

export class CommitteeApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "CommitteeApiError"; }
}
function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function id(value: unknown): value is string {
  return typeof value === "string" && /^[1-9][0-9]{0,18}$/.test(value) && (value.length < 19 || value <= "9223372036854775807");
}
function advisor(value: unknown): value is Advisor {
  const row = object(value); return Boolean(row && id(row.id) && typeof row.full_name === "string");
}
function project(value: unknown): value is Project {
  const row = object(value), team = object(row?.team);
  return Boolean(row && id(row.id) && typeof row.name === "string" && (row.description === null || typeof row.description === "string")
    && team && id(team.id) && typeof team.name === "string");
}
function assignment(value: unknown): value is Assignment {
  const row = object(value);
  return Boolean(row && id(row.id) && advisor(row.advisor) && typeof row.assigned_at === "string"
    && /(Z|[+-]\d{2}:\d{2})$/.test(row.assigned_at) && Number.isFinite(Date.parse(row.assigned_at)));
}
function invalid(): never { throw new CommitteeApiError(502, "INVALID_RESPONSE"); }
function array<T extends { id: string }>(value: unknown, check: (item: unknown) => item is T): T[] {
  if (!Array.isArray(value) || !value.every(check) || new Set(value.map((row) => row.id)).size !== value.length) return invalid();
  return value;
}
function path(projectId: string) {
  if (!id(projectId)) throw new CommitteeApiError(422, "VALIDATION_ERROR");
  return `${ROOT}/${projectId}`;
}
async function request(url: string, signal?: AbortSignal, method = "GET", body?: object, expected = 200): Promise<unknown> {
  const csrf = typeof document === "undefined" ? undefined : document.cookie.split(";").map((part) => part.trim())
    .find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const response = await fetch(`${BASE}${url}`, { method, signal, credentials: "include", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: JSON.stringify(body) } : {}) });
  if (response.ok && expected === 204) {
    if (response.status !== 204 || (await response.text()) !== "") return invalid();
    return undefined;
  }
  const json = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(json?.error);
    throw new CommitteeApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED");
  }
  if (response.status !== expected || !json || !("data" in json)) return invalid();
  return json.data;
}
export async function projects(signal?: AbortSignal): Promise<Project[]> { return array(await request(ROOT, signal), project); }
export async function detail(projectId: string, signal?: AbortSignal): Promise<Detail> {
  const data = object(await request(`${path(projectId)}/committee`, signal));
  if (!data || !project(data.project) || data.project.id !== projectId || typeof data.roster_locked !== "boolean") return invalid();
  const assignments = array(data.assignments, assignment);
  if (new Set(assignments.map((row) => row.advisor.id)).size !== assignments.length) return invalid();
  return { project: data.project, roster_locked: data.roster_locked, assignments };
}
export async function candidates(projectId: string, signal?: AbortSignal): Promise<Advisor[]> {
  return array(await request(`${path(projectId)}/committee-candidates`, signal), advisor);
}
export async function appoint(projectId: string, advisorId: string, signal?: AbortSignal): Promise<Assignment> {
  if (!id(advisorId)) return invalid();
  const data = await request(`${path(projectId)}/committee`, signal, "POST", { advisor_id: advisorId }, 201);
  if (!assignment(data) || data.advisor.id !== advisorId) return invalid();
  return data;
}
export async function replace(projectId: string, assignmentId: string, advisorId: string, signal?: AbortSignal): Promise<Assignment> {
  if (!id(assignmentId) || !id(advisorId)) return invalid();
  const data = await request(`${path(projectId)}/committee/${assignmentId}`, signal, "PATCH", { advisor_id: advisorId });
  if (!assignment(data) || data.id !== assignmentId || data.advisor.id !== advisorId) return invalid();
  return data;
}
export async function remove(projectId: string, assignmentId: string, signal?: AbortSignal): Promise<void> {
  if (!id(assignmentId)) return invalid();
  await request(`${path(projectId)}/committee/${assignmentId}/remove`, signal, "POST", {}, 204);
}
export function errorMessage(cause: unknown): string {
  if (!(cause instanceof CommitteeApiError)) return "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้งก่อนทำรายการซ้ำ";
  return ({ AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", COMMITTEE_ACCESS_FORBIDDEN: "เฉพาะผู้ประสานงานเท่านั้นที่ใช้หน้านี้ได้",
    PROJECT_NOT_FOUND: "ไม่พบโครงงานที่คุณเข้าถึงได้", COMMITTEE_ASSIGNMENT_NOT_FOUND: "ไม่พบรายการแต่งตั้ง กรุณาตรวจข้อมูลใหม่",
    COMMITTEE_ADVISOR_NOT_FOUND: "ไม่พบอาจารย์ที่แต่งตั้งได้", COMMITTEE_ROSTER_LOCKED: "รายชื่อกรรมการล็อกแล้วหลังเริ่มลงมติ",
    PROJECT_ADVISOR_INELIGIBLE: "อาจารย์ที่ปรึกษาเป็นกรรมการของโครงงานเดียวกันไม่ได้",
    COMMITTEE_ADVISOR_ALREADY_ASSIGNED: "อาจารย์ท่านนี้อยู่ในรายชื่อกรรมการแล้ว", CSRF_INVALID: "ข้อมูลยืนยันคำขอไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่",
    ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้", VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูลกรรมการ",
    INTERNAL_ERROR: "ระบบยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง", INVALID_RESPONSE: "ข้อมูลตอบกลับไม่ถูกต้อง กรุณาตรวจข้อมูลอีกครั้ง"
  } as Record<string, string>)[cause.code] ?? "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้งก่อนทำรายการซ้ำ";
}
