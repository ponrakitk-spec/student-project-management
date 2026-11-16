"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { AuthApiError, currentUser, trimAscii } from "@/features/auth/api";
import { useSession } from "@/features/auth/use-session";
import { currentTeam, TeamApiError, type CurrentTeam } from "@/features/teams/api";
import { currentProject, ProjectApiError, type Project } from "@/features/projects/api";
import { advisorHistory, teamHistory, eligibility, uploadSubmission, reviewSubmission, downloadSubmission,
  SubmissionApiError, submissionErrorMessage, MAX_FILE_BYTES, STATUS_TEXT, type Submission } from "./api";
import styles from "./submissions.module.css";

type Mode = "team" | "advisor";
type Data = { kind: "team"; team: CurrentTeam; project: Project; history: Submission[]; canSubmit: boolean } | { kind: "advisor"; history: Submission[] };
type State = { status: "loading" } | { status: "missing"; resource: "team" | "project" } | { status: "error"; message: string } | { status: "ready"; data: Data };
const timestamp = (s: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(s));
export function SubmissionScreen({ mode }: { mode: Mode }) {
  const session = useSession(); const router = useRouter();
  const login = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") login(); }, [session.state.status, login]);
  const frame = (content: ReactNode) => <AuthShell><section aria-label={mode === "team" ? "การส่งโครงงานของทีม" : "ตรวจโครงงานของอาจารย์"}>{content}</section></AuthShell>;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") return frame(<p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>);
  if (session.state.status === "error") return frame(<><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p><button onClick={session.retry}>ลองอีกครั้ง</button></>);
  if (session.state.user.role !== (mode === "team" ? "student" : "advisor")) return frame(<><Link href="/">← กลับหน้าบัญชี</Link><h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>);
  return frame(<SubmissionPanel key={`${mode}:${session.state.user.id}`} mode={mode} actor={session.state.user.id} login={login} recheck={session.retry} />);
}
function SubmissionPanel({ mode, actor, login, recheck }: { mode: Mode; actor: string; login: () => void; recheck: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" }); const [revision, setRevision] = useState(0);
  const [file, setFile] = useState<File | null>(null); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [uncertain, setUncertain] = useState(false);
  const pending = useRef(false); const action = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setFile(null); setRevision(n => n + 1); }, []);
  useEffect(() => () => action.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load(): Promise<Data | null> {
      let data: Data;
      if (mode === "advisor") data = { kind: "advisor", history: await advisorHistory(controller.signal) };
      else {
        const team = await currentTeam(controller.signal); if (!team) { setState({ status: "missing", resource: "team" }); return null; }
        const project = await currentProject(controller.signal); if (!project) { setState({ status: "missing", resource: "project" }); return null; }
        const history = await teamHistory(controller.signal); const canSubmit = await eligibility(controller.signal);
        if (project.team_id !== team.id || history.some(row => row.project_id !== project.id)) throw new SubmissionApiError(502, "INVALID_RESPONSE");
        data = { kind: "team", team, project, history, canSubmit };
      }
      const user = await currentUser(controller.signal);
      if (user.id !== actor || user.role !== (mode === "team" ? "student" : "advisor")) { recheck(); return null; }
      return data;
    }
    void load().then(data => { if (data && !controller.signal.aborted) { setState({ status: "ready", data }); setUncertain(false); } }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if ((cause instanceof SubmissionApiError || cause instanceof TeamApiError || cause instanceof ProjectApiError || cause instanceof AuthApiError) && cause.status === 401) { login(); return; }
      setState({ status: "error", message: submissionErrorMessage(cause) });
    });
    return () => controller.abort();
  }, [mode, actor, revision, login, recheck]);
  async function run(operation: (signal: AbortSignal) => Promise<unknown>, message: string, write = true) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(""); setNotice("");
    const controller = new AbortController(); action.current = controller;
    try {
      await operation(controller.signal);
      if (!controller.signal.aborted) { if (write) { setNotice(message); refresh(); } }
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof SubmissionApiError && cause.status === 401) { login(); return; }
      setError(submissionErrorMessage(cause)); if (write) setUncertain(true);
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); if (pending.current || uncertain) return;
    if (!file) { setError("กรุณาเลือกไฟล์ PDF หรือ PPTX"); return; }
    if (file.size < 1 || file.size > MAX_FILE_BYTES) { setError("ไฟล์ต้องมีขนาด 1–4,000,000 ไบต์"); return; }
    if (!/\.(pdf|pptx)$/i.test(file.name)) { setError("รองรับเฉพาะ PDF หรือ PPTX"); return; }
    if (state.status !== "ready" || state.data.kind !== "team" || !state.data.canSubmit || state.data.team.membership.role !== "leader") return;
    const project = state.data.project;
    void run(async signal => { const row = await uploadSubmission(file, signal); if (row.project_id !== project.id || row.submitted_by !== actor) throw new SubmissionApiError(502, "INVALID_RESPONSE"); }, "ส่งโครงงานแล้ว");
  }
  const back = <Link className={styles.back} href={mode === "team" ? "/projects" : "/"}>← {mode === "team" ? "กลับหน้าโครงงาน" : "กลับหน้าบัญชี"}</Link>;
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดประวัติการส่ง…</p></>;
  if (state.status === "missing") return <>{back}<h1>{state.resource === "team" ? "ต้องมีทีมก่อนส่งโครงงาน" : "ต้องมีโครงงานก่อนส่ง"}</h1><Link href={state.resource === "team" ? "/teams" : "/projects"}>ไปเตรียมข้อมูล</Link></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดประวัติไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primary} onClick={refresh}>ลองอีกครั้ง</button></>;
  const data = state.data;
  return <>{back}<h1>{mode === "team" ? "ส่งโครงงานและประวัติ" : "ตรวจโครงงานที่ปรึกษา"}</h1>
    <p className={styles.hint}>{data.kind === "team" ? data.project.name : "รายการส่งของโครงงานที่คุณตอบรับเป็นที่ปรึกษา"}</p>
    {notice && <p role="status" className={styles.notice}>{notice}</p>}
    {error && <div role="alert" className={styles.error}><p>{error}</p><button disabled={busy} onClick={refresh}>ตรวจประวัติอีกครั้ง</button><Link href="/login">เข้าสู่ระบบใหม่</Link></div>}
    {data.kind === "team" && (data.team.membership.role !== "leader" ? <p className={styles.hint}>เฉพาะหัวหน้าทีมปัจจุบันเท่านั้นที่ส่งโครงงานได้</p>
      : data.canSubmit ? <form className={styles.form} onSubmit={submit} aria-busy={busy} noValidate>
        <label htmlFor="submission-file">ไฟล์โครงงาน PDF หรือ PPTX</label><input id="submission-file" type="file" accept=".pdf,.pptx" disabled={busy || uncertain} onChange={event => setFile(event.target.files?.[0] ?? null)} />
        <p className={styles.hint}>หนึ่งไฟล์ ขนาด 1–4,000,000 ไบต์ ระบบจะเก็บชื่อและคำอธิบายโครงงาน ณ เวลาส่ง</p>
        <button className={styles.primary} disabled={busy || uncertain} type="submit">{busy ? "กำลังส่ง…" : "ส่งโครงงาน"}</button></form>
        : <p className={styles.hint}>ยังส่งรอบใหม่ไม่ได้ ต้องมีอาจารย์ตอบรับ และไม่มีรอบที่กำลังรอตรวจหรือขั้นตอนที่ล็อกอยู่</p>)}
    <div className={styles.heading}><h2>ประวัติการส่ง</h2><button disabled={busy} onClick={refresh}>โหลดประวัติใหม่</button></div>
    {data.history.length === 0 ? <p>ยังไม่มีรายการส่ง</p> : <ul className={styles.list}>{data.history.map(row => <li className={styles.card} key={row.id} data-testid={`submission-${row.id}`}>
      <h3>{row.snapshot_name}</h3><p className={styles.hint}>{row.team_name} · {STATUS_TEXT[row.status]}</p>
      <p className={styles.description}>{row.snapshot_description ?? "ยังไม่มีคำอธิบาย"}</p><p className={styles.hint}>ส่งเมื่อ {timestamp(row.submitted_at)}</p>
      <p className={styles.filename}>{row.original_filename}</p>
      {row.reviewed_at && <p className={styles.hint}>ตรวจเมื่อ {timestamp(row.reviewed_at)}</p>}{row.review_comment && <p className={styles.description}>คำแนะนำ: {row.review_comment}</p>}
      <button className={styles.secondary} disabled={busy} onClick={() => void run(signal => downloadSubmission(row, signal), "", false)}>ดาวน์โหลดไฟล์</button>
      {data.kind === "advisor" && row.status === "pending_review" && <ReviewForm key={row.id} row={row} disabled={busy || uncertain}
        onReview={(decision, comment) => void run(signal => reviewSubmission(row, decision, comment, signal), "บันทึกผลตรวจแล้ว")} />}
    </li>)}</ul>}
  </>;
}
function ReviewForm({ row, disabled, onReview }: { row: Submission; disabled: boolean; onReview: (decision: "approved" | "revision_requested", comment: string | null) => void }) {
  const [decision, setDecision] = useState<"approved" | "revision_requested">("approved"); const [comment, setComment] = useState("");
  const [confirm, setConfirm] = useState(false); const [error, setError] = useState("");
  function submit(event: FormEvent) { event.preventDefault(); if (disabled) return; if (decision === "revision_requested" && !trimAscii(comment)) { setError("กรุณาระบุคำแนะนำเมื่อขอแก้ไข"); return; } setError(""); setConfirm(true); }
  return <form className={styles.form} onSubmit={submit} noValidate>
    <label htmlFor={`decision-${row.id}`}>ผลตรวจ</label><select id={`decision-${row.id}`} disabled={disabled || confirm} value={decision} onChange={e => setDecision(e.target.value as typeof decision)}><option value="approved">อนุมัติ</option><option value="revision_requested">ขอแก้ไข</option></select>
    <label htmlFor={`comment-${row.id}`}>คำแนะนำ{decision === "revision_requested" ? " (จำเป็น)" : " (ไม่บังคับ)"}</label><textarea id={`comment-${row.id}`} value={comment} disabled={disabled || confirm} onChange={e => setComment(e.target.value)} />
    {error && <p role="alert">{error}</p>}
    {confirm ? <div role="group" aria-label="ยืนยันผลตรวจ"><p>บันทึกผลตรวจได้ครั้งเดียว ยืนยัน{decision === "approved" ? "อนุมัติ" : "ขอแก้ไข"}รอบนี้หรือไม่?</p>
      <button className={styles.primary} type="button" disabled={disabled} onClick={() => onReview(decision, trimAscii(comment) || null)}>ยืนยันผลตรวจ</button>
      <button className={styles.secondary} type="button" disabled={disabled} onClick={() => setConfirm(false)}>ยกเลิก</button></div>
      : <button className={styles.primary} disabled={disabled} type="submit">บันทึกผลตรวจ</button>}
  </form>;
}
