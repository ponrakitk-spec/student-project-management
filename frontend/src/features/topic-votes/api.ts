import type { Project } from "@/features/committee-assignments/api";

export type Decision = "approved" | "revision_requested";
export type Mode = "committee" | "team" | "advisor" | "coordinator";
export type Submission = { id: string; snapshot_name: string; snapshot_description: string | null;
  status: "pending_review" | "approved" | "revision_requested"; submitted_at: string };
export type OwnVote = { id: string; submission_id: string; vote: Decision; comment: string | null; voted_at: string };
type CommitteeRound = { submission: Submission; own_vote: OwnVote | null; decision: Decision | null };
export type CommitteeContext = { project: Project; latest_submission_id: string | null; can_vote: boolean;
  blocking_reason: "NO_SUBMISSION" | "SUBMISSION_NOT_APPROVED" | "COMMITTEE_INCOMPLETE" | "ALREADY_VOTED" | null; rounds: CommitteeRound[] };
type ReaderRound = { submission: Submission; decision: Decision | null; comments: string[] };
export type ReaderContext = { project: Project; committee: { full_name: string }[]; rounds: ReaderRound[] };
type CoordinatorVote = { id: string; advisor: { id: string; full_name: string }; vote: Decision; comment: string | null; voted_at: string };
type CoordinatorRound = { submission: Submission; decision: Decision | null; votes: CoordinatorVote[] };
export type CoordinatorContext = { project: Project; rounds: CoordinatorRound[] };
export type Context = { kind: "committee"; data: CommitteeContext } | { kind: "reader"; data: ReaderContext } | { kind: "coordinator"; data: CoordinatorContext };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export class TopicVoteApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) { super(code); this.name = "TopicVoteApiError"; }
}
function object(value: unknown): Record<string, unknown> | null { return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null; }
function id(value: unknown): value is string { return typeof value === "string" && /^[1-9][0-9]{0,18}$/.test(value) && (value.length < 19 || value <= "9223372036854775807"); }
function decision(value: unknown): value is Decision { return value === "approved" || value === "revision_requested"; }
function time(value: unknown): value is string { return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value) && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)); }
function project(value: unknown): value is Project {
  const row = object(value), team = object(row?.team);
  return Boolean(row && id(row.id) && typeof row.name === "string" && (row.description === null || typeof row.description === "string")
    && team && id(team.id) && typeof team.name === "string");
}
function submission(value: unknown): value is Submission {
  const row = object(value);
  return Boolean(row && id(row.id) && typeof row.snapshot_name === "string" && (row.snapshot_description === null || typeof row.snapshot_description === "string")
    && ["pending_review", "approved", "revision_requested"].includes(String(row.status)) && time(row.submitted_at));
}
function vote(value: unknown): value is OwnVote {
  const row = object(value);
  return Boolean(row && id(row.id) && id(row.submission_id) && decision(row.vote) && (row.comment === null || typeof row.comment === "string") && time(row.voted_at));
}
function invalid(): never { throw new TopicVoteApiError(502, "INVALID_RESPONSE"); }
function rounds(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return invalid();
  const result = value.map(object);
  if (!result.every((row): row is Record<string, unknown> => Boolean(row && submission(row.submission) && (row.decision === null || decision(row.decision))))) return invalid();
  if (new Set(result.map((row) => (row.submission as Submission).id)).size !== result.length) return invalid();
  return result;
}
function checkedId(value: string): string { if (!id(value)) throw new TopicVoteApiError(422, "VALIDATION_ERROR"); return value; }
async function request(path: string, signal?: AbortSignal, body?: object): Promise<unknown> {
  const csrf = typeof document === "undefined" ? undefined : document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const response = await fetch(`${BASE}${path}`, { method: body ? "POST" : "GET", signal, credentials: "include", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: JSON.stringify(body) } : {}) });
  const json = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(json?.error);
    throw new TopicVoteApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED");
  }
  if (response.status !== (body ? 201 : 200) || !json || !("data" in json)) return invalid();
  return json.data;
}
export async function listProjects(mode: "committee" | "advisor", signal?: AbortSignal): Promise<Project[]> {
  const data = await request(`/api/v1/${mode}/projects`, signal);
  if (!Array.isArray(data) || !data.every(project) || new Set(data.map((row) => row.id)).size !== data.length) return invalid();
  return data;
}
export async function context(mode: Mode, projectId?: string, signal?: AbortSignal): Promise<Context> {
  const path = mode === "team" ? "/api/v1/projects/me/committee" : mode === "advisor" ? `/api/v1/advisor/projects/${checkedId(projectId ?? "")}/committee`
    : `/api/v1/${mode}/projects/${checkedId(projectId ?? "")}/topic-votes`;
  const data = object(await request(path, signal));
  if (!data || !project(data.project) || (projectId && data.project.id !== projectId)) return invalid();
  const rows = rounds(data.rounds);
  if (mode === "committee") {
    if ((data.latest_submission_id !== null && !id(data.latest_submission_id)) || typeof data.can_vote !== "boolean"
      || ![null, "NO_SUBMISSION", "SUBMISSION_NOT_APPROVED", "COMMITTEE_INCOMPLETE", "ALREADY_VOTED"].includes(data.blocking_reason as null | string)) return invalid();
    if (data.latest_submission_id !== (rows[0] ? (rows[0].submission as Submission).id : null)) return invalid();
    for (const row of rows) if (row.own_vote !== null && (!vote(row.own_vote) || row.own_vote.submission_id !== (row.submission as Submission).id)) return invalid();
    if (data.can_vote && (!rows[0] || (rows[0].submission as Submission).status !== "approved" || rows[0].own_vote !== null || data.blocking_reason !== null)) return invalid();
    return { kind: "committee", data: data as unknown as CommitteeContext };
  }
  if (mode === "coordinator") {
    for (const row of rows) {
      if ((row.submission as Submission).status !== "approved" || !Array.isArray(row.votes)) return invalid();
      const votes = row.votes.map(object);
      if (!votes.every((item) => item && id(item.id) && decision(item.vote) && (item.comment === null || typeof item.comment === "string")
        && time(item.voted_at) && id(object(item.advisor)?.id) && typeof object(item.advisor)?.full_name === "string")) return invalid();
      if (new Set(votes.map((item) => item!.id)).size !== votes.length) return invalid();
    }
    return { kind: "coordinator", data: data as unknown as CoordinatorContext };
  }
  if (!Array.isArray(data.committee) || !data.committee.every((row) => typeof object(row)?.full_name === "string")) return invalid();
  for (const row of rows) if (!Array.isArray(row.comments) || !row.comments.every((item) => typeof item === "string") || (row.decision === null && row.comments.length !== 0)) return invalid();
  return { kind: "reader", data: data as unknown as ReaderContext };
}
export async function castVote(projectId: string, submissionId: string, choice: Decision, comment: string | null, signal?: AbortSignal): Promise<OwnVote> {
  const data = await request(`/api/v1/committee/projects/${checkedId(projectId)}/topic-votes`, signal,
    { submission_id: checkedId(submissionId), vote: choice, comment });
  if (!vote(data) || data.submission_id !== submissionId || data.vote !== choice) return invalid();
  return data;
}
export const DECISIONS = { approved: "ผ่าน", revision_requested: "ขอแก้ไข" };
export const BLOCKING: Record<string, string> = { NO_SUBMISSION: "ยังไม่มีรอบส่งหัวข้อ", SUBMISSION_NOT_APPROVED: "รอบล่าสุดยังไม่ผ่านการอนุมัติจากอาจารย์",
  COMMITTEE_INCOMPLETE: "ต้องมีกรรมการอย่างน้อย 3 คนก่อนลงมติ", ALREADY_VOTED: "คุณลงมติรอบนี้แล้ว ไม่สามารถแก้ไขได้" };
