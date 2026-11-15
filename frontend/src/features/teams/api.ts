import { trimAscii } from "@/features/auth/api";

export type CreatedTeam = {
  id: string;
  name: string;
  description: string | null;
  members: [{ id: string; user_id: string; role: "leader" }];
};
export type CurrentTeam = {
  id: string;
  name: string;
  description: string | null;
  membership: { id: string; role: "leader" | "member" };
};
export type TeamMember = { id: string; user_id: string; full_name: string; role: "leader" | "member" };
type FieldError = { field: string; code: string };
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class TeamApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly fields: FieldError[] = []) {
    super(code);
    this.name = "TeamApiError";
  }
}

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function isField(value: unknown): value is FieldError {
  const item = object(value);
  return typeof item?.field === "string" && typeof item?.code === "string";
}
function isId(value: unknown): value is string { return typeof value === "string" && /^-?\d+$/.test(value); }

async function request(path: string, init: RequestInit, expectNoContent = false): Promise<unknown> {
  const response = await fetch(`${API_BASE}/api/v1/teams${path}`, { ...init, credentials: "include", cache: "no-store" });
  if (response.ok && expectNoContent) {
    if (response.status !== 204 || await response.text() !== "") throw new TeamApiError(502, "INVALID_RESPONSE");
    return;
  }
  const body = object(await response.json().catch(() => null));
  if (!response.ok) {
    const error = object(body?.error);
    throw new TeamApiError(response.status, typeof error?.code === "string" ? error.code : "REQUEST_FAILED",
      Array.isArray(error?.fields) ? error.fields.filter(isField) : []);
  }
  if (!body || !("data" in body)) throw new TeamApiError(502, "INVALID_RESPONSE");
  return body.data;
}

export async function createTeam(name: string, description: string, signal?: AbortSignal): Promise<CreatedTeam> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const data = object(await request("", { method: "POST", signal,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: JSON.stringify({ name: trimAscii(name), description: trimAscii(description) || null }) }));
  const member = Array.isArray(data?.members) && data.members.length === 1 ? object(data.members[0]) : null;
  if (!data || !isId(data.id) || typeof data.name !== "string" || !(typeof data.description === "string" || data.description === null)
    || !member || !isId(member.id) || !isId(member.user_id) || member.role !== "leader") throw new TeamApiError(502, "INVALID_RESPONSE");
  return data as CreatedTeam;
}

export async function currentTeam(signal?: AbortSignal): Promise<CurrentTeam | null> {
  let value: unknown;
  try { value = await request("/me", { method: "GET", signal }); }
  catch (error) {
    if (error instanceof TeamApiError && error.status === 404 && error.code === "TEAM_NOT_FOUND") return null;
    throw error;
  }
  return parseCurrentTeam(value);
}

function parseCurrentTeam(value: unknown): CurrentTeam {
  const data = object(value);
  const membership = object(data?.membership);
  if (!data || !isId(data.id) || typeof data.name !== "string" || !(typeof data.description === "string" || data.description === null)
    || !membership || !isId(membership.id) || !["leader", "member"].includes(String(membership.role))) throw new TeamApiError(502, "INVALID_RESPONSE");
  return data as CurrentTeam;
}

export async function updateTeam(changes: { name?: string; description?: string | null }, signal?: AbortSignal): Promise<CurrentTeam> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  return parseCurrentTeam(await request("/me", { method: "PATCH", signal,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: JSON.stringify(changes) }));
}

export async function transferLeader(teamMemberId: string, signal?: AbortSignal): Promise<CurrentTeam> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  return parseCurrentTeam(await request("/me/leader", { method: "POST", signal,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: JSON.stringify({ team_member_id: teamMemberId }) }));
}

async function membershipExit(path: string, signal?: AbortSignal): Promise<void> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  await request(path, { method: "POST", signal,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) }, body: "{}" }, true);
}

export function leaveTeam(signal?: AbortSignal) { return membershipExit("/me/leave", signal); }
export function removeTeamMember(id: string, signal?: AbortSignal) { return membershipExit(`/me/members/${id}/remove`, signal); }

function isMember(value: unknown): value is TeamMember {
  const item = object(value);
  return Boolean(item && isId(item.id) && isId(item.user_id) && typeof item.full_name === "string"
    && (item.role === "leader" || item.role === "member"));
}

export async function currentMembers(signal?: AbortSignal): Promise<TeamMember[]> {
  const data = await request("/me/members", { method: "GET", signal });
  if (!Array.isArray(data) || !data.length || !data.every(isMember)
    || new Set(data.map((item) => item.id)).size !== data.length
    || new Set(data.map((item) => item.user_id)).size !== data.length) throw new TeamApiError(502, "INVALID_RESPONSE");
  return data;
}

export async function addMember(email: string, signal?: AbortSignal): Promise<TeamMember> {
  const csrf = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("spms_csrf="))?.slice("spms_csrf=".length);
  const data = await request("/me/members", { method: "POST", signal,
    headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: JSON.stringify({ email: trimAscii(email) }) });
  if (!isMember(data) || data.role !== "member") throw new TeamApiError(502, "INVALID_RESPONSE");
  return data;
}

