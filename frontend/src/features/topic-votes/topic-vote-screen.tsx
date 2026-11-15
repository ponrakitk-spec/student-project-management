"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import type { Project } from "@/features/committee-assignments/api";
import { BLOCKING, castVote, context, DECISIONS, errorMessage, listProjects, TopicVoteApiError,
  type Context, type Decision, type Mode, type Submission } from "./api";
import styles from "./topic-votes.module.css";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "missing"; message: string }
  | { status: "forbidden" } | { status: "projects"; projects: Project[] } | { status: "ready"; context: Context };
const date = (value: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(value));
const trim = (value: string) => value.replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, "");

export function TopicVoteScreen({ mode, projectId }: { mode: Mode; projectId?: string }) {
  const session = useSession(), router = useRouter();
  const unauthenticated = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") unauthenticated(); }, [session.state.status, unauthenticated]);
  const role = mode === "team" ? "student" : mode === "coordinator" ? "coordinator" : "advisor";
  return <AuthShell><section aria-label="การลงมติหัวข้อโครงงาน">
    {session.state.status === "loading" || session.state.status === "unauthenticated" ? <p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>
      : session.state.status === "error" ? <><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p><button onClick={session.retry}>ลองอีกครั้ง</button></>
        : session.state.user.role !== role ? <><Link href="/">← กลับหน้าบัญชี</Link><h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>
          : <Workspace key={`${session.state.user.id}:${mode}:${projectId ?? "list"}`} mode={mode} projectId={projectId} unauthenticated={unauthenticated} />}
  </section></AuthShell>;
}