export function errorMessage(cause: unknown): string {
  if (!(cause instanceof TopicVoteApiError)) return "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้งก่อนทำรายการซ้ำ";
  return ({ AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง", VOTE_ACCESS_FORBIDDEN: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้",
    COMMITTEE_READER_ACCESS_FORBIDDEN: "บทบาทของคุณไม่สามารถใช้หน้านี้ได้", COMMITTEE_PROJECT_NOT_FOUND: "ไม่พบโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ",
    PROJECT_NOT_FOUND: "ไม่พบโครงงานที่คุณเข้าถึงได้", TEAM_NOT_FOUND: "ไม่พบทีมปัจจุบันของคุณ", SUBMISSION_CHANGED: "มีรอบส่งใหม่ กรุณาอ่านหัวข้ออีกครั้งก่อนลงมติ",
    SUBMISSION_NOT_APPROVED: BLOCKING.SUBMISSION_NOT_APPROVED, COMMITTEE_INCOMPLETE: BLOCKING.COMMITTEE_INCOMPLETE,
    VOTE_ALREADY_CAST: BLOCKING.ALREADY_VOTED, CSRF_INVALID: "ข้อมูลยืนยันคำขอไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่",
    ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้", VALIDATION_ERROR: "กรุณาตรวจสอบผลการลงมติและความคิดเห็น",
    INTERNAL_ERROR: "ระบบยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง", INVALID_RESPONSE: "ข้อมูลตอบกลับไม่ถูกต้อง กรุณาตรวจข้อมูลอีกครั้ง"
  } as Record<string, string>)[cause.code] ?? "ยังยืนยันผลไม่ได้ กรุณาตรวจข้อมูลอีกครั้ง";
}
