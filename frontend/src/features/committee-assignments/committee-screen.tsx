"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { useSession } from "@/features/auth/use-session";
import authStyles from "@/features/auth/auth.module.css";
import { appoint, candidates, CommitteeApiError, detail, errorMessage, projects, remove, replace,
  type Advisor, type Assignment, type Detail, type Project } from "./api";
import styles from "./committee.module.css";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "missing" } | { status: "forbidden" }
  | { status: "ready"; projects: Project[]; detail?: Detail; candidates: Advisor[] };
type Confirmation = { type: "remove"; assignment: Assignment } | { type: "replace"; assignment: Assignment; advisor: Advisor };

export function CommitteeScreen({ projectId }: { projectId?: string }) {
  const { state, retry } = useSession();
  const router = useRouter();
  const unauthenticated = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (state.status === "unauthenticated") unauthenticated(); }, [state.status, unauthenticated]);
  return <AuthShell><section aria-label="จัดการกรรมการโครงงาน">
    {state.status === "loading" || state.status === "unauthenticated" ? <p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>
      : state.status === "error" ? <><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{state.message}</p><button onClick={retry}>ลองอีกครั้ง</button></>
        : state.user.role !== "coordinator" ? <><Link href="/">← กลับหน้าบัญชี</Link><h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>
          : <Workspace key={`${state.user.id}:${projectId ?? "list"}`} projectId={projectId} unauthenticated={unauthenticated} />}
  </section></AuthShell>;
}

