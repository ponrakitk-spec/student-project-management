"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/features/auth/auth-shell";
import { trimAscii } from "@/features/auth/api";
import { useSession } from "@/features/auth/use-session";
import { currentTeam, TeamApiError, type CurrentTeam } from "@/features/teams/api";
import { currentProject, ProjectApiError, type Project } from "@/features/projects/api";
import styles from "./workspace.module.css";

const ROLES = { student: "นักศึกษา", advisor: "อาจารย์", coordinator: "ผู้ประสานงาน" };
type StudentState = { status: "loading" } | { status: "error"; forbidden: boolean }
  | { status: "ready"; team: CurrentTeam | null; project: Project | null };

function validId(value: string) {
  return /^[1-9]\d*$/.test(value) && BigInt(value) <= BigInt("9223372036854775807");
}

function StudentOverview({ onExpired }: { onExpired: () => void }) {
  const [state, setState] = useState<StudentState>({ status: "loading" });
  const [revision, setRevision] = useState(0);
  function reload() { setState({ status: "loading" }); setRevision((value) => value + 1); }
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const team = await currentTeam(controller.signal);
        if (controller.signal.aborted) return;
        if (team && (!validId(team.id) || !validId(team.membership.id) || !trimAscii(team.name))) throw new Error("INVALID_TEAM_OVERVIEW");
        const project = team ? await currentProject(controller.signal) : null;
        if (controller.signal.aborted) return;
        // Two independent reads must never combine different teams during an exit/join.
        if (project && (!validId(project.id) || !validId(project.team_id) || !validId(project.created_by)
          || !trimAscii(project.name) || project.team_id !== team?.id)) throw new Error("INVALID_PROJECT_OVERVIEW");
        setState({ status: "ready", team, project });
      } catch (cause) {
        if (controller.signal.aborted) return;
        const apiError = cause instanceof TeamApiError || cause instanceof ProjectApiError;
        if (apiError && cause.status === 401) { onExpired(); return; }
        setState({ status: "error", forbidden: apiError && cause.status === 403 });
      }
    }
    void load();
    return () => controller.abort();
  }, [revision, onExpired]);

  return <section aria-label="ภาพรวมทีมและโครงงาน" className={styles.overview}>
    <div className={styles.sectionTop}><h2>ทีมและโครงงานของฉัน</h2>
      <button className={styles.textButton} onClick={reload} disabled={state.status === "loading"}>โหลดข้อมูลใหม่</button>
    </div>
    {state.status === "loading" && <p className={styles.state} role="status">กำลังโหลดทีมและโครงงาน…</p>}
    {state.status === "error" && <div className={styles.error} role="alert">
      <h3>{state.forbidden ? "ยังเข้าถึงพื้นที่นี้ไม่ได้" : "ยังโหลดข้อมูลไม่ได้"}</h3>
      <p>{state.forbidden ? "สิทธิ์ของบัญชีอาจเปลี่ยนแปลง กรุณาตรวจสอบบัญชีหรือโหลดข้อมูลใหม่" : "ยังยืนยันข้อมูลทีมและโครงงานไม่ได้ กรุณาลองอีกครั้ง"}</p>
      <button className={styles.textButton} onClick={reload}>ลองอีกครั้ง</button>
    </div>}
    {state.status === "ready" && (state.team ? <>
      <section className={styles.card} aria-label="ทีมของฉัน">
        <span className={styles.label}>ทีมของฉัน</span><h3>{state.team.name}</h3>
        <p className={styles.badge}>{state.team.membership.role === "leader" ? "หัวหน้าทีม" : "สมาชิกทีม"}</p>
        {state.team.description && <p className={styles.description}>{state.team.description}</p>}
        <Link className={styles.link} href="/teams">ไปที่ทีมของฉัน →</Link>
      </section>
      <section className={styles.card} aria-label="โครงงานของทีม">
        <span className={styles.label}>โครงงานของทีม</span>
        {state.project ? <><h3>{state.project.name}</h3>
          {state.project.description && <p className={styles.description}>{state.project.description}</p>}
          <Link className={styles.link} href="/projects">ดูโครงงานของทีม →</Link>
        </> : <><h3>ยังไม่มีโครงงานของทีม</h3>
          <p>{state.team.membership.role === "leader" ? "เริ่มบันทึกหัวข้อโครงงานให้ทีมของคุณ" : "หัวหน้าทีมเป็นผู้สร้างโครงงาน"}</p>
          {state.team.membership.role === "leader" && <Link className={styles.link} href="/projects">ไปสร้างโครงงาน →</Link>}
        </>}
      </section>
    </> : <section className={styles.card} aria-label="เริ่มสร้างทีม">
      <span className={styles.label}>เริ่มต้นใช้งาน</span><h3>คุณยังไม่มีทีม</h3>
      <p>สร้างทีมก่อนเริ่มโครงงาน หรือให้หัวหน้าทีมเพิ่มคุณเข้าทีมด้วยอีเมลที่สมัครไว้</p>
      <Link className={styles.link} href="/teams">เริ่มสร้างทีม →</Link>
    </section>)}
  </section>;
}

