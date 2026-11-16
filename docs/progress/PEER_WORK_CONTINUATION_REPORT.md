# พัฒนาส่วนที่เพื่อนยังขาด — 2026-11-16

**รอบถัดมา:** ผู้ใช้ยืนยันและพัฒนา [Task/Assignee/History ต่อจาก Milestoneแล้ว](TASK_IMPLEMENTATION_REPORT.md) ข้อความนอก scope/ยังไม่มี Task ในรายงานนี้บันทึกสถานะก่อนรอบ Task ให้ดูรายงานใหม่สำหรับ source/ผลตรวจปัจจุบัน

ทำต่อบน local `feature/team-integration` (HEAD `6040702` + working tree ที่รวม Backend Submission แล้ว) จากคำสั่งเจ้าของ “ดำเนินการในส่วนของเพื่อนที่ยังไม่ได้ทำต่อเลย” และคำยืนยันเพิ่มเติม “เริ่ม Milestone สำหรับทีมตามขอบเขตนี้” ไม่มี Commit/Push

เพื่อนยังเผยแพร่ snapshot `31c4fcb` เดิม จึงรักษาที่มา Backend Submission ตาม [integration report](SUBMISSION_INTEGRATION_REPORT.md) แล้วรับช่วงพัฒนา UI/ฟังก์ชันที่ไม่พบใน snapshot ไม่แก้ branch เพื่อน ไม่เอา Supabase runtime/config มาเปิดใช้

## ฟังก์ชันที่เพิ่ม

| ส่วน | ไฟล์หลัก | พฤติกรรม |
| --- | --- | --- |
| Submission UI | `frontend/src/features/submissions/api.ts`, `submission-screen.tsx`, `submissions.module.css` และ routes `/projects/submissions`, `/advisor/submissions` | หัวหน้าส่ง PDF/PPTX, สมาชิกดูประวัติและดาวน์โหลด, อาจารย์อนุมัติ/ขอแก้ไขพร้อมคำแนะนำและยืนยันครั้งเดียว; แสดง immutable snapshot/history และใช้ eligibility จริง |
| Milestone Backend | `backend/milestone_api.py`, `milestone_store.py` | 5 operations/2 paths ตาม [Contract](../api/MILESTONES_CONTRACT.md): student อ่านทีมตน หัวหน้าสร้าง/แก้/ลบผ่าน controlled functions เดิม; ทุก ID เป็น string |
| Milestone UI | `frontend/src/features/milestones/` และ route `/projects/milestones` | รายการเรียง due_date/id, สร้าง/แก้ metadata, ยืนยันก่อนลบ, สมาชิกอ่านอย่างเดียว, ไม่มี status dropdown หรือ Task API |
| Navigation | หน้าบัญชีและหน้า Project | เพิ่มทางเข้า Submission สำหรับอาจารย์ และ Submission/Milestone สำหรับทีม ไม่เปลี่ยนหน้า Login หรือ Workspace เดิม |
| จุดต่อ Backend/tests | main, test_auth_security, test_project_api, auth_browser_server, http_concurrency, team_api_direct_smoke | เพิ่ม router/error/no-store และ DELETE CORS ที่ยืนยัน; exact OpenAPI 41 paths, borrowed UOW ครบ 9 รายการ; Project ยังไม่มี DELETE endpoint/R-01 คงเดิม |

## กฎ V1 และการป้องกันที่รักษา

- Runtime pin `student_project_management_v1_test`/`project_app` เหมือนเดิม ไม่มี DDL/grant หรือ backend.database/ฐานหลัก/.env เปลี่ยน
- Milestone ใช้ actor จาก session, Team→Project locks แล้ว recheck membership/leader; `v1_create_milestone`/`v1_update_milestone`/`v1_delete_milestone` เป็นผู้บังคับกฎและตั้ง metadata ไม่เปิด direct DML
- due_date เมื่อสร้างหรือเปลี่ยนค่าต้องไม่ก่อน DB Bangkok date; D-01 ไม่ย่อวันจน Task เกินกำหนดใหม่; ไม่มี advisor/topic approval gate เพิ่ม
- Status/updated/completed metadata คำนวณตาม Tasks; คะแนนแรกล็อก writes; FK RESTRICT ยังห้ามลบ Milestone ที่มี Task
- พบ PostgreSQL `23001`/constraint `tasks_milestone_id_fkey` จาก `v1_delete_milestone` เมื่อมี Task จึง map เป็น 409 MILESTONE_HAS_TASKS เฉพาะ constraint นี้ (รองรับ 23503 ด้วย) ไม่มีการเพิ่มสิทธิ์หรือใช้ owner ข้าม positive business request; 42501/SQLSTATE ที่ไม่รู้จักยังเป็น sanitized500
- Frontend ส่ง multipart ตรง FastAPI พร้อม session/CSRF โดยไม่ตั้ง boundary เอง ดาวน์โหลดผ่าน authorized fetch และชื่อ attachment ที่สร้างจาก ID ไม่มี public file URL/preview
- ตรวจ response/status/ID/project scope ก่อนแสดง success; abort เมื่อ unmount/เปลี่ยนบัญชีและตรวจ session หลังอ่านข้อมูล; ไม่เก็บ token/ข้อมูลธุรกิจใน local storage
- POST/PATCH/DELETE ไม่มี automatic retry; ถ้าผลเขียนไม่แน่นอนปิดการเขียนจนโหลดรายการ/ประวัติใหม่ ไม่แสดง “กำลังบันทึก” ค้างหลัง request จบแต่ยังไม่รู้ผล