function Workspace({ projectId, unauthenticated }: { projectId?: string; unauthenticated: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState("");
  const [replacements, setReplacements] = useState<Record<string, string>>({});
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(false);
  const actionController = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setConfirmation(null); setSelected(""); setReplacements({}); setRevision((value) => value + 1); }, []);
  useEffect(() => () => actionController.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load(): Promise<State> {
      if (!projectId) return { status: "ready", projects: await projects(controller.signal), candidates: [] };
      const context = await detail(projectId, controller.signal);
      return { status: "ready", projects: [], detail: context,
        candidates: context.roster_locked ? [] : await candidates(projectId, controller.signal) };
    }
    void load().then((value) => {
      if (!controller.signal.aborted) { setState(value); setUncertain(false); }
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof CommitteeApiError && cause.status === 401) return unauthenticated();
      setState(cause instanceof CommitteeApiError && cause.code === "PROJECT_NOT_FOUND" ? { status: "missing" }
        : cause instanceof CommitteeApiError && cause.code === "COMMITTEE_ACCESS_FORBIDDEN" ? { status: "forbidden" }
          : { status: "error", message: errorMessage(cause) });
    });
    return () => controller.abort();
  }, [revision, projectId, unauthenticated]);

  async function act(operation: (signal: AbortSignal) => Promise<unknown>, message: string) {
    if (pending.current || uncertain) return;
    pending.current = true; setBusy(true); setError(""); setNotice("");
    const controller = new AbortController(); actionController.current = controller;
    try {
      await operation(controller.signal);
      if (controller.signal.aborted) return;
      setNotice(message); refresh();
    } catch (cause: unknown) {
      if (controller.signal.aborted) return;
      if (cause instanceof CommitteeApiError && cause.status === 401) return unauthenticated();
      setError(errorMessage(cause));
      if (cause instanceof CommitteeApiError && cause.code === "COMMITTEE_ROSTER_LOCKED") refresh();
      else setUncertain(true);
    } finally {
      if (!controller.signal.aborted) { pending.current = false; setBusy(false); }
    }
  }
  const back = <Link className={styles.backLink} href={projectId ? "/coordinator/projects" : "/"}>← {projectId ? "กลับรายการโครงงาน" : "กลับหน้าบัญชี"}</Link>;
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดข้อมูลกรรมการ…</p></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดข้อมูลไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primaryButton} onClick={refresh}>ลองอีกครั้ง</button></>;
  if (state.status === "missing") return <>{back}<h1>ไม่พบโครงงานที่คุณเข้าถึงได้</h1><p>ผู้ประสานงานเห็นโครงงานเมื่อมีหัวข้อที่อาจารย์อนุมัติแล้ว</p></>;
  if (state.status === "forbidden") return <>{back}<h1>บทบาทของคุณไม่สามารถใช้หน้านี้ได้</h1></>;
  if (!projectId || !state.detail) return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>สำหรับผู้ประสานงาน</span><h1>โครงงานสำหรับแต่งตั้งกรรมการ</h1><p>แสดงโครงงานที่มีหัวข้อผ่านการอนุมัติจากอาจารย์แล้ว</p></div>
    <button className={styles.textButton} onClick={refresh}>โหลดรายการใหม่</button>
    {state.projects.length === 0 ? <p className={styles.hint}>ยังไม่มีโครงงานที่มีหัวข้อผ่านการอนุมัติจากอาจารย์</p>
      : <ul className={styles.list} aria-label="โครงงานที่จัดกรรมการได้">{state.projects.map((row) => <li className={styles.card} key={row.id}>
        <h2>{row.name}</h2><p>{row.team.name}</p><Link className={styles.secondaryButton} href={`/coordinator/projects/${row.id}/committee`}>จัดการกรรมการ</Link>
      </li>)}</ul>}</>;

  const context = state.detail;
  const disabled = busy || uncertain || context.roster_locked;
  const choose = (assignment: Assignment) => {
    const advisor = state.candidates.find((row) => row.id === replacements[assignment.id]);
    if (!advisor) { setError("กรุณาเลือกอาจารย์ที่จะเปลี่ยนเป็นกรรมการ"); return; }
    setConfirmation({ type: "replace", assignment, advisor });
  };
  return <>{back}<div className={authStyles.heading}><span className={authStyles.sectionLabel}>แต่งตั้งกรรมการ</span><h1>{context.project.name}</h1><p>{context.project.team.name}</p></div>
    <p className={context.roster_locked ? styles.locked : styles.hint}>{context.roster_locked ? "รายชื่อกรรมการล็อกแล้วหลังเริ่มลงมติ" : "แก้รายชื่อกรรมการได้ก่อนเริ่มลงมติ"}</p>
    <p className={styles.hint}>กรรมการ {context.assignments.length} คน · ต้องมีอย่างน้อย 3 คนก่อนเริ่มลงมติ</p>
    <Link className={styles.backLink} href={`/coordinator/projects/${projectId}/topic-votes`}>ดูการลงมติรายบุคคล →</Link>
    <Link className={styles.backLink} href={`/coordinator/projects/${projectId}/evaluations`}>ผลประเมินโครงงาน →</Link>
    {notice && <p className={styles.notice} role="status">{notice}</p>}
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p><button disabled={busy} onClick={refresh}>ตรวจข้อมูลอีกครั้ง</button></div>}
    <div className={styles.headingRow}><h2>รายชื่อกรรมการ</h2><button className={styles.textButton} disabled={busy} onClick={refresh}>โหลดข้อมูลใหม่</button></div>
    {context.assignments.length === 0 ? <p className={styles.hint}>ยังไม่มีกรรมการ</p> : <ul className={styles.list} aria-label="รายชื่อกรรมการ">
      {context.assignments.map((row) => <li className={styles.card} key={row.id} data-testid={`committee-${row.id}`}>
        <h3>{row.advisor.full_name}</h3><p className={styles.hint}>แต่งตั้งเมื่อ {new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(row.assigned_at))}</p>
        {!context.roster_locked && <div className={styles.rowControls}><label htmlFor={`replace-${row.id}`}>เลือกอาจารย์แทน {row.advisor.full_name}</label>
          <select id={`replace-${row.id}`} disabled={disabled || confirmation !== null} value={replacements[row.id] ?? ""} onChange={(event) => setReplacements({ ...replacements, [row.id]: event.target.value })}>
            <option value="">เลือกอาจารย์</option>{state.candidates.map((option) => <option key={option.id} value={option.id}>{option.full_name}</option>)}</select>
          <div className={styles.actions}><button className={styles.secondaryButton} disabled={disabled || confirmation !== null} onClick={() => choose(row)}>เปลี่ยนกรรมการ</button>
            <button className={styles.secondaryButton} disabled={disabled || confirmation !== null} onClick={() => setConfirmation({ type: "remove", assignment: row })}>ถอดกรรมการ</button></div>
        </div>}
      </li>)}</ul>}
    {confirmation && <div className={styles.confirmation} role="region" aria-label="ยืนยันการเปลี่ยนรายชื่อ" aria-busy={busy}>
      <h2>{confirmation.type === "replace" ? "ยืนยันเปลี่ยนกรรมการ" : "ยืนยันถอดกรรมการ"}</h2><p>{confirmation.assignment.advisor.full_name}</p>
      {confirmation.type === "replace" && <p>เปลี่ยนเป็น {confirmation.advisor.full_name}</p>}
      <div className={styles.actions}><button className={styles.primaryButton} disabled={disabled} onClick={() => {
        if (confirmation.type === "replace") void act((signal) => replace(projectId, confirmation.assignment.id, confirmation.advisor.id, signal), "เปลี่ยนกรรมการแล้ว");
        else void act((signal) => remove(projectId, confirmation.assignment.id, signal), "ถอดกรรมการแล้ว");
      }}>{busy ? "กำลังบันทึก…" : confirmation.type === "replace" ? "ยืนยันเปลี่ยนกรรมการ" : "ยืนยันถอดกรรมการ"}</button>
        <button className={styles.secondaryButton} disabled={busy} onClick={() => setConfirmation(null)}>ยกเลิก</button></div>
    </div>}
    {!context.roster_locked && <form className={styles.form} aria-busy={busy} onSubmit={(event) => {
      event.preventDefault(); if (pending.current || disabled || confirmation) return;
      if (!selected) { setError("กรุณาเลือกอาจารย์ที่จะแต่งตั้ง"); return; }
      void act((signal) => appoint(projectId, selected, signal), "เพิ่มกรรมการแล้ว");
    }}>
      <label htmlFor="committee-candidate">เลือกอาจารย์เป็นกรรมการ</label><select id="committee-candidate" disabled={disabled || confirmation !== null} value={selected} onChange={(event) => setSelected(event.target.value)}>
        <option value="">เลือกอาจารย์</option>{state.candidates.map((row) => <option key={row.id} value={row.id}>{row.full_name}</option>)}</select>
      {state.candidates.length === 0 && <p className={styles.hint}>ไม่มีอาจารย์ที่แต่งตั้งเพิ่มได้ในขณะนี้</p>}
      <button className={styles.primaryButton} disabled={disabled || confirmation !== null || state.candidates.length === 0} type="submit">{busy ? "กำลังบันทึก…" : "เพิ่มกรรมการ"}</button>
    </form>}
  </>;
}
