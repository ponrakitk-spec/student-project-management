"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { leaveTeam, removeTeamMember, TeamApiError, teamErrorMessage, type TeamMember } from "./api";
import styles from "./teams.module.css";

export function MembershipExitAction({ mode, target, onComplete, onCheck, onUnauthenticated }: {
  mode: "leave" | "remove"; target: TeamMember; onComplete: () => void;
  onCheck: () => void; onUnauthenticated: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checkNeeded, setCheckNeeded] = useState(false);
  const [loginNeeded, setLoginNeeded] = useState(false);
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const leaving = mode === "leave";
  async function submit() {
    if (pending.current || checkNeeded) return;
    const controller = new AbortController(); request.current = controller;
    pending.current = true; setBusy(true); setError(""); setLoginNeeded(false);
    try {
      if (leaving) await leaveTeam(controller.signal);
      else await removeTeamMember(target.id, controller.signal);
      if (!controller.signal.aborted) onComplete();
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof TeamApiError && ["TEAM_NOT_FOUND", "TEAM_ACCESS_FORBIDDEN", "TEAM_MEMBER_REMOVAL_FORBIDDEN"].includes(cause.code)) { onCheck(); return; }
      setError(teamErrorMessage(cause));
      setLoginNeeded(cause instanceof TeamApiError && cause.code === "CSRF_INVALID");
      setCheckNeeded(!(cause instanceof TeamApiError) || cause.status >= 500
        || (cause instanceof TeamApiError && cause.code === "TEAM_MEMBER_NOT_FOUND"));
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }

  return <div className={styles.exitAction}>
    {!confirming && <button type="button" className={styles.textButton} disabled={checkNeeded} onClick={() => setConfirming(true)}
      aria-label={leaving ? "ออกจากทีม" : `ถอด ${target.full_name} (สมาชิก #${target.id})`}>{leaving ? "ออกจากทีม" : "ถอดสมาชิก"}</button>}
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบทีมอีกครั้ง</button>}
    </div>}
    {confirming && <div className={styles.transferConfirmation} role="group" aria-label={leaving ? "ยืนยันการออกจากทีม" : "ยืนยันการถอดสมาชิก"}>
      <p>{leaving ? "ยืนยันออกจากทีมของคุณ" : `ยืนยันถอด ${target.full_name} (สมาชิก #${target.id})`}</p>
      <p>{leaving ? "คุณจะยังเข้าสู่ระบบได้ แต่สิทธิ์เข้าถึงข้อมูลทีมและโครงงานจากสมาชิกภาพนี้จะสิ้นสุด" : "สมาชิกคนนี้จะเสียสิทธิ์เข้าถึงข้อมูลทีมและโครงงานจากสมาชิกภาพนี้"}</p>
      <p>การมอบหมายงานจะถูกถอนตามกฎ หากมีงานที่กำลังทำและไม่มีผู้รับผิดชอบคนอื่น ระบบจะปฏิเสธทั้งรายการ</p>
      <div className={styles.editActions}>
        <button type="button" className={styles.primaryButton} disabled={busy || checkNeeded} onClick={() => void submit()}>
          {busy ? "กำลังดำเนินการ…" : leaving ? "ยืนยันออกจากทีม" : "ยืนยันถอดสมาชิก"}
        </button>
        <button type="button" className={styles.secondaryButton} disabled={busy} onClick={() => { setConfirming(false); if (!checkNeeded) setError(""); }}>ยกเลิก</button>
      </div>
    </div>}
  </div>;
}