export function teamErrorMessage(error: unknown): string {
  if (!(error instanceof TeamApiError)) return "ไม่สามารถยืนยันผลการทำรายการได้ กรุณาตรวจสอบทีมอีกครั้ง";
  return ({
    AUTHENTICATION_REQUIRED: "กรุณาเข้าสู่ระบบอีกครั้ง",
    TEAM_CREATION_FORBIDDEN: "เฉพาะนักศึกษาเท่านั้นที่สร้างทีมได้",
    TEAM_ACCESS_FORBIDDEN: "หน้านี้สำหรับทีมของนักศึกษาเท่านั้น",
    TEAM_UPDATE_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่แก้ไขทีมได้",
    TEAM_METADATA_LOCKED: "ยังแก้ไขข้อมูลทีมในขั้นตอนนี้ไม่ได้ กรุณาตรวจสอบผลการส่งโครงงาน",
    TEAM_LEADER_TRANSFER_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่โอนหัวหน้าได้",
    TEAM_MEMBER_NOT_FOUND: "ไม่พบสมาชิกที่เลือกในทีมของคุณ กรุณาโหลดรายชื่อใหม่",
    LEADER_TARGET_INVALID: "กรุณาเลือกสมาชิกคนอื่นในทีมเพื่อรับหน้าที่หัวหน้า",
    TEAM_MEMBER_REMOVAL_FORBIDDEN: "เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ถอดสมาชิกได้",
    TEAM_LEADERSHIP_TRANSFER_REQUIRED: "ต้องโอนตำแหน่งหัวหน้าก่อนออกจากทีมหรือถอดสมาชิกคนนี้",
    MEMBER_EXIT_BLOCKED_BY_TASK: "ยังออกหรือถอดสมาชิกไม่ได้ เพราะมีงานที่กำลังทำซึ่งต้องมีผู้รับผิดชอบคนอื่นก่อน",
    TEAM_NOT_FOUND: "คุณยังไม่มีทีม กรุณาตรวจสอบทีมของคุณอีกครั้ง",
    TEAM_MEMBER_ADDITION_FORBIDDEN: "เฉพาะหัวหน้าทีมเท่านั้นที่เพิ่มสมาชิกได้",
    MEMBER_NOT_FOUND: "ไม่พบนักศึกษาที่เพิ่มได้ด้วยอีเมลนี้",
    MEMBER_UNAVAILABLE: "ไม่สามารถเพิ่มนักศึกษาคนนี้ได้ เนื่องจากมีทีมอยู่แล้ว",
    MEMBER_ADDITION_LOCKED: "ช่วงสถานะปัจจุบันยังไม่อนุญาตให้เพิ่มสมาชิก",
    ALREADY_IN_TEAM: "คุณมีทีมอยู่แล้ว กรุณาตรวจสอบทีมของคุณ",
    CSRF_INVALID: "ไม่สามารถยืนยันคำขอได้ กรุณาเข้าสู่ระบบอีกครั้ง",
    ORIGIN_NOT_ALLOWED: "ไม่สามารถทำรายการจากหน้านี้ได้ กรุณาติดต่อผู้ดูแลระบบ",
    INTERNAL_ERROR: "ระบบยังไม่พร้อมใช้งาน กรุณาลองอีกครั้ง",
    VALIDATION_ERROR: "กรุณาตรวจสอบข้อมูลทีม",
  } as Record<string, string>)[error.code] ?? "ไม่สามารถทำรายการได้ กรุณาตรวจสอบทีมอีกครั้ง";
}

const FIELD_MESSAGES: Record<string, string> = {
  REQUIRED: "กรุณากรอกชื่อทีม", INVALID_TYPE: "รูปแบบข้อมูลไม่ถูกต้อง",
  TEAM_NAME_REQUIRED: "กรุณากรอกชื่อทีม", TEAM_NAME_TOO_LONG: "ชื่อทีมต้องยาวไม่เกิน 255 ตัวอักษร",
  TEAM_TEXT_INVALID: "ข้อความมีอักขระที่ระบบไม่รองรับ กรุณาตรวจสอบอีกครั้ง",
};
export function teamFieldMessages(error: unknown): Record<string, string> {
  if (!(error instanceof TeamApiError)) return {};
  return Object.fromEntries(error.fields.filter((item) => ["name", "description"].includes(item.field))
    .map((item) => [item.field, FIELD_MESSAGES[item.code] ?? "กรุณาตรวจสอบข้อมูลช่องนี้"]));
}

export function validateTeamInput(name: string, description: string): Record<string, string> {
  const fields: Record<string, string> = {};
  const title = trimAscii(name);
  if (!title) fields.name = FIELD_MESSAGES.TEAM_NAME_REQUIRED;
  else if (Array.from(title).length > 255) fields.name = FIELD_MESSAGES.TEAM_NAME_TOO_LONG;
  for (const [key, value] of [["name", name], ["description", description]]) {
    if (value.includes("\x00") || Array.from(value).some((char) => {
      const point = char.codePointAt(0)!;
      return point >= 0xd800 && point <= 0xdfff;
    })) fields[key] = FIELD_MESSAGES.TEAM_TEXT_INVALID;
  }
  return fields;
}
