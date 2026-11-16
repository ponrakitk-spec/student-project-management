export type Milestone = { id: string; project_id: string; name: string; description: string | null; due_date: string;
  status: "not_started" | "in_progress" | "completed"; created_at: string; updated_at: string; created_by: string; updated_by: string | null; completed_at: string | null };
export type MilestoneList = { project_id: string; can_manage: boolean; milestones: Milestone[] };
export type MilestoneFields = { name: string; description: string | null; due_date: string };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ROOT = "/api/v1/projects/me/milestones";
export const STATUS_TEXT = { not_started: "ยังไม่เริ่ม", in_progress: "กำลังดำเนินการ", completed: "เสร็จแล้ว" };
export class MilestoneApiError extends Error { constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "MilestoneApiError"; } }
function object(v: unknown): Record<string, unknown> | null { return v !== null && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : null; }
function id(v: unknown): v is string { return typeof v === "string" && /^[1-9]\d{0,18}$/.test(v) && (v.length < 19 || v <= "9223372036854775807"); }
function time(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v) && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v)); }
export function isMilestone(v: unknown): v is Milestone {
  const r = object(v); return Boolean(r && id(r.id) && id(r.project_id) && typeof r.name === "string" && (r.description === null || typeof r.description === "string")
    && typeof r.due_date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(r.due_date) && ["not_started", "in_progress", "completed"].includes(String(r.status))
    && time(r.created_at) && time(r.updated_at) && id(r.created_by) && (r.updated_by === null || id(r.updated_by))
    && (r.status === "completed" ? time(r.completed_at) : r.completed_at === null));
}
function invalid(): never { throw new MilestoneApiError(502, "INVALID_RESPONSE"); }
async function request(path: string, method = "GET", body?: object, signal?: AbortSignal): Promise<unknown> {
  const token = typeof document === "undefined" ? undefined : document.cookie.split(";").map(p => p.trim()).find(p => p.startsWith("spms_csrf="))?.slice(10);
  const response = await fetch(`${BASE}${path}`, { method, signal, credentials: "include", cache: "no-store", headers: {
    ...(body ? { "Content-Type": "application/json" } : {}), ...(method !== "GET" && token ? { "X-CSRF-Token": token } : {}),
  }, ...(body ? { body: JSON.stringify(body) } : {}) });
  if (method === "DELETE" && response.status === 204) return;
  const json = object(await response.json().catch(() => null));
  if (!response.ok) { const e = object(json?.error); throw new MilestoneApiError(response.status, typeof e?.code === "string" ? e.code : "REQUEST_FAILED"); }
  if (response.status !== (method === "POST" ? 201 : 200) || method === "DELETE" || !json || !("data" in json)) return invalid();
  return json.data;
}
export async function listMilestones(signal?: AbortSignal): Promise<MilestoneList> {
  const data = object(await request(ROOT, "GET", undefined, signal));
  if (!data || !id(data.project_id) || typeof data.can_manage !== "boolean" || !Array.isArray(data.milestones) || !data.milestones.every(isMilestone)
    || data.milestones.some(r => r.project_id !== data.project_id) || new Set(data.milestones.map(r => r.id)).size !== data.milestones.length) return invalid();
  return data as MilestoneList;
}
export async function saveMilestone(fields: Partial<MilestoneFields>, current?: Milestone, signal?: AbortSignal): Promise<Milestone> {
  if (current && !id(current.id)) return invalid();
  const data = await request(current ? `/api/v1/milestones/${current.id}` : ROOT, current ? "PATCH" : "POST", fields, signal);
  if (!isMilestone(data) || current && (data.id !== current.id || data.project_id !== current.project_id || data.created_by !== current.created_by)) return invalid();
  return data;
}
export async function deleteMilestone(row: Milestone, signal?: AbortSignal): Promise<void> {
  if (!id(row.id)) return invalid();
  await request(`/api/v1/milestones/${row.id}`, "DELETE", undefined, signal);
}
export function milestoneErrorMessage(cause: unknown): string {
  if (!(cause instanceof MilestoneApiError)) return "ไม่สามารถยืนยันผลได้ กรุณาโหลดรายการก่อนทำใหม่";
  return ({ MILESTONE_NAME_CONFLICT: "ชื่อแผนงานซ้ำในโครงงานนี้", MILESTONE_DUE_DATE_PAST: "วันกำหนดส่งต้องไม่ก่อนวันนี้ตามเวลาไทย",
    MILESTONE_LOCKED: "แผนงานถูกล็อกหลังมีคะแนนประเมินแล้ว", TASK_DUE_DATE_CONFLICT: "ต้องปรับวันกำหนดส่งของงานย่อยก่อนย่อวันแผนงาน",
    MILESTONE_HAS_TASKS: "ลบแผนงานที่มีงานย่อยไม่ได้", MILESTONE_ACTION_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่จัดการได้", MILESTONE_ACCESS_FORBIDDEN: "หน้านี้สำหรับนักศึกษา",
    MILESTONE_NOT_FOUND: "ไม่พบแผนงานที่คุณมีสิทธิ์เข้าถึง", VALIDATION_ERROR: "กรุณาตรวจชื่อ คำอธิบาย และวันกำหนดส่ง", CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
    AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาโหลดรายการอีกครั้ง",
  } as Record<string, string>)[cause.code] ?? "ไม่สามารถยืนยันผลได้ กรุณาโหลดรายการก่อนทำใหม่";
}
