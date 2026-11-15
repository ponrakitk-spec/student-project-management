"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { trimAscii } from "@/features/auth/api";
import { updateProject, ProjectApiError, projectErrorMessage, projectFieldMessages, validateProjectInput, type Project } from "./api";
import styles from "./projects.module.css";

export function ProjectEditForm({ project, onUpdated, onCancel, onCheck, onUnauthenticated }: {
  project: Project; onUpdated: (project: Project) => void; onCancel: () => void;
  onCheck: () => void; onUnauthenticated: () => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
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
    const invalid = validateProjectInput(name, description);
    setFields(invalid); setError(""); setLoginNeeded(false);
    if (Object.keys(invalid).length) return;
    const changes: { name?: string; description?: string | null } = {};
    if (trimAscii(name) !== project.name) changes.name = trimAscii(name);
    const normalizedDescription = trimAscii(description) || null;
    if (normalizedDescription !== project.description) changes.description = normalizedDescription;
    // A no-op still asks the server to verify current authority and phase.
    if (!Object.keys(changes).length) changes.name = project.name;
    const controller = new AbortController(); request.current = controller;
    pending.current = true; setBusy(true);
    try {
      const updated = await updateProject(changes, controller.signal);
      if (!controller.signal.aborted) onUpdated(updated);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ProjectApiError && cause.status === 401) { onUnauthenticated(); return; }
      if (cause instanceof ProjectApiError && ["PROJECT_UPDATE_FORBIDDEN", "TEAM_NOT_FOUND", "PROJECT_NOT_FOUND", "PROJECT_ACCESS_FORBIDDEN"].includes(cause.code)) { onCheck(); return; }
      setError(projectErrorMessage(cause)); setFields(projectFieldMessages(cause));
      setLoginNeeded(cause instanceof ProjectApiError && cause.code === "CSRF_INVALID");
      setCheckNeeded(!(cause instanceof ProjectApiError) || cause.status >= 500);
    } finally { pending.current = false; if (!controller.signal.aborted) setBusy(false); }
  }

  return <section className={styles.editPanel} aria-label="แก้ไขโครงงาน">
    <h2>แก้ไขข้อมูลโครงงาน</h2>
    <p className={styles.hint}>แก้ไขได้เฉพาะช่วงที่สถานะการส่งโครงงานอนุญาต การแก้ไขไม่เปลี่ยนข้อมูลที่ส่งไปแล้ว</p>
    {error && <div className={styles.errorBox} role="alert"><p>{error}</p>
      {loginNeeded ? <Link href="/login">เข้าสู่ระบบใหม่</Link> : <button type="button" onClick={onCheck}>ตรวจสอบโครงงานอีกครั้ง</button>}
    </div>}
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={busy}>
      <div className={styles.field}><label htmlFor="project-edit-name">ชื่อโครงงาน</label>
        <input id="project-edit-name" name="name" value={name} onChange={(event) => setName(event.target.value)} disabled={busy} required autoComplete="off"
          aria-invalid={Boolean(fields.name)} aria-describedby={fields.name ? "project-edit-name-error" : "project-edit-name-hint"} />
        {fields.name ? <p id="project-edit-name-error" className={styles.fieldError}>{fields.name}</p> : <p id="project-edit-name-hint" className={styles.hint}>ไม่เกิน 255 ตัวอักษร</p>}
      </div>
      <div className={styles.field}><label htmlFor="project-edit-description">คำอธิบายโครงงาน <span className={styles.optional}>(ไม่บังคับ)</span></label>
        <textarea id="project-edit-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={busy}
          aria-invalid={Boolean(fields.description)} aria-describedby={fields.description ? "project-edit-description-error" : undefined} />
        {fields.description && <p id="project-edit-description-error" className={styles.fieldError}>{fields.description}</p>}
      </div>
      <div className={styles.editActions}>
        <button className={styles.primaryButton} type="submit" disabled={busy || checkNeeded}>{busy ? "กำลังบันทึก…" : "บันทึกการแก้ไข"}</button>
        <button className={styles.secondaryButton} type="button" disabled={busy} onClick={onCancel}>ยกเลิก</button>
      </div>
    </form>
  </section>;
}
