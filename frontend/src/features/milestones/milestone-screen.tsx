"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { AuthApiError, currentUser, trimAscii } from "@/features/auth/api";
import { useSession } from "@/features/auth/use-session";
import { currentTeam, TeamApiError } from "@/features/teams/api";
import { currentProject, ProjectApiError } from "@/features/projects/api";
import { listMilestones, saveMilestone, deleteMilestone, milestoneErrorMessage, MilestoneApiError, STATUS_TEXT, type Milestone, type MilestoneList, type MilestoneFields } from "./api";
import styles from "./milestones.module.css";

type State = { status: "loading" } | { status: "missing"; resource: "team" | "project" } | { status: "error"; message: string }
  | { status: "ready"; data: MilestoneList; leader: boolean; projectName: string };
export function MilestoneScreen() {
  const session = useSession(); const router = useRouter(); const login = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") login(); }, [session.state.status, login]);
  let content;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") content = <p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>;
  else if (session.state.status === "error") content = <><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p role="alert">{session.state.message}</p><button onClick={session.retry}>ลองอีกครั้ง</button></>;
  else if (session.state.user.role !== "student") content = <><Link href="/">← กลับหน้าบัญชี</Link><h1>หน้านี้สำหรับนักศึกษา</h1></>;
  else content = <Panel key={session.state.user.id} actor={session.state.user.id} login={login} recheck={session.retry} />;
  return <AuthShell><section aria-label="แผนงานโครงงาน">{content}</section></AuthShell>;
}
function Panel({ actor, login, recheck }: { actor: string; login: () => void; recheck: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" }); const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Milestone | "new" | null>(null); const [removing, setRemoving] = useState<Milestone | null>(null);
  const [busy, setBusy] = useState(false); const [uncertain, setUncertain] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const pending = useRef(false); const action = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setEditing(null); setRemoving(null); setRevision(n => n + 1); }, []);
  useEffect(() => () => action.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const team = await currentTeam(controller.signal); if (!team) return { status: "missing", resource: "team" } as const;
      const project = await currentProject(controller.signal); if (!project) return { status: "missing", resource: "project" } as const;
      const data = await listMilestones(controller.signal);
      if (project.team_id !== team.id || data.project_id !== project.id) throw new MilestoneApiError(502, "INVALID_RESPONSE");
      const user = await currentUser(controller.signal);
      if (user.id !== actor || user.role !== "student") { recheck(); return null; }
      return { status: "ready", data, leader: team.membership.role === "leader", projectName: project.name } as const;
    }
    void load().then(value => { if (value && !controller.signal.aborted) { setState(value); setUncertain(false); } }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if ((cause instanceof MilestoneApiError || cause instanceof TeamApiError || cause instanceof ProjectApiError || cause instanceof AuthApiError) && cause.status === 401) { login(); return; }
      setState({ status: "error", message: milestoneErrorMessage(cause) });
    });
    return () => controller.abort();
  }, [actor, revision, login, recheck]);
  async function run(operation: (signal: AbortSignal) => Promise<unknown>, message: string) {
    if (pending.current || uncertain) return;
    pending.current = true; setBusy(true); setError(""); setNotice(""); const controller = new AbortController(); action.current = controller;
    try { await operation(controller.signal); if (!controller.signal.aborted) { setNotice(message); refresh(); } }
    catch (cause) { if (!controller.signal.aborted) { if (cause instanceof MilestoneApiError && cause.status === 401) { login(); return; } setError(milestoneErrorMessage(cause)); setUncertain(true); } }
    finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }
  const back = <Link className={styles.back} href="/projects">← กลับหน้าโครงงาน</Link>;
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดแผนงาน…</p></>;
  if (state.status === "missing") return <>{back}<h1>{state.resource === "team" ? "ต้องมีทีมก่อนจัดการแผนงาน" : "ต้องมีโครงงานก่อนจัดการแผนงาน"}</h1><Link href={state.resource === "team" ? "/teams" : "/projects"}>ไปเตรียมข้อมูล</Link></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดแผนงานไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primary} onClick={refresh}>ลองอีกครั้ง</button></>;
  const canManage = state.leader && state.data.can_manage;
  return <>{back}<h1>แผนงานโครงงาน</h1><p className={styles.hint}>{state.projectName}</p>
    {notice && <p className={styles.notice} role="status">{notice}</p>}{error && <div className={styles.error} role="alert"><p>{error}</p><button disabled={busy} onClick={refresh}>โหลดรายการอีกครั้ง</button><Link href="/login">เข้าสู่ระบบใหม่</Link></div>}
    <button className={styles.secondary} disabled={busy} onClick={refresh}>โหลดแผนงานใหม่</button>
    {!canManage && <p className={styles.hint}>{state.leader ? "แผนงานถูกล็อกหลังมีคะแนนประเมินแล้ว" : "สมาชิกอ่านแผนงานได้ เฉพาะหัวหน้าทีมเท่านั้นที่จัดการได้"}</p>}
    {canManage && !editing && !removing && <button className={styles.primary} disabled={busy || uncertain} onClick={() => setEditing("new")}>สร้างแผนงาน</button>}
    {canManage && editing && <MilestoneForm key={editing === "new" ? "new" : editing.id} row={editing === "new" ? undefined : editing} disabled={busy || uncertain} busy={busy}
      cancel={() => setEditing(null)} save={fields => void run(async signal => {
        const row = await saveMilestone(fields, editing === "new" ? undefined : editing, signal);
        if (row.project_id !== state.data.project_id || editing === "new" && row.created_by !== actor) throw new MilestoneApiError(502, "INVALID_RESPONSE");
      }, editing === "new" ? "สร้างแผนงานแล้ว" : "แก้ไขแผนงานแล้ว")} />}
    {state.data.milestones.length === 0 ? <p className={styles.hint}>ยังไม่มีแผนงาน</p> : <ul className={styles.list}>{state.data.milestones.map(row => <li className={styles.card} key={row.id} data-testid={`milestone-${row.id}`}>
      <h2>{row.name}</h2><p className={styles.hint}>กำหนดส่ง {row.due_date} · {STATUS_TEXT[row.status]}</p><p className={styles.description}>{row.description ?? "ยังไม่มีคำอธิบาย"}</p>
      <p className={styles.hint}>สถานะคำนวณจากงานย่อย</p>
      <Link className={styles.back} href={`/projects/milestones/${row.id}/tasks`}>งานย่อยและผู้รับผิดชอบ →</Link>
      {canManage && !editing && (removing?.id === row.id ? <div role="group" aria-label="ยืนยันลบแผนงาน"><p>ยืนยันลบแผนงาน “{row.name}” หรือไม่? ลบได้เฉพาะแผนงานที่ไม่มีงานย่อย</p>
        <button className={styles.primary} disabled={busy || uncertain} onClick={() => void run(signal => deleteMilestone(row, signal), "ลบแผนงานแล้ว")}>ยืนยันลบแผนงาน</button>
        <button className={styles.secondary} disabled={busy} onClick={() => setRemoving(null)}>ยกเลิก</button></div>
        : !removing && <div><button className={styles.secondary} disabled={busy || uncertain} onClick={() => setEditing(row)}>แก้ไขแผนงาน</button><button className={styles.secondary} disabled={busy || uncertain} onClick={() => setRemoving(row)}>ลบแผนงาน</button></div>)}
    </li>)}</ul>}
  </>;
}
function MilestoneForm({ row, disabled, busy, save, cancel }: { row?: Milestone; disabled: boolean; busy: boolean; save: (fields: Partial<MilestoneFields>) => void; cancel: () => void }) {
  const [name, setName] = useState(row?.name ?? ""); const [description, setDescription] = useState(row?.description ?? ""); const [due, setDue] = useState(row?.due_date ?? ""); const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault(); if (disabled) return;
    const normalized = trimAscii(name);
    if (!normalized || Array.from(normalized).length > 255) { setError("ชื่อแผนงานต้องมี 1–255 ตัวอักษร"); return; }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(due)) { setError("กรุณาระบุวันกำหนดส่ง"); return; }
    const all = { name: normalized, description: trimAscii(description) || null, due_date: due };
    const fields = row ? Object.fromEntries(Object.entries(all).filter(([key, value]) => row[key as keyof Milestone] !== value)) : all;
    if (!Object.keys(fields).length) { setError("ยังไม่มีการเปลี่ยนแปลง"); return; }
    setError(""); save(fields);
  }
  return <form className={styles.form} onSubmit={submit} aria-busy={busy} noValidate><h2>{row ? "แก้ไขแผนงาน" : "สร้างแผนงาน"}</h2>
    <label htmlFor="milestone-name">ชื่อแผนงาน</label><input id="milestone-name" value={name} disabled={disabled} onChange={e => setName(e.target.value)} />
    <label htmlFor="milestone-description">คำอธิบายแผนงาน (ไม่บังคับ)</label><textarea id="milestone-description" value={description} disabled={disabled} onChange={e => setDescription(e.target.value)} />
    <label htmlFor="milestone-due">วันกำหนดส่ง</label><input id="milestone-due" type="date" value={due} disabled={disabled} onChange={e => setDue(e.target.value)} />
    <p className={styles.hint}>วันกำหนดส่งที่สร้างหรือเปลี่ยนต้องไม่ก่อนวันปัจจุบันตามเวลาไทยของระบบ</p>{error && <p role="alert">{error}</p>}
    <button className={styles.primary} type="submit" disabled={disabled}>{busy ? "กำลังบันทึก…" : "บันทึกแผนงาน"}</button><button className={styles.secondary} type="button" disabled={disabled} onClick={cancel}>ยกเลิก</button>
  </form>;
}
