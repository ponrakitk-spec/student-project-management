"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import { BLOCKING, context, errorMessage, EvaluationApiError, record, type Context, type Mode } from "./api";
import styles from "./evaluations.module.css";

type State = { status: "loading" } | { status: "error" | "missing"; message: string } | { status: "forbidden" } | { status: "ready"; context: Context };
const trim = (value: string) => value.replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, "");
const date = (value: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(value));

export function EvaluationScreen({ mode, projectId }: { mode: Mode; projectId?: string }) {
  const session = useSession(), router = useRouter();
  const unauthenticated = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") unauthenticated(); }, [session.state.status, unauthenticated]);
  const role = mode === "team" ? "student" : mode === "coordinator" ? "coordinator" : "advisor";
  return <AuthShell><section aria-label="การประเมินโครงงาน">
    {session.state.status === "loading" || session.state.status === "unauthenticated" ? <p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>
      : session.state.status === "error" ? <><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p><button onClick={session.retry}>ลองอีกครั้ง</button></>
        : session.state.user.role !== role ? <><Link href="/">← กลับหน้าบัญชี</Link><h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>
          : <Workspace key={`${session.state.user.id}:${mode}:${projectId ?? "me"}`} mode={mode} projectId={projectId} unauthenticated={unauthenticated} />}
  </section></AuthShell>;
}

