"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { trimAscii } from "@/features/auth/api";
import { updateTeam, TeamApiError, teamErrorMessage, teamFieldMessages, validateTeamInput, type CurrentTeam } from "./api";
import styles from "./teams.module.css";

export function TeamEditForm({ team, onUpdated, onCancel, onCheck, onUnauthenticated }: {
  team: CurrentTeam; onUpdated: (team: CurrentTeam) => void; onCancel: () => void;
  onCheck: () => void; onUnauthenticated: () => void;
}) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [loginNeeded, setLoginNeeded] = useState(false);
  const [checkNeeded, setCheckNeeded] = useState(false);
  const pending = useRef(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || checkNeeded) return;
    const invalid = validateTeamInput(name, description);
    setFields(invalid); setError(""); setLoginNeeded(false);
    if (Object.keys(invalid).length) return;
    const changes: { name?: string; description?: string | null } = {};
    if (trimAscii(name) !== team.name) changes.name = trimAscii(name);
    const normalizedDescription = trimAscii(description) || null;
    if (normalizedDescription !== team.description) changes.description = normalizedDescription;
    if (!Object.keys(changes).length) changes.name = team.name;
    const controller = new AbortController(); request.current = controller;
    pending.current = true; setBusy(true);
    try {
      const updated = await updateTeam(changes, controller.signal);
      if (!controller.signal.aborted) onUpdated(updated);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof TeamApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof TeamApiError && ["TEAM_UPDATE_FORBIDDEN", "TEAM_NOT_FOUND", "TEAM_ACCESS_FORBIDDEN"].includes(cause.code)) { onCheck(); return; }
      setError(teamErrorMessage(cause)); setFields(teamFieldMessages(cause));
      setLoginNeeded(cause instanceof TeamApiError && cause.code === "CSRF_INVALID");
      setCheckNeeded(!(cause instanceof TeamApiError) || cause.status >= 500);
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }

  return <section className={styles.editPanel} aria-label="แก้ไขทีม">
    <h2>แก้ไขข้อมูลทีม</h2>
    <p className={styles.hint}>แก้ไขได้เฉพาะช่วงที่สถานะโครงงานอนุญาต ข้อมูลสมาชิกและโครงงานคงเดิม</p>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบทีมอีกครั้ง</button>}
    </div>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      <div className={styles.field}><label htmlFor="team-edit-name">ชื่อทีม</label>
        <input id="team-edit-name" name="name" value={name} onChange={(event) => setName(event.target.value)} disabled={busy} required autoComplete="off"
          aria-invalid={Boolean(fields.name)} aria-describedby={fields.name ? "team-edit-name-error" : "team-edit-name-hint"} />
        {fields.name ? <p id="team-edit-name-error" className={styles.fieldError}>{fields.name}</p> : <p id="team-edit-name-hint" className={styles.hint}>ไม่เกิน 255 ตัวอักษร</p>}
      </div>
      <div className={styles.field}><label htmlFor="team-edit-description">คำอธิบายทีม <span className={styles.optional}>(ไม่บังคับ)</span></label>
        <textarea id="team-edit-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={busy}
          aria-invalid={Boolean(fields.description)} aria-describedby={fields.description ? "team-edit-description-error" : undefined} />
        {fields.description && <p id="team-edit-description-error" className={styles.fieldError}>{fields.description}</p>}
      </div>
      <div className={styles.editActions}>
        <button className={styles.primaryButton} type="submit" disabled={busy || checkNeeded}>{busy ? "กำลังบันทึก…" : "บันทึกการแก้ไข"}</button>
        <button className={styles.secondaryButton} type="button" disabled={busy} onClick={onCancel}>ยกเลิก</button>
      </div>
    </form>
  </section>;
}
