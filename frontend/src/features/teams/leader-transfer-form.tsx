"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { transferLeader, TeamApiError, teamErrorMessage, type CurrentTeam, type TeamMember } from "./api";
import styles from "./teams.module.css";

export function LeaderTransferForm({ members, actorId, onTransferred, onCheck, onUnauthenticated }: {
  members: TeamMember[]; actorId: string; onTransferred: (team: CurrentTeam) => void;
  onCheck: () => void; onUnauthenticated: () => void;
}) {
  const candidates = members.filter((member) => member.user_id !== actorId && member.role === "member");
  const [selectedId, setSelectedId] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checkNeeded, setCheckNeeded] = useState(false);
  const [loginNeeded, setLoginNeeded] = useState(false);
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const target = candidates.find((member) => member.id === selectedId);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || checkNeeded) return;
    setError(""); setLoginNeeded(false);
    if (!target) { setError("กรุณาเลือกสมาชิกที่จะรับหน้าที่หัวหน้า"); return; }
    if (!confirming) { setConfirming(true); return; }
    const controller = new AbortController(); request.current = controller;
    pending.current = true; setBusy(true);
    try {
      const team = await transferLeader(target.id, controller.signal);
      if (!controller.signal.aborted) onTransferred(team);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof TeamApiError && ["TEAM_NOT_FOUND", "TEAM_ACCESS_FORBIDDEN", "TEAM_LEADER_TRANSFER_FORBIDDEN"].includes(cause.code)) { onCheck(); return; }
      setError(cause instanceof TeamApiError && cause.status === 422 ? "กรุณาเลือกสมาชิกจากรายชื่อทีมอีกครั้ง" : teamErrorMessage(cause));
      setLoginNeeded(cause instanceof TeamApiError && cause.code === "CSRF_INVALID");
      setCheckNeeded(!(cause instanceof TeamApiError) || cause.status >= 500
        || (cause instanceof TeamApiError && cause.code === "TEAM_MEMBER_NOT_FOUND"));
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }

  return <section className={styles.transferSection} aria-label="โอนหัวหน้าทีม">
    <h3>โอนหัวหน้าทีม</h3>
    {!candidates.length ? <p className={styles.hint}>ต้องมีสมาชิกอีกคนในทีมก่อนจึงจะโอนหัวหน้าได้</p> : <>
      <p className={styles.hint}>เลือกสมาชิกในทีมเพื่อรับหน้าที่หัวหน้า คุณจะยังอยู่ในทีมในฐานะสมาชิก</p>
      {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
        {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบทีมอีกครั้ง</button>}
      </div>}
      <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
        <div className={styles.field}><label htmlFor="leader-transfer-target">สมาชิกที่จะเป็นหัวหน้าคนใหม่</label>
          <select id="leader-transfer-target" value={selectedId} disabled={busy || confirming || checkNeeded} onChange={(event) => setSelectedId(event.target.value)}>
            <option value="">เลือกสมาชิก</option>
            {candidates.map((member) => <option key={member.id} value={member.id}>{member.full_name} (สมาชิก #{member.id})</option>)}
          </select>
        </div>
        {confirming && target && <div className={styles.transferConfirmation} role="group" aria-label="ยืนยันการโอนหัวหน้า">
          <p>คุณกำลังโอนหน้าที่หัวหน้าให้ <strong>{target.full_name}</strong> (สมาชิก #{target.id})</p>
          <p>หลังยืนยัน คุณจะเป็นสมาชิกและใช้เครื่องมือหัวหน้าไม่ได้จนกว่าจะได้รับโอนกลับ</p>
        </div>}
        <div className={styles.editActions}>
          <button type="submit" className={styles.primaryButton} disabled={busy || checkNeeded}>
            {busy ? "กำลังโอนหัวหน้า…" : confirming ? "ยืนยันโอนหัวหน้า" : "ตรวจสอบการโอนหัวหน้า"}
          </button>
          {confirming && <button type="button" className={styles.secondaryButton} disabled={busy} onClick={() => { setConfirming(false); if (!checkNeeded) setError(""); }}>ยกเลิก</button>}
        </div>
      </form>
    </>}
  </section>;
}