function Workspace({ mode, projectId, unauthenticated }: { mode: Mode; projectId?: string; unauthenticated: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [revision, setRevision] = useState(0), [choice, setChoice] = useState<Decision | "">("");
  const [comment, setComment] = useState(""), [confirmation, setConfirmation] = useState(false);
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const pending = useRef(false), actionController = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setChoice(""); setComment(""); setConfirmation(false); setRevision((value) => value + 1); }, []);
  useEffect(() => () => actionController.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load(): Promise<State> {
      if (!projectId && (mode === "committee" || mode === "advisor")) return { status: "projects", projects: await listProjects(mode, controller.signal) };
      return { status: "ready", context: await context(mode, projectId, controller.signal) };
    }
    void load().then((value) => { if (!controller.signal.aborted) { setState(value); setUncertain(false); } }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof TopicVoteApiError && cause.status === 401) return unauthenticated();
      if (cause instanceof TopicVoteApiError && cause.status === 403) return setState({ status: "forbidden" });
      setState(cause instanceof TopicVoteApiError && ["TEAM_NOT_FOUND", "PROJECT_NOT_FOUND", "COMMITTEE_PROJECT_NOT_FOUND"].includes(cause.code)
        ? { status: "missing", message: errorMessage(cause) } : { status: "error", message: errorMessage(cause) });
    });
    return () => controller.abort();
  }, [mode, projectId, revision, unauthenticated]);

  async function submitVote(submissionId: string) {
    if (pending.current || uncertain || !projectId || !choice) return;
    pending.current = true; setBusy(true); setError(""); setNotice("");
    const controller = new AbortController(); actionController.current = controller;
    try {
      await castVote(projectId, submissionId, choice, trim(comment) || null, controller.signal);
      if (!controller.signal.aborted) { setNotice("บันทึกการลงมติแล้ว"); refresh(); }
    } catch (cause: unknown) {
      if (controller.signal.aborted) return;
      if (cause instanceof TopicVoteApiError && cause.status === 401) return unauthenticated();
      setError(errorMessage(cause));
      if (cause instanceof TopicVoteApiError && cause.status === 409) refresh();
      else setUncertain(true);
    } finally {
      if (!controller.signal.aborted) { pending.current = false; setBusy(false); }
    }
  }
  const backPath = mode === "team" ? "/projects" : mode === "coordinator" ? `/coordinator/projects/${projectId}/committee`
    : projectId ? `/${mode}/projects` : "/";
  const back = <Link className={styles.backLink} href={backPath}>← {projectId || mode === "team" ? "กลับหน้าที่เกี่ยวข้อง" : "กลับหน้าบัญชี"}</Link>;
  const reload = () => { setError(""); refresh(); };
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดข้อมูลการลงมติ…</p></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดข้อมูลไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primaryButton} onClick={reload}>ลองอีกครั้ง</button></>;
  if (state.status === "missing") return <>{back}<h1>{state.message}</h1></>;
  if (state.status === "forbidden") return <>{back}<h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>;
  if (state.status === "projects") return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>สำหรับอาจารย์</span>
    <h1>{mode === "committee" ? "งานกรรมการของคุณ" : "โครงงานที่คุณเป็นที่ปรึกษา"}</h1><p>{mode === "committee" ? "แสดงเฉพาะโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ" : "แสดงโครงงานที่คุณตอบรับเป็นที่ปรึกษาแล้ว"}</p></div>
    <button className={styles.textButton} onClick={reload}>โหลดรายการใหม่</button>
    {state.projects.length === 0 ? <p className={styles.hint}>{mode === "committee" ? "ยังไม่มีโครงงานที่คุณได้รับแต่งตั้งเป็นกรรมการ" : "ยังไม่มีโครงงานที่คุณตอบรับเป็นที่ปรึกษา"}</p>
      : <ul className={styles.list}>{state.projects.map((row) => <li className={styles.card} key={row.id}><h2>{row.name}</h2><p>{row.team.name}</p>
        <Link className={styles.secondaryButton} href={mode === "committee" ? `/committee/projects/${row.id}/topic-votes` : `/advisor/projects/${row.id}/committee`}>{mode === "committee" ? "อ่านหัวข้อและลงมติ" : "ดูรายชื่อกรรมการและผลหัวข้อ"}</Link>
        <Link className={styles.secondaryButton} href={`/${mode}/projects/${row.id}/evaluations`}>{mode === "committee" ? "ประเมินโครงงาน" : "ผลประเมินโครงงาน"}</Link></li>)}</ul>}</>;

  const result = state.context, project = result.data.project;
  return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>{mode === "committee" ? "กรรมการโครงงาน" : "รายชื่อกรรมการและผลหัวข้อ"}</span><h1>{project.name}</h1><p>{project.team.name}</p></div>
    <Link className={styles.backLink} href={mode === "team" ? "/projects/evaluations" : `/${mode}/projects/${projectId}/evaluations`}>ผลประเมินโครงงาน →</Link>
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p><button disabled={busy} onClick={reload}>ตรวจข้อมูลอีกครั้ง</button></div>}
    <button className={styles.textButton} disabled={busy} onClick={reload}>โหลดข้อมูลใหม่</button>
    {result.kind === "reader" && <div className={styles.card}><h2>รายชื่อกรรมการ</h2>{result.data.committee.length === 0 ? <p className={styles.hint}>ยังไม่มีกรรมการ</p>
      : <ul aria-label="รายชื่อกรรมการ">{result.data.committee.map((row, index) => <li key={index}>{row.full_name}</li>)}</ul>}</div>}
    {result.data.rounds.length === 0 && <p className={styles.hint}>ยังไม่มีรอบส่งหัวข้อที่แสดงได้</p>}
    <div className={styles.list}>{result.data.rounds.map((round) => <article className={styles.card} key={round.submission.id} data-testid={`topic-round-${round.submission.id}`}>
      <Snapshot submission={round.submission} />
      <p className={round.decision ? styles.notice : styles.hint}>ผลสรุป: {round.decision ? DECISIONS[round.decision] : "รอผลสรุปจากกรรมการ"}</p>
      {"own_vote" in round && (round.own_vote ? <div className={styles.ownVote}><h3>การลงมติของคุณ</h3><p>{DECISIONS[round.own_vote.vote]}</p>
        {round.own_vote.comment && <p className={styles.comment}>{round.own_vote.comment}</p>}<p className={styles.hint}>{date(round.own_vote.voted_at)}</p></div> : <p className={styles.hint}>คุณยังไม่ได้ลงมติรอบนี้</p>)}
      {"comments" in round && round.comments.length > 0 && <div><h3>ความคิดเห็นจากกรรมการ</h3><ul className={styles.comments} aria-label="ความคิดเห็นจากกรรมการ">
        {round.comments.map((text, index) => <li className={styles.comment} key={index}>{text}</li>)}</ul></div>}
      {"votes" in round && <ul className={styles.comments} aria-label="ผลลงมติรายบุคคล">{round.votes.map((row) => <li key={row.id} className={styles.ownVote}>
        <h3>{row.advisor.full_name}</h3><p>{DECISIONS[row.vote]}</p>{row.comment && <p className={styles.comment}>{row.comment}</p>}<p className={styles.hint}>{date(row.voted_at)}</p>
      </li>)}</ul>}
    </article>)}</div>
    {result.kind === "committee" && (result.data.can_vote && result.data.latest_submission_id ? <form className={styles.form} aria-busy={busy} onSubmit={(event) => {
      event.preventDefault(); if (pending.current || uncertain) return;
      if (!choice) { setError("กรุณาเลือกผลการลงมติ"); return; }
      if (choice === "revision_requested" && !trim(comment)) { setError("กรุณาระบุความคิดเห็นเมื่อขอแก้ไข"); return; }
      setError(""); setConfirmation(true);
    }}><h2>ลงมติรอบล่าสุด</h2><label htmlFor="vote-choice">ผลการลงมติ</label>
      <select id="vote-choice" value={choice} disabled={busy || uncertain || confirmation} onChange={(event) => setChoice(event.target.value as Decision | "")}>
        <option value="">เลือกผลการลงมติ</option><option value="approved">ผ่าน</option><option value="revision_requested">ขอแก้ไข</option></select>
      <label htmlFor="vote-comment">ความคิดเห็น</label><textarea id="vote-comment" value={comment} disabled={busy || uncertain || confirmation} onChange={(event) => setComment(event.target.value)} />
      <p className={styles.hint}>หากขอแก้ไข ต้องระบุความคิดเห็น</p>
      {!confirmation && <button className={styles.primaryButton} disabled={busy || uncertain} type="submit">ตรวจสอบก่อนลงมติ</button>}
      {confirmation && <div className={styles.confirmation} role="region" aria-label="ยืนยันการลงมติ"><h2>ยืนยันการลงมติ</h2>
        <p>{result.data.rounds[0].submission.snapshot_name}</p><p>{choice ? DECISIONS[choice] : ""}</p>{trim(comment) && <p className={styles.comment}>{trim(comment)}</p>}
        <p>เมื่อบันทึกแล้วจะไม่สามารถแก้ไขหรือลบการลงมติได้</p><div className={styles.actions}>
          <button className={styles.primaryButton} type="button" disabled={busy || uncertain} onClick={() => void submitVote(result.data.latest_submission_id!)}>{busy ? "กำลังบันทึก…" : "ยืนยันลงมติ"}</button>
          <button className={styles.secondaryButton} type="button" disabled={busy} onClick={() => setConfirmation(false)}>ยกเลิก</button></div></div>}
    </form> : <p className={styles.hint}>{BLOCKING[result.data.blocking_reason ?? ""]}</p>)}
  </>;
}

function Snapshot({ submission }: { submission: Submission }) {
  return <><span className={styles.hint}>หัวข้อรอบส่ง · {date(submission.submitted_at)}</span><h2>{submission.snapshot_name}</h2>
    {submission.snapshot_description && <p className={styles.comment}>{submission.snapshot_description}</p>}</>;
}