## ผลทดสอบ

| ชุด | ผลล่าสุด | ขอบเขต |
| --- | --- | --- |
| Milestone HTTP/PostgreSQL | 8 PASS | create/read/order/no-op/update/delete, Unicode/duplicate/date/spoof, member/cross-project/exit, D-01/FK, derived status, first-score lock, CORS/CSRF/Origin, atomic failure; outer ROLLBACK |
| Focused Browser | **13/13 PASS**, 15.3s | Submission7 + Milestone6; metadata/ACL/row counts คืน baseline, fixture connections0 |
| Lint | PASS | ESLint รวม source/tests ใหม่ |
| TypeScript | PASS | standalone tsc และ production build type checking |
| Production build | PASS | มี 3 routes ใหม่ ไม่มีการต่อ DB ระหว่าง build |
| Full Backend | **553 PASS**, 68.575s | 35 modules; full public values/metadata/owners/ACL/Auth counts คืน baseline หลัง ROLLBACK (sequences excluded); รอบแรกติด assertion CORS เดิมที่ยังไม่รวม DELETE ที่เพิ่งอนุมัติ แก้ expected set โดยยังตรวจ exact methods และ untrusted Origin แล้ว |
| Full Browser | **122/122 PASS**, 1.8 นาที | ชุดเดิม109 + ใหม่13; metadata/ACL/row counts คืน baseline, fixture connections0 |
| Direct LOGIN app | PASS | physical/effective `project_app` บน test DB จริง: Milestone create201/PATCH200/DELETE204 โดยไม่มี advisor gate และ ROLLBACK คืน metadata/ACL/row counts; ไม่ใช้ owner ใน request connection |
| Postflight/ตรวจ source | PASS | baseline52 functions/differences=[]/effective app ACL ตรงเดิม; Python syntax/ลิงก์เอกสาร/whitespace ผ่าน ไม่พบค่าลับ `.env` ตามค่าที่ตรวจ; source SQL/Auth/Team/Project business stores เดิมไม่เปลี่ยน |

Focused Browser เป็น real HTTP/Browser→FastAPI→PostgreSQL สำหรับ upload PDF/snapshot/download bytes/review/revision/history, Milestone CRUD/member read และ double-submit/uncertain response; บาง error recovery/malformed response เป็น transport mocks (เช่น Milestone Task conflict/DELETE200) ส่วน D-01/Task FK/first-score guard พิสูจน์จริงใน Backend tests ไม่อ้างว่าทุกกรณีเป็น DB happy path

พบ test selectors ชน Next route announcer จึงจำกัดการหา alert ภายใน feature region; ยังตรวจข้อความจริง ไม่แก้ runtime เพื่อหลบ assertion PPTX parser/upload พิสูจน์ใน Backend ส่วน Browser positive file รอบนี้เป็น PDF ไม่ใช่ PPTX

คำสั่งเฉพาะส่วน:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_milestone_api -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
Push-Location frontend
npm run test:e2e -- submissions.spec.ts milestones.spec.ts
Pop-Location
```

Full Backend ใช้คำสั่งอัปเดตใน [LOCAL_SETUP](../team/LOCAL_SETUP.md) และ Browser เต็มใช้ `npm run test:e2e` ทุกชุดเขียนเฉพาะ test DB/ROLLBACK; sequence values ไม่คืนด้วย ROLLBACK ไม่ทดสอบพร้อมการเขียนจาก server/ชุดอื่น

## งานที่ยังเหลือ

- Task API/UI, assignees/history และหน้าอ่าน Milestone ของ advisor/coordinator ยังไม่อยู่ในขอบเขตที่ยืนยัน ไม่สร้าง endpoint เพิ่มโดยเดา
- ยังไม่ทำ Milestone/Submission concurrency ชุดใหม่หรือ winner-COMMIT และไม่เปิด Supabase
- Milestone ที่ผู้ใช้สร้างใหม่ยังไม่มีทางเพิ่ม Task/ทำให้ completed ผ่าน UI รอบนี้ จึงยังเตรียม prerequisite Evaluation ทั้งหมดจาก UI อย่างเดียวไม่ได้
- Manual UAT, fresh Windows installation, Browser positive PPTX และ file/parser security ทุก boundary ยังไม่ได้ยืนยันครบ แม้ flow พื้นฐานผ่าน
- อัปเดต [คู่มือ](../user/USER_GUIDE.md) และ [Manual UAT](../uat/MANUAL_UAT.md) เพิ่ม UA21–UA22 เป็นแผน22กรณี ผลจริงโดยผู้ใช้ยัง Not Run
- P11/P13/P17/P19 คง In Progress; Done6/20=30% ตาม checklist เดิม ไม่เพิ่มเปอร์เซ็นต์จากจำนวน tests
