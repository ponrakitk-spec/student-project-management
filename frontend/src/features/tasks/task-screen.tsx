"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { AuthApiError, currentUser, trimAscii } from "@/features/auth/api";
import { useSession } from "@/features/auth/use-session";
import { currentTeam, currentMembers, TeamApiError, type TeamMember } from "@/features/teams/api";
import { currentProject, ProjectApiError } from "@/features/projects/api";
import { listTasks, currentTask, saveTask, setTaskStatus, deleteTask, assignees, assignmentHistory, assignTask, unassignTask,
  TaskApiError, taskErrorMessage, validId, STATUS_TEXT, type Task, type TaskFields, type TaskStatus, type TaskList, type Assignee, type AssignmentHistory } from "./api";
import styles from "./tasks.module.css";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: TaskList; leader: boolean; members: TeamMember[] };
type Run = (operation: (signal: AbortSignal) => Promise<unknown>, message: string, deleted?: boolean) => void;
const timestamp = (s: string) => new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(s));
export function TaskScreen({ milestone }: { milestone: string }) {
  const session = useSession(); const router = useRouter(); const login = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (session.state.status === "unauthenticated") login(); }, [session.state.status, login]);
  let content;
  if (session.state.status === "loading" || session.state.status === "unauthenticated") content = <p role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p>;
  else if (session.state.status === "error") content = <><p role="alert">{session.state.message}</p><button onClick={session.retry}>ลองอีกครั้ง</button></>;
  else if (session.state.user.role !== "student") content = <><Link href="/">← กลับหน้าบัญชี</Link><h1>หน้านี้สำหรับนักศึกษา</h1></>;
  else if (!validId(milestone)) content = <><Link href="/projects/milestones">← กลับหน้าแผนงาน</Link><h1>รหัสแผนงานไม่ถูกต้อง</h1></>;
  else content = <Panel key={`${session.state.user.id}:${milestone}`} actor={session.state.user.id} milestone={milestone} login={login} recheck={session.retry} />;
  return <AuthShell><section className={styles.screen} aria-label="งานย่อยและผู้รับผิดชอบ">{content}</section></AuthShell>;
}
function Panel({ actor, milestone, login, recheck }: { actor: string; milestone: string; login: () => void; recheck: () => void }) {
  const [state, setState] = useState<State>({ status: "loading" }); const [revision, setRevision] = useState(0);
  const [creating, setCreating] = useState(false); const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false); const [uncertain, setUncertain] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const pending = useRef(false); const action = useRef<AbortController | null>(null);
  const refresh = useCallback(() => { setState({ status: "loading" }); setCreating(false); setRevision(n => n + 1); }, []);
  useEffect(() => () => action.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const team = await currentTeam(controller.signal); if (!team) throw new TaskApiError(404, "TASK_NOT_FOUND");
      const project = await currentProject(controller.signal); if (!project || project.team_id !== team.id) throw new TaskApiError(404, "TASK_NOT_FOUND");
      const data = await listTasks(milestone, controller.signal); const members = await currentMembers(controller.signal);
      if (data.milestone.project_id !== project.id) throw new TaskApiError(502, "INVALID_RESPONSE");
      const user = await currentUser(controller.signal); if (user.id !== actor || user.role !== "student") { recheck(); return null; }
      return { status: "ready", data, leader: team.membership.role === "leader", members } as const;
    }
    void load().then(value => { if (value && !controller.signal.aborted) { setState(value); setUncertain(false); } }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if ((cause instanceof TaskApiError || cause instanceof TeamApiError || cause instanceof ProjectApiError || cause instanceof AuthApiError) && cause.status === 401) { login(); return; }
      setState({ status: "error", message: taskErrorMessage(cause) });
    });
    return () => controller.abort();
  }, [actor, milestone, revision, login, recheck]);
  const run: Run = (operation, message, deleted) => {
    if (pending.current || uncertain) return;
    pending.current = true; setBusy(true); setError(""); setNotice(""); const controller = new AbortController(); action.current = controller;
    void operation(controller.signal).then(() => { if (!controller.signal.aborted) { setNotice(message); if (deleted) setSelected(null); refresh(); } }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof TaskApiError && cause.status === 401) { login(); return; }
      setError(taskErrorMessage(cause)); setUncertain(true);
    }).finally(() => { pending.current = false; if (!controller.signal.aborted) setBusy(false); });
  };
  const back = <Link className={styles.back} href="/projects/milestones">← กลับหน้าแผนงาน</Link>;
  if (state.status === "loading") return <>{back}<p role="status">กำลังโหลดงานย่อย…</p></>;
  if (state.status === "error") return <>{back}<h1>ยังโหลดงานไม่ได้</h1><p role="alert">{state.message}</p><button className={styles.primary} onClick={refresh}>ลองอีกครั้ง</button></>;
  const { data, leader, members } = state; const manage = leader && data.can_manage;
  return <>{back}<h1>งานย่อยของ {data.milestone.name}</h1><p className={styles.hint}>แผนงาน: {STATUS_TEXT[data.milestone.status]} · กำหนดส่ง {data.milestone.due_date}</p>
    {notice && <p role="status" className={styles.notice}>{notice}</p>}{error && <div role="alert" className={styles.error}><p>{error}</p><button disabled={busy} onClick={refresh}>โหลดข้อมูลงานอีกครั้ง</button><Link href="/login">เข้าสู่ระบบใหม่</Link></div>}
    <button className={styles.secondary} disabled={busy} onClick={refresh}>โหลดงานใหม่</button>
    {manage && !creating && <button className={styles.primary} disabled={busy || uncertain} onClick={() => { setCreating(true); setSelected(null); }}>สร้างงานย่อย</button>}
    {leader && !data.can_manage && <p className={styles.hint}>งานถูกล็อกหลังมีคะแนนประเมินแล้ว</p>}
    {creating && manage && <TaskForm busy={busy} disabled={busy || uncertain} cancel={() => setCreating(false)} save={fields => run(async signal => {
      const created = await saveTask(milestone, fields, undefined, signal); if (created.created_by !== actor) throw new TaskApiError(502, "INVALID_RESPONSE"); setSelected(created.id);
    }, "สร้างงานย่อยแล้ว")} />}
    {data.tasks.length === 0 ? <p className={styles.hint}>ยังไม่มีงานย่อย</p> : <ul className={styles.list}>{data.tasks.map(row => <li className={styles.card} key={row.id} data-testid={`task-${row.id}`}>
      <h2>{row.name}</h2><p className={styles.hint}>{STATUS_TEXT[row.status]} · {row.due_date ?? "ไม่ระบุวันกำหนดส่ง"}</p><p className={styles.description}>{row.description ?? "ยังไม่มีคำอธิบาย"}</p>
      <button className={styles.secondary} disabled={busy} onClick={() => { setCreating(false); setSelected(selected === row.id ? null : row.id); }}>{selected === row.id ? "ปิดรายละเอียดงาน" : "ดูรายละเอียดงาน"}</button>
      {selected === row.id && !creating && <Details key={`${row.id}:${revision}`} row={row} actor={actor} members={members} leader={leader} manage={manage} disabled={busy || uncertain} busy={busy} run={run} login={login} />}
    </li>)}</ul>}
  </>;
}
type Detail = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; task: Task; assignees: Assignee[]; history: AssignmentHistory[] };
function Details({ row, actor, members, leader, manage, disabled, busy, run, login }: { row: Task; actor: string; members: TeamMember[]; leader: boolean; manage: boolean; disabled: boolean; busy: boolean; run: Run; login: () => void }) {
  const [state, setState] = useState<Detail>({ status: "loading" }); const [editing, setEditing] = useState(false);
  const [removing, setRemoving] = useState<string | "task" | null>(null); const [member, setMember] = useState(""); const [status, setStatus] = useState<TaskStatus>(row.status);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([currentTask(row.id, row.milestone_id, controller.signal), assignees(row.id, controller.signal), assignmentHistory(row.id, controller.signal)]).then(([task, current, history]) => {
      if (controller.signal.aborted) return;
      if (current.some(a => !members.some(m => m.id === a.team_member_id && m.user_id === a.user.id))) throw new TaskApiError(502, "INVALID_RESPONSE");
      setState({ status: "ready", task, assignees: current, history }); setStatus(task.status);
    }).catch((cause: unknown) => { if (!controller.signal.aborted) { if (cause instanceof TaskApiError && cause.status === 401) login(); else setState({ status: "error", message: taskErrorMessage(cause) }); } });
    return () => controller.abort();
  }, [row.id, row.milestone_id, members, login]);
  if (state.status === "loading") return <p role="status">กำลังโหลดรายละเอียดงาน…</p>;
  if (state.status === "error") return <p role="alert">{state.message} กรุณาโหลดงานใหม่</p>;
  const task = state.task; const completed = task.status === "completed"; const hasAssignee = state.assignees.length > 0;
  const available = members.filter(m => !state.assignees.some(a => a.team_member_id === m.id));
  const changeStatus = (!leader || manage) && (!completed || manage);
  return <div className={styles.details}>
    <p className={styles.hint}>อัปเดตเมื่อ {timestamp(task.updated_at)}{task.completed_at ? ` · เสร็จเมื่อ ${timestamp(task.completed_at)}` : ""}</p>
    {manage && !completed && !editing && <button className={styles.secondary} disabled={disabled} onClick={() => setEditing(true)}>แก้ไขงานย่อย</button>}
    {editing && manage && !completed && <TaskForm row={task} disabled={disabled} busy={busy} cancel={() => setEditing(false)} save={fields => run(signal => saveTask(task.milestone_id, fields, task, signal), "แก้ไขงานย่อยแล้ว")} />}
    {changeStatus && <form className={styles.form} onSubmit={event => { event.preventDefault(); if (!disabled && status !== task.status) run(signal => setTaskStatus(task, status, signal), "เปลี่ยนสถานะงานแล้ว"); }}>
      <label htmlFor={`status-${task.id}`}>สถานะงานย่อย</label><select id={`status-${task.id}`} value={status} disabled={disabled} onChange={e => setStatus(e.target.value as TaskStatus)}>
        {Object.entries(STATUS_TEXT).map(([value, label]) => <option key={value} value={value} disabled={completed ? value !== "in_progress" && value !== "completed" : value !== "not_started" && !hasAssignee}>{label}</option>)}
      </select><button className={styles.primary} disabled={disabled || status === task.status || completed && !hasAssignee} type="submit">บันทึกสถานะงาน</button>
    </form>}
    {!hasAssignee && <p className={styles.hint}>{completed ? "งานที่เสร็จแล้วและไม่มีผู้รับผิดชอบยังเปิดกลับไม่ได้ตามกฎปัจจุบัน" : "ต้องมีผู้รับผิดชอบอย่างน้อยหนึ่งคนก่อนเริ่มหรือทำงานให้เสร็จ"}</p>}
    <h3>ผู้รับผิดชอบปัจจุบัน</h3>{state.assignees.length === 0 ? <p className={styles.hint}>ยังไม่มีผู้รับผิดชอบ</p> : <ul className={styles.people} aria-label="ผู้รับผิดชอบปัจจุบัน">{state.assignees.map(a => <li key={a.id}>
      <span>{a.user.full_name}{a.user.id === actor ? " (คุณ)" : ""}</span><span className={styles.hint}>มอบหมายเมื่อ {timestamp(a.assigned_at)}</span>
      {manage && !completed && <button className={styles.secondary} disabled={disabled} onClick={() => setRemoving(a.team_member_id)}>ถอนผู้รับผิดชอบ</button>}
    </li>)}</ul>}
    {manage && !completed && available.length > 0 && <form className={styles.form} onSubmit={event => { event.preventDefault(); if (!disabled && available.some(m => m.id === member)) run(signal => assignTask(task.id, member, signal), "มอบหมายงานแล้ว"); }}>
      <label htmlFor={`member-${task.id}`}>เลือกผู้รับผิดชอบ</label><select id={`member-${task.id}`} value={member} disabled={disabled} onChange={e => setMember(e.target.value)}><option value="">เลือกสมาชิกทีม</option>{available.map(m => <option key={m.id} value={m.id}>{m.full_name}{m.user_id === actor ? " (คุณ)" : ""}</option>)}</select>
      <button className={styles.primary} type="submit" disabled={disabled || !available.some(m => m.id === member)}>มอบหมายงาน</button></form>}
    <h3>ประวัติถอนผู้รับผิดชอบ</h3>{state.history.length === 0 ? <p className={styles.hint}>ยังไม่มีประวัติถอนงาน</p> : <ul className={styles.people} aria-label="ประวัติถอนผู้รับผิดชอบ">{state.history.map(h => <li key={h.id}><span>{h.user.full_name}</span><span className={styles.hint}>มอบหมาย {timestamp(h.assigned_at)} · ถอน {timestamp(h.unassigned_at)}</span></li>)}</ul>}
    {manage && !completed && !removing && <button className={styles.secondary} disabled={disabled} onClick={() => setRemoving("task")}>ลบงานย่อย</button>}
    {removing && manage && !completed && <div className={styles.confirm} role="group" aria-label="ยืนยันการลบหรือถอนงาน"><p>{removing === "task" ? "ยืนยันลบงานย่อยพร้อมรายการผู้รับผิดชอบและประวัติของงานนี้หรือไม่?" : "ยืนยันถอนผู้รับผิดชอบรายนี้หรือไม่? ประวัติจะถูกเก็บไว้"}</p>
      <button className={styles.primary} disabled={disabled} onClick={() => removing === "task" ? run(signal => deleteTask(task, signal), "ลบงานย่อยแล้ว", true) : run(signal => unassignTask(task.id, removing, signal), "ถอนผู้รับผิดชอบแล้ว")}>{removing === "task" ? "ยืนยันลบงานย่อย" : "ยืนยันถอนผู้รับผิดชอบ"}</button>
      <button className={styles.secondary} disabled={busy} onClick={() => setRemoving(null)}>ยกเลิก</button></div>}
  </div>;
}
function TaskForm({ row, disabled, busy, save, cancel }: { row?: Task; disabled: boolean; busy: boolean; save: (fields: Partial<TaskFields>) => void; cancel: () => void }) {
  const [name, setName] = useState(row?.name ?? ""); const [description, setDescription] = useState(row?.description ?? ""); const [due, setDue] = useState(row?.due_date ?? ""); const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault(); if (disabled) return; const normalized = trimAscii(name);
    if (!normalized || Array.from(normalized).length > 255) { setError("ชื่องานต้องมี 1–255 ตัวอักษร"); return; }
    if (due && !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(due)) { setError("กรุณาตรวจวันกำหนดส่ง"); return; }
    const all = { name: normalized, description: trimAscii(description) || null, due_date: due || null };
    const fields = row ? Object.fromEntries(Object.entries(all).filter(([key, value]) => row[key as keyof Task] !== value)) : all;
    if (!Object.keys(fields).length) { setError("ยังไม่มีการเปลี่ยนแปลง"); return; } setError(""); save(fields);
  }
  return <form className={styles.form} onSubmit={submit} aria-busy={busy} noValidate><h3>{row ? "แก้ไขงานย่อย" : "สร้างงานย่อย"}</h3>
    <label htmlFor="task-name">ชื่องานย่อย</label><input id="task-name" value={name} disabled={disabled} onChange={e => setName(e.target.value)} />
    <label htmlFor="task-description">คำอธิบายงาน (ไม่บังคับ)</label><textarea id="task-description" value={description} disabled={disabled} onChange={e => setDescription(e.target.value)} />
    <label htmlFor="task-due">วันกำหนดส่งงาน (ไม่บังคับ)</label><input id="task-due" type="date" value={due} disabled={disabled} onChange={e => setDue(e.target.value)} />
    <p className={styles.hint}>ถ้าระบุวันใหม่ ต้องไม่ก่อนวันนี้ตามเวลาไทยและไม่เกินวันของแผนงาน</p>{error && <p role="alert">{error}</p>}
    <button className={styles.primary} type="submit" disabled={disabled}>{busy ? "กำลังบันทึก…" : "บันทึกงานย่อย"}</button><button className={styles.secondary} type="button" disabled={disabled} onClick={cancel}>ยกเลิก</button>
  </form>;
}