const ADVISOR_LINKS = [
  { href: "/advisor/invitations", title: "คำเชิญของฉัน", description: "อ่านและตอบคำเชิญจากทีมโครงงาน" },
  { href: "/advisor/projects", title: "โครงงานที่ปรึกษา", description: "ดูโครงงานที่คุณตอบรับเป็นอาจารย์ที่ปรึกษา" },
  { href: "/committee/projects", title: "งานกรรมการ", description: "ดูโครงงานที่ได้รับแต่งตั้ง ลงมติและประเมินตามสิทธิ์" },
];

export function WorkspaceScreen() {
  const router = useRouter();
  const { state, retry } = useSession();
  const expired = useCallback(() => router.replace("/login?reason=session"), [router]);
  useEffect(() => { if (state.status === "unauthenticated") expired(); }, [state.status, expired]);
  useEffect(() => {
    // Hide the previous user's overview until identity has been checked again.
    window.addEventListener("focus", retry);
    window.addEventListener("pageshow", retry);
    return () => { window.removeEventListener("focus", retry); window.removeEventListener("pageshow", retry); };
  }, [retry]);

  if (state.status === "loading" || state.status === "unauthenticated") {
    return <AuthShell><p className={styles.state} role="status">กำลังตรวจสอบการเข้าสู่ระบบ…</p></AuthShell>;
  }
  if (state.status === "error") {
    return <AuthShell><div className={styles.error} role="alert"><h1>ยังเชื่อมต่อระบบไม่ได้</h1><p>{state.message}</p>
      <button className={styles.textButton} onClick={retry}>ลองอีกครั้ง</button></div></AuthShell>;
  }
  const user = state.user;
  return <AuthShell><section aria-label="พื้นที่ทำงาน" className={styles.workspace}>
    <Link className={styles.backLink} href="/">← กลับหน้าบัญชี</Link>
    <header className={styles.heading}><span className={styles.badge}>{ROLES[user.role]}</span>
      <h1>พื้นที่ทำงาน</h1><p>สวัสดี, {user.full_name}</p><p>เลือกงานที่ต้องการดำเนินการต่อ</p>
    </header>
    {user.role === "student" ? <StudentOverview key={user.id} onExpired={expired} /> :
      <nav aria-label="ทางเข้างาน" className={styles.overview}>
        {(user.role === "advisor" ? ADVISOR_LINKS : [
          { href: "/coordinator/projects", title: "จัดการกรรมการโครงงาน", description: "จัดการกรรมการและอ่านผลของโครงงานที่คุณมีสิทธิ์เข้าถึง" },
        ]).map((item) => <Link className={styles.actionCard} key={item.href} href={item.href}>
          <span className={styles.actionTitle}>{item.title}<span aria-hidden="true">→</span></span><p>{item.description}</p>
        </Link>)}
      </nav>}
  </section></AuthShell>;
}