function Workspace({ mode, projectId, unauthenticated }: { mode: Mode; projectId?: string; unauthenticated: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" }), [revision, setRevision] = useState(0);
  const [score, setScore] = useState(""), [comment, setComment] = useState("");
  const [confirmation, setConfirmation] = useState(false), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const pending = useRef(false), action = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setScore(""); setComment(""); setConfirmation(false); setRevision((value) => value + 1); }, []);
  useEffect(() => () => action.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    void context(mode, projectId, controller.signal).then((data) => {
      if (!controller.signal.aborted) { setState({ status: "ready", context: data }); setUncertain(false); }
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof EvaluationApiError && cause.status === 401) return unauthenticated();
      if (cause instanceof EvaluationApiError && cause.status === 403) return setState({ status: "forbidden" });
      setState(cause instanceof EvaluationApiError && ["TEAM_NOT_FOUND", "PROJECT_NOT_FOUND", "COMMITTEE_PROJECT_NOT_FOUND"].includes(cause.code)
        ? { status: "missing", message: errorMessage(cause) } : { status: "error", message: errorMessage(cause) });
    });
    return () => controller.abort();
  }, [mode, projectId, revision, unauthenticated]);

  async function submit() {
    if (pending.current || uncertain || !projectId) return;
    pending.current = true; setBusy(true); setError(""); setNotice("");
    const controller = new AbortController(); action.current = controller;
    try {
      await record(projectId, Number(score), trim(comment), controller.signal);
      if (!controller.signal.aborted) { setNotice("บันทึกการประเมินแล้ว"); refresh(); }
    } catch (cause: unknown) {
      if (controller.signal.aborted) return;
      if (cause instanceof EvaluationApiError && cause.status === 401) return unauthenticated();
      setError(errorMessage(cause));
      if (cause instanceof EvaluationApiError && cause.status === 409) refresh();
      else setUncertain(true);
    } finally {
      if (!controller.signal.aborted) { pending.current = false; setBusy(false); }
    }
  }
  const backPath = mode === "team" ? "/projects" : mode === "coordinator" ? `/coordinator/projects/${projectId}/committee` : `/${mode}/projects`;
  const back = <Link className={styles.backLink} href={backPath}>← กลับหน้าที่เกี่ยวข้อง</Link>;
  const reload = () => { setError(""); refresh(); };
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดข้อมูลการประเมิน…</p></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดข้อมูลไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primaryButton} onClick={reload}>ลองอีกครั้ง</button></>;
  if (state.status === "missing") return <>{back}<h1>{state.message}</h1></>;
  if (state.status === "forbidden") return <>{back}<h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>;
  if (state.status !== "ready") return null;
  const result = state.context, project = result.data.project;
  return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>ประเมินและผลคะแนนโครงงาน</span><h1>{project.name}</h1><p>{project.team.name}</p></div>
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p><button disabled={busy} onClick={reload}>ตรวจข้อมูลอีกครั้ง</button></div>}
    <button className={styles.textButton} disabled={busy} onClick={reload}>โหลดข้อมูลใหม่</button>
    <section className={styles.card} aria-label="สรุปคะแนน"><h2>สรุปคะแนน</h2>{result.data.summary === null ? <p className={styles.hint}>รอกรรมการประเมินครบทุกคน</p>
      : <dl className={styles.summary}><div><dt>คะแนนรวม</dt><dd>{result.data.summary.total_score}</dd></div><div><dt>คะแนนเฉลี่ย</dt><dd>{result.data.summary.average_score} / 100</dd></div></dl>}</section>
    {result.kind === "committee" && result.data.own_evaluation !== null && <section className={styles.card} aria-label="การประเมินของคุณ"><h2>การประเมินของคุณ</h2>
      <p>คะแนนของคุณ: {result.data.own_evaluation.score} / 100</p><p className={styles.comment}>{result.data.own_evaluation.comment}</p>
      <p className={styles.hint}>{date(result.data.own_evaluation.created_at)}</p><p className={styles.hint}>{BLOCKING.ALREADY_EVALUATED}</p></section>}
    {result.kind === "coordinator" && result.data.summary !== null && <section className={styles.card}><h2>ผลประเมินรายบุคคล</h2><ul className={styles.list} aria-label="ผลประเมินรายบุคคล">
      {result.data.evaluations.map((row) => <li className={styles.individual} key={row.id}><h3>{row.advisor.full_name}</h3><p>คะแนน: {row.score} / 100</p>
        <p className={styles.comment}>{row.comment}</p><p className={styles.hint}>{date(row.created_at)}</p></li>)}</ul></section>}
    {result.kind === "committee" && (result.data.can_evaluate ? <form noValidate className={styles.form} aria-busy={busy} onSubmit={(event) => {
      event.preventDefault(); if (pending.current || uncertain) return;
      const value = Number(score);
      if (!trim(score) || !Number.isInteger(value) || value < 0 || value > 100) { setError("กรุณาระบุคะแนนจำนวนเต็ม 0–100"); return; }
      if (!trim(comment)) { setError("กรุณาระบุความคิดเห็น"); return; }
      setError(""); setConfirmation(true);
    }}><h2>ประเมินโครงงาน</h2><label htmlFor="evaluation-score">คะแนน (0–100)</label><input id="evaluation-score" type="number" min="0" max="100" step="1" inputMode="numeric"
      value={score} disabled={busy || uncertain || confirmation} onChange={(event) => setScore(event.target.value)} />
      <label htmlFor="evaluation-comment">ความคิดเห็น</label><textarea id="evaluation-comment" value={comment} disabled={busy || uncertain || confirmation} onChange={(event) => setComment(event.target.value)} />
      <p className={styles.hint}>เมื่อมีการประเมินครั้งแรก ระบบจะล็อกการแก้ไขแผนงานและงานของโครงงาน</p>
      {!confirmation && <button className={styles.primaryButton} type="submit" disabled={busy || uncertain}>ตรวจสอบก่อนบันทึก</button>}
      {confirmation && <div className={styles.confirmation} role="region" aria-label="ยืนยันการประเมิน"><h2>ยืนยันการประเมิน</h2><p>{project.name}</p>
        <p>คะแนน: {Number(score)} / 100</p><p className={styles.comment}>{trim(comment)}</p><p>เมื่อบันทึกแล้วจะไม่สามารถแก้ไขหรือลบการประเมินได้</p><div className={styles.actions}>
          <button className={styles.primaryButton} type="button" disabled={busy || uncertain} onClick={() => void submit()}>{busy ? "กำลังบันทึก…" : "ยืนยันบันทึกการประเมิน"}</button>
          <button className={styles.secondaryButton} type="button" disabled={busy} onClick={() => setConfirmation(false)}>ยกเลิก</button></div></div>}
    </form> : !result.data.own_evaluation && <p className={styles.hint}>{BLOCKING[result.data.blocking_reason ?? ""]}</p>)}
  </>;
}
