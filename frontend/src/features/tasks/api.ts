import { isMilestone, type Milestone } from "@/features/milestones/api";
export type TaskStatus = "not_started" | "in_progress" | "completed";
export type Task = { id: string; milestone_id: string; name: string; description: string | null; due_date: string | null; status: TaskStatus;
  created_at: string; updated_at: string; created_by: string; updated_by: string | null; completed_at: string | null };
export type TaskFields = { name: string; description: string | null; due_date: string | null };
export type TaskList = { milestone: Milestone; can_manage: boolean; tasks: Task[] };
export type Assignee = { id: string; team_member_id: string; user: { id: string; full_name: string }; assigned_at: string };
export type AssignmentHistory = { id: string; user: { id: string; full_name: string }; assigned_at: string; unassigned_at: string };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const STATUS_TEXT = { not_started: "ยังไม่เริ่ม", in_progress: "กำลังดำเนินการ", completed: "เสร็จแล้ว" };
export class TaskApiError extends Error { constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "TaskApiError"; } }
function object(v: unknown): Record<string, unknown> | null { return v !== null && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : null; }
export function validId(v: unknown): v is string { return typeof v === "string" && /^[1-9]\d{0,18}$/.test(v) && (v.length < 19 || v <= "9223372036854775807"); }
function time(v: unknown): v is string { return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v) && /(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v)); }
function task(v: unknown): v is Task {
  const r = object(v); return Boolean(r && validId(r.id) && validId(r.milestone_id) && typeof r.name === "string" && (r.description === null || typeof r.description === "string")
    && (r.due_date === null || typeof r.due_date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(r.due_date)) && ["not_started", "in_progress", "completed"].includes(String(r.status))
    && time(r.created_at) && time(r.updated_at) && validId(r.created_by) && (r.updated_by === null || validId(r.updated_by))
    && (r.status === "completed" ? time(r.completed_at) : r.completed_at === null));
}
function user(v: unknown): boolean { const r = object(v); return Boolean(r && validId(r.id) && typeof r.full_name === "string"); }
function assignee(v: unknown): v is Assignee { const r = object(v); return Boolean(r && validId(r.id) && validId(r.team_member_id) && user(r.user) && time(r.assigned_at)); }
function history(v: unknown): v is AssignmentHistory { const r = object(v); return Boolean(r && validId(r.id) && user(r.user) && time(r.assigned_at) && time(r.unassigned_at)); }
function invalid(): never { throw new TaskApiError(502, "INVALID_RESPONSE"); }
function path(id: string): string { if (!validId(id)) return invalid(); return `/api/v1/tasks/${id}`; }
async function request(url: string, method = "GET", body?: object, signal?: AbortSignal, expectedStatus = method === "POST" ? 201 : 200): Promise<unknown> {
  const token = typeof document === "undefined" ? undefined : document.cookie.split(";").map(p => p.trim()).find(p => p.startsWith("spms_csrf="))?.slice(10);
  const response = await fetch(`${BASE}${url}`, { method, signal, credentials: "include", cache: "no-store", headers: {
    ...(body ? { "Content-Type": "application/json" } : {}), ...(method !== "GET" && token ? { "X-CSRF-Token": token } : {}),
  }, ...(body ? { body: JSON.stringify(body) } : {}) });
  if (method === "DELETE" && response.status === 204) return;
  const json = object(await response.json().catch(() => null));
  if (!response.ok) { const e = object(json?.error); throw new TaskApiError(response.status, typeof e?.code === "string" ? e.code : "REQUEST_FAILED"); }
  if (response.status !== expectedStatus || method === "DELETE" || !json || !("data" in json)) return invalid();
  return json.data;
}
export async function listTasks(milestone: string, signal?: AbortSignal): Promise<TaskList> {
  if (!validId(milestone)) return invalid();
  const data = object(await request(`/api/v1/milestones/${milestone}/tasks`, "GET", undefined, signal));
  if (!data || !isMilestone(data.milestone) || data.milestone.id !== milestone || typeof data.can_manage !== "boolean" || !Array.isArray(data.tasks) || !data.tasks.every(task)
    || data.tasks.some(t => t.milestone_id !== milestone) || new Set(data.tasks.map(t => t.id)).size !== data.tasks.length) return invalid();
  return data as TaskList;
}
export async function currentTask(id: string, milestone: string, signal?: AbortSignal): Promise<Task> {
  const data = await request(path(id), "GET", undefined, signal);
  if (!task(data) || data.id !== id || data.milestone_id !== milestone) return invalid(); return data;
}
export async function saveTask(milestone: string, fields: Partial<TaskFields>, row?: Task, signal?: AbortSignal): Promise<Task> {
  if (!validId(milestone)) return invalid();
  const data = await request(row ? path(row.id) : `/api/v1/milestones/${milestone}/tasks`, row ? "PATCH" : "POST", fields, signal);
  if (!task(data) || data.milestone_id !== milestone || row && (data.id !== row.id || data.created_by !== row.created_by)) return invalid(); return data;
}
export async function setTaskStatus(row: Task, status: TaskStatus, signal?: AbortSignal): Promise<Task> {
  const data = await request(`${path(row.id)}/status`, "POST", { status }, signal, 200);
  if (!task(data) || data.id !== row.id || data.milestone_id !== row.milestone_id || data.status !== status) return invalid(); return data;
}
export const deleteTask = async (row: Task, signal?: AbortSignal): Promise<void> => { await request(path(row.id), "DELETE", undefined, signal); };
export async function assignees(id: string, signal?: AbortSignal): Promise<Assignee[]> {
  const data = await request(`${path(id)}/assignees`, "GET", undefined, signal);
  if (!Array.isArray(data) || !data.every(assignee) || new Set(data.map(a => a.team_member_id)).size !== data.length) return invalid(); return data;
}
export async function assignmentHistory(id: string, signal?: AbortSignal): Promise<AssignmentHistory[]> {
  const data = await request(`${path(id)}/assignment-history`, "GET", undefined, signal);
  if (!Array.isArray(data) || !data.every(history)) return invalid(); return data;
}
export async function assignTask(id: string, member: string, signal?: AbortSignal): Promise<Assignee> {
  if (!validId(member)) return invalid(); const data = await request(`${path(id)}/assignees`, "POST", { team_member_id: member }, signal);
  if (!assignee(data) || data.team_member_id !== member) return invalid(); return data;
}
export async function unassignTask(id: string, member: string, signal?: AbortSignal): Promise<void> {
  if (!validId(member)) return invalid(); await request(`${path(id)}/assignees/${member}`, "DELETE", undefined, signal);
}
export function taskErrorMessage(cause: unknown): string {
  if (!(cause instanceof TaskApiError)) return "ไม่สามารถยืนยันผลได้ กรุณาโหลดข้อมูลงานก่อนทำใหม่";
  return ({ TASK_NOT_FOUND: "ไม่พบงานที่คุณมีสิทธิ์เข้าถึง", MILESTONE_NOT_FOUND: "ไม่พบแผนงานที่คุณมีสิทธิ์เข้าถึง", TASK_ACCESS_FORBIDDEN: "หน้านี้สำหรับนักศึกษา",
    TASK_ACTION_FORBIDDEN: "คุณไม่มีสิทธิ์ทำรายการนี้", TASK_LOCKED: "งานหรือการมอบหมายถูกล็อกในขั้นตอนปัจจุบัน", TASK_COMPLETED: "หัวหน้าต้องเปิดงานที่เสร็จแล้วกลับก่อนแก้ไขหรือลบ",
    TASK_DUE_DATE_INVALID: "วันกำหนดส่งต้องไม่ก่อนวันนี้ตามเวลาไทยและไม่เกินวันแผนงาน", TASK_NAME_CONFLICT: "ชื่องานซ้ำในแผนงานนี้", TASK_ASSIGNEE_REQUIRED: "ต้องมีผู้รับผิดชอบอย่างน้อยหนึ่งคน",
    TASK_STATUS_CONFLICT: "ไม่สามารถเปลี่ยนสถานะตามที่เลือกได้", ASSIGNEE_ALREADY_ASSIGNED: "สมาชิกคนนี้เป็นผู้รับผิดชอบอยู่แล้ว", ASSIGNEE_NOT_CURRENT_MEMBER: "ผู้รับผิดชอบต้องเป็นสมาชิกปัจจุบันของทีมนี้",
    ASSIGNEE_NOT_FOUND: "ไม่พบผู้รับผิดชอบรายการนี้", CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบใหม่", VALIDATION_ERROR: "กรุณาตรวจข้อมูลงาน",
    INTERNAL_ERROR: "ระบบงานยังไม่พร้อมใช้งาน กรุณาโหลดข้อมูลก่อนทำใหม่" } as Record<string, string>)[cause.code] ?? "ไม่สามารถยืนยันผลได้ กรุณาโหลดข้อมูลงานก่อนทำใหม่";
}
