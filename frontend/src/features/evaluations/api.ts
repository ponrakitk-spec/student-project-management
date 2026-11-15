import type { Project } from "@/features/committee-assignments/api";

export type Mode = "committee" | "team" | "advisor" | "coordinator";
export type Evaluation = { id: string; score: number; comment: string; created_at: string };
export type Summary = { total_score: string; average_score: number };
export type Committee = { project: Project; summary: Summary | null; can_evaluate: boolean;
  blocking_reason: "NO_SUBMISSION" | "TOPIC_NOT_APPROVED" | "COMPLETED_MILESTONE_REQUIRED" | "ALREADY_EVALUATED" | null;
  own_evaluation: Evaluation | null };
export type Reader = { project: Project; summary: Summary | null };
export type Coordinator = Reader & { evaluations: (Evaluation & { advisor: { id: string; full_name: string } })[] };
export type Context = { kind: "committee"; data: Committee } | { kind: "reader"; data: Reader } | { kind: "coordinator"; data: Coordinator };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export class EvaluationApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "EvaluationApiError"; }
}
function object(value: unknown): Record<string, unknown> | null { return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; }
function id(value: unknown): value is string { return typeof value === "string" && /^[1-9][0-9]{0,18}$/.test(value) && (value.length < 19 || value <= "9223372036854775807"); }
function keys(value: Record<string, unknown>, expected: string[]) { return Object.keys(value).sort().join(",") === expected.slice().sort().join(","); }
function score(value: unknown): value is number { return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 100; }
function time(value: unknown): value is string { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value) && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)); }
function project(value: unknown): value is Project {
  const row = object(value), team = object(row?.team);
  return Boolean(row && id(row.id) && typeof row.name === "string" && (row.description === null || typeof row.description === "string")
    && team && id(team.id) && typeof team.name === "string");
}
function evaluation(value: unknown): value is Evaluation {
  const row = object(value);
  return Boolean(row && id(row.id) && score(row.score) && typeof row.comment === "string" && row.comment.length > 0 && time(row.created_at));
}
function summary(value: unknown): value is Summary | null {
  if (value === null) return true;
  const row = object(value);
  return Boolean(row && keys(row, ["total_score", "average_score"]) && typeof row.total_score === "string"
    && /^(0|[1-9][0-9]*)$/.test(row.total_score) && score(row.average_score));
}
function invalid(): never { throw new EvaluationApiError(502, "INVALID_RESPONSE"); }
async function request(path: string, signal?: AbortSignal, body?: object): Promise<unknown> {
  const csrf = typeof document === "undefined" ? undefined : document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const response = await fetch(`${BASE}${path}`, { method: body ? "POST" : "GET", signal, credentials: "include", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: JSON.stringify(body) } : {}) });
  const json = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(json?.error);
    throw new EvaluationApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED");
  }
  if (response.status !== (body ? 201 : 200) || !json || !("data" in json)) return invalid();
  return json.data;
}
function checkedId(value: string) { if (!id(value)) throw new EvaluationApiError(422, "VALIDATION_ERROR"); return value; }
export async function context(mode: Mode, projectId: string | undefined, signal?: AbortSignal): Promise<Context> {
  const path = mode === "team" ? "/api/v1/projects/me/evaluations" : `/api/v1/${mode}/projects/${checkedId(projectId ?? "")}/evaluations`;
  const data = object(await request(path, signal));
  if (!data || !project(data.project) || (projectId && data.project.id !== projectId) || !summary(data.summary)) return invalid();
  if (mode === "committee") {
    if (!keys(data, ["project", "summary", "can_evaluate", "blocking_reason", "own_evaluation"]) || typeof data.can_evaluate !== "boolean"
      || ![null, "NO_SUBMISSION", "TOPIC_NOT_APPROVED", "COMPLETED_MILESTONE_REQUIRED", "ALREADY_EVALUATED"].includes(data.blocking_reason as string | null)
      || (data.own_evaluation !== null && (!evaluation(data.own_evaluation) || !keys(object(data.own_evaluation)!, ["id", "score", "comment", "created_at"])))) return invalid();
    if (data.can_evaluate !== (data.blocking_reason === null) || (data.can_evaluate && data.own_evaluation !== null)
      || (data.own_evaluation !== null && data.blocking_reason !== "ALREADY_EVALUATED") || (data.summary !== null && data.own_evaluation === null)) return invalid();
    return { kind: "committee", data: data as unknown as Committee };
  }
  if (mode === "coordinator") {
    if (!keys(data, ["project", "summary", "evaluations"]) || !Array.isArray(data.evaluations)
      || (data.summary === null ? data.evaluations.length !== 0 : data.evaluations.length === 0)) return invalid();
    for (const value of data.evaluations) {
      const row = object(value), advisor = object(row?.advisor);
      if (!evaluation(value) || !row || !keys(row, ["id", "advisor", "score", "comment", "created_at"])
        || !advisor || !id(advisor.id) || typeof advisor.full_name !== "string") return invalid();
    }
    if (new Set(data.evaluations.map((row: Evaluation) => row.id)).size !== data.evaluations.length) return invalid();
    return { kind: "coordinator", data: data as unknown as Coordinator };
  }
  if (!keys(data, ["project", "summary"])) return invalid();
  return { kind: "reader", data: data as unknown as Reader };
}
export async function record(projectId: string, value: number, comment: string, signal?: AbortSignal): Promise<Evaluation> {
  const data = await request(`/api/v1/committee/projects/${checkedId(projectId)}/evaluations`, signal, { score: value, comment });
  if (!evaluation(data) || !keys(object(data)!, ["id", "score", "comment", "created_at"]) || data.score !== value || data.comment !== comment) return invalid();
  return data;
}
export const BLOCKING: Record<string, string> = { NO_SUBMISSION: "ยังไม่มีรอบส่งหัวข้อ", TOPIC_NOT_APPROVED: "หัวข้อโครงงานยังไม่ผ่านการอนุมัติจากกรรมการ",
  COMPLETED_MILESTONE_REQUIRED: "ต้องมี Milestone ที่เสร็จสมบูรณ์อย่างน้อย 1 รายการก่อนประเมิน", ALREADY_EVALUATED: "คุณประเมินโครงงานนี้แล้ว ไม่สามารถแก้ไขหรือลบได้" };
export function errorMessage(cause: unknown): string {
  if (!(cause instanceof EvaluationApiError)) return "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้งก่อนทำรายการซ้ำ";
  return ({ AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", EVALUATION_ACCESS_FORBIDDEN: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้",
    EVALUATION_READER_ACCESS_FORBIDDEN: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", COMMITTEE_PROJECT_NOT_FOUND: "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ",
    PROJECT_NOT_FOUND: "ไม่พบโครงงานที่คุณเข้าถึงได้", TEAM_NOT_FOUND: "ไม่พบทีมปัจจุบันของคุณ", EVALUATION_ALREADY_RECORDED: BLOCKING.ALREADY_EVALUATED,
    TOPIC_NOT_APPROVED: BLOCKING.TOPIC_NOT_APPROVED, COMPLETED_MILESTONE_REQUIRED: BLOCKING.COMPLETED_MILESTONE_REQUIRED,
    CSRF_INVALID: "ข้อมูลยืนยันคำขอไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่", ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้",
    VALIDATION_ERROR: "กรุณาตรวจสอบคะแนนและความคิดเห็น", INTERNAL_ERROR: "ระบบยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง",
    INVALID_RESPONSE: "ข้อมูลตอบกลับไม่ถูกต้อง กรุณาตรวจข้อมูลอีกครั้ง"
  } as Record<string, string>)[cause.code] ?? "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง";
}
