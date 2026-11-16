export type SubmissionStatus = "pending_review" | "approved" | "revision_requested";
export type Submission = { id: string; project_id: string; submitted_by: string; submitted_at: string;
  snapshot_name: string; snapshot_description: string | null; status: SubmissionStatus; reviewed_by: string | null;
  reviewed_at: string | null; review_comment: string | null; original_filename: string; mime_type: string; team_name: string };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TEAM = "/api/v1/projects/me/submissions";
export const MAX_FILE_BYTES = 4_000_000;
export const STATUS_TEXT = { pending_review: "รออาจารย์ตรวจ", approved: "อาจารย์อนุมัติแล้ว", revision_requested: "ขอแก้ไข" };
export class SubmissionApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "SubmissionApiError"; }
}
function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function id(value: unknown): value is string { return typeof value === "string" && /^[1-9]\d{0,18}$/.test(value) && (value.length < 19 || value <= "9223372036854775807"); }
function time(value: unknown): value is string { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value) && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)); }
function submission(value: unknown): value is Submission {
  const r = object(value);
  return Boolean(r && id(r.id) && id(r.project_id) && id(r.submitted_by) && time(r.submitted_at)
    && typeof r.snapshot_name === "string" && (r.snapshot_description === null || typeof r.snapshot_description === "string")
    && typeof r.team_name === "string" && typeof r.original_filename === "string"
    && ["application/pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation"].includes(String(r.mime_type))
    && (r.review_comment === null || typeof r.review_comment === "string")
    && (r.status === "pending_review" ? r.reviewed_by === null && r.reviewed_at === null && r.review_comment === null
      : ["approved", "revision_requested"].includes(String(r.status)) && id(r.reviewed_by) && time(r.reviewed_at)
        && (r.status !== "revision_requested" || typeof r.review_comment === "string" && r.review_comment.trim().length > 0)));
}
function invalid(): never { throw new SubmissionApiError(502, "INVALID_RESPONSE"); }
async function checked(response: Response, expected: number): Promise<unknown> {
  const json = object(await response.json().catch(() => null));
  if (!response.ok) { const error = object(json?.error); throw new SubmissionApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED"); }
  if (response.status !== expected || !json || !("data" in json)) return invalid();
  return json.data;
}
function csrf(): Record<string, string> {
  const token = document.cookie.split(";").map(p => p.trim()).find(p => p.startsWith("spms_csrf="))?.slice(10);
  return token ? { "X-CSRF-Token": token } : {};
}
async function list(path: string, signal?: AbortSignal): Promise<Submission[]> {
  const data = await checked(await fetch(`${BASE}${path}`, { signal, credentials: "include", cache: "no-store" }), 200);
  if (!Array.isArray(data) || !data.every(submission) || new Set(data.map(r => r.id)).size !== data.length) return invalid();
  return data;
}
export const teamHistory = (signal?: AbortSignal) => list(TEAM, signal);
export const advisorHistory = (signal?: AbortSignal) => list("/api/v1/advisor/submissions", signal);
export async function eligibility(signal?: AbortSignal): Promise<boolean> {
  const data = object(await checked(await fetch(`${BASE}${TEAM}/eligibility`, { signal, credentials: "include", cache: "no-store" }), 200));
  if (typeof data?.can_submit !== "boolean") return invalid();
  return data.can_submit;
}
export async function uploadSubmission(file: File, signal?: AbortSignal): Promise<Submission> {
  const form = new FormData(); form.append("file", file);
  const data = await checked(await fetch(`${BASE}${TEAM}`, { method: "POST", body: form, headers: csrf(), signal, credentials: "include", cache: "no-store" }), 201);
  if (!submission(data) || data.status !== "pending_review") return invalid();
  return data;
}
export async function reviewSubmission(row: Submission, decision: "approved" | "revision_requested", comment: string | null, signal?: AbortSignal): Promise<Submission> {
  if (!id(row.id)) return invalid();
  const data = await checked(await fetch(`${BASE}/api/v1/project-submissions/${row.id}/review`, { method: "POST", signal,
    credentials: "include", cache: "no-store", headers: { "Content-Type": "application/json", ...csrf() }, body: JSON.stringify({ decision, comment }) }), 200);
  if (!submission(data) || data.id !== row.id || data.project_id !== row.project_id || data.status !== decision) return invalid();
  return data;
}
export async function downloadSubmission(row: Submission, signal?: AbortSignal): Promise<void> {
  if (!id(row.id)) return invalid();
  const response = await fetch(`${BASE}/api/v1/project-submissions/${row.id}/file`, { signal, credentials: "include", cache: "no-store" });
  if (!response.ok) { await checked(response, 200); return; }
  if (response.status !== 200 || response.headers.get("content-type") !== row.mime_type) return invalid();
  const blob = await response.blob();
  if (blob.size < 1 || blob.size > MAX_FILE_BYTES || signal?.aborted) return invalid();
  const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = `submission-${row.id}.${row.mime_type === "application/pdf" ? "pdf" : "pptx"}`;
  document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function submissionErrorMessage(cause: unknown): string {
  if (!(cause instanceof SubmissionApiError)) return "ไม่สามารถยืนยันผลได้ กรุณาตรวจประวัติก่อนทำรายการอีกครั้ง";
  return ({ FILE_EMPTY: "ไฟล์ว่างเปล่า", FILE_TOO_LARGE: "ไฟล์ต้องมีขนาดไม่เกิน 4,000,000 ไบต์", FILE_TYPE_UNSUPPORTED: "รองรับเฉพาะ PDF หรือ PPTX",
    FILE_TYPE_MISMATCH: "ชนิดไฟล์ไม่ตรงกับนามสกุลหรือเนื้อหา", FILE_CONTENT_INVALID: "ไฟล์ไม่ใช่เอกสาร PDF/PPTX ที่อ่านได้", FILE_NAME_INVALID: "ชื่อไฟล์ไม่ถูกต้อง",
    ACCEPTED_ADVISOR_REQUIRED: "ต้องมีอาจารย์ตอบรับก่อนส่ง", SUBMISSION_PENDING: "มีรอบที่กำลังรอตรวจอยู่แล้ว", SUBMISSION_PHASE_CLOSED: "ขั้นตอนปัจจุบันยังไม่อนุญาตให้ส่งรอบใหม่",
    SUBMISSION_ALREADY_REVIEWED: "รอบนี้ได้รับการตรวจแล้ว กรุณาโหลดประวัติใหม่", SUBMISSION_ACTION_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ส่งได้",
    SUBMISSION_ACCESS_FORBIDDEN: "บทบาทของคุณไม่มีสิทธิ์ทำรายการนี้", SUBMISSION_NOT_FOUND: "ไม่พบรอบส่งที่คุณมีสิทธิ์เข้าถึง", CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
    AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูล", INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาตรวจประวัติอีกครั้ง",
  } as Record<string, string>)[cause.code] ?? "ไม่สามารถยืนยันผลได้ กรุณาตรวจประวัติก่อนทำรายการอีกครั้ง";
}
