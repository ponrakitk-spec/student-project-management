# Task / Assignee / History — 2026-11-16

Local `feature/team-integration` ฐาน `6040702` + working tree เดิมที่รวม Submission/Milestone แล้ว ผู้ใช้สั่งพัฒนาต่อและเลือก “พัฒนา Task/ผู้รับผิดชอบตามร่างครบ workflow” ตาม [Contract](../api/TASKS_CONTRACT.md) ไม่มีการอนุมัติแก้ Schema/RBAC หรือเปิด Supabase

## Source ที่เตรียม

- `backend/task_validation.py`: pure fields validation ตาม V1 ไม่ใช้ Python/browser clock ตัดสิน business date หรือเดา state transitions
- `backend/task_store.py`, `task_api.py`: 10 operations/6 paths สำหรับทีมตนเอง ทุก write ผ่าน controlled functions เดิม actor จาก session ล็อก Team→Project และให้ function ล็อก Milestone→Task; recheck membership/leader และ first-score lock
- main/router/validation/storage/no-store, exact OpenAPI และ Browser/HTTP harness อัปเดต Task UOW เป็นรายการที่10 ไม่มี CORS methods เพิ่มจาก Milestone รอบก่อน
- `frontend/src/features/tasks/`, route `/projects/milestones/[milestone_id]/tasks` และลิงก์จาก Milestone: create/partial edit/status, เลือกสมาชิกทีมเพื่อ assign, ยืนยัน unassign/delete และอ่าน history จริง ไม่มี local-storage tokens หรือ write retry
- Client ตรวจ status/ID/milestone/project scope และ session หลังอ่าน; write ที่ผลไม่แน่นอนต้อง GET ใหม่ก่อนทำซ้ำ มี pending guard/abort ป้องกัน double submit และข้อมูลข้ามบัญชี
- Tests ใหม่: `test_task_validation.py`, `test_task_store.py`, `test_task_api.py`, `frontend/tests/tasks.spec.ts` และเพิ่ม direct app smoke สำหรับ Task→assignee→Milestone completion/history

ไม่แก้ตาราง/ฟังก์ชัน SQL/grants, backend.database, auth_store หรือ `.env` ไม่สร้างข้อมูลถาวร/บัญชีอาจารย์เพิ่มในรอบพัฒนา ยังไม่ Commit/Push

## ผลทดสอบล่าสุด

| ชุด | ผล |
| --- | --- |
| Offline Task validation | 8 PASS |
| Offline Task storage error boundaries | 5 PASS: unknown42501/timeout/trigger/constraint ไม่ถูกตีความเป็น business conflict |
| รวม Task offline + Auth security + HTTP safeguards | 52 PASS ไม่มีการต่อ DB |
| Python AST / TypeScript / ESLint | PASS |
| Task HTTP/PostgreSQL | **12 PASS**: CRUD/nullable dates/unique/roles/transition/assignee/history/cascade/C-02/first-score lock/atomic failure และ flow HTTP ตั้งแต่ Submission ถึง Evaluation |
| Direct LOGIN project_app | PASS: create/assign/complete/reopen/last-assignee409/unassign/history/delete และคืน baseline ไม่ใช้ owner ใน request connection |
| Full Backend | **578 PASS**, 73.598s / 38 modules; full public values/metadata/owners/ACL/Auth counts คืน baselineหลัง ROLLBACK (sequence values excluded) |
| Focused Task Browser | **8/8 PASS**, 45.1s พร้อมคืน metadata/ACL/counts/fixture connections0 |
| Full Browser | **130/130 PASS**, 2.4นาที (122เดิม+8ใหม่); รวมมือถือชื่อMilestone255ตัว/pending assignment/whole API–UI flow พร้อม ROLLBACK/fixture connections0 |
| Production build | PASS มี dynamic Task route และ TypeScript ผ่าน ไม่มี DB connection ระหว่าง build |
| เปิดเว็บหลังพัฒนา | PASS: Backend8001ตอบ200/OpenAPI47pathsมีTask, Frontend3000ตอบ200/dynamic Task routeโหลดได้และredirectผู้ไม่Login; BrowserเรียกAPI8001เท่านั้น ใช้ROLLBACKและไม่seedstaff/phaseอัตโนมัติ |
| Source/postflight | PASS: baseline52functions/differences=[]/ACLตรงเดิม, Python syntax/TypeScript/lint/ลิงก์/whitespaceผ่าน ไม่มีค่าลับจาก.envตามค่าที่ตรวจ ไม่มีprotected SQL/Auth/Team/Project storesเปลี่ยนหรือstaging |

ผล Backend553/Browser122 ของ [รอบก่อน](PEER_WORK_CONTINUATION_REPORT.md) เป็น historical evidence ก่อนเพิ่ม Task ผลปัจจุบันใช้ชุด578/130ด้านบน ไม่บวกจำนวน tests ต่างรอบเข้าด้วยกันเพื่ออ้าง coverage

ผู้ใช้อนุมัติปิดรอบทดลองก่อนทดสอบแล้ว ก่อนปิดตรวจพบ committed `public.users` และ `auth.credentials` เพิ่มอย่างละ2จากคำขอสร้างบัญชี CLI ไม่มีจำนวนแถวตารางอื่นเพิ่ม เก็บ baseline ล่าสุดนี้แล้วปิดเฉพาะสอง server ของเรา ตรวจหลังปิด metadata/ACL/counts กลับ baseline และ fixture connections0 บัญชีถาวรทั้งสองคู่ยังอยู่ครบ ไม่ย้อนหรือลบเพื่อให้เท่ากับ snapshot เก่า

## ขั้นตอนตรวจ/เปิดเว็บรอบนี้

1. เก็บ committed baseline ล่าสุดก่อนปิด เพราะผู้ใช้อาจสร้างบัญชีอาจารย์ถาวรผ่าน CLI ระหว่างรอบ ไม่ลบหรือย้อนบัญชีเหล่านั้นเพื่อให้ snapshot เก่าตรง
2. ปิดเฉพาะ Frontend3000/Backend8001 ของรอบที่เปิดให้ทดลอง ข้อมูลสมัคร/ทีม/Project/Submission/ไฟล์ใน outer ROLLBACK จะถูกยกเลิก ต้องให้ผู้ใช้รับทราบก่อน
3. ตรวจหลังปิดว่าข้อมูล/metadata/ACL กลับ baseline ล่าสุดและ fixture connections0 จากนั้นตรวจชื่อ test DB ก่อนชุดเขียนทุกครั้ง
4. รัน Task HTTP tests/direct LOGIN project_app, focused Browser8, Full Backend/Browser และตรวจคืน baseline; ถ้าพบ42501ให้รายงานSQLSTATE/function/grant ไม่เพิ่มสิทธิ์หรือใช้ownerข้าม business request
5. พิสูจน์ flow ข้อมูล Project ใหม่: accepted advisor→upload/review→committee/vote→Task UI assign/complete→Milestone derived completed→Evaluation UI ให้คะแนนได้ โดยไม่ใช้ SQL ทำ phase shortcut ในกรณี Browser นี้
6. เปิดเว็บรุ่นใหม่ด้วยโหมด8001/ROLLBACK หลังตรวจผ่าน ตามคำขอให้รันเว็บหลังพัฒนาเสร็จ

## กฎที่ยังต้องรักษา

สมาชิกปัจจุบันเปลี่ยน status ของงานที่ยังไม่ completed ได้แม้ไม่ใช่ assignee ตาม V1; หัวหน้าเท่านั้นที่แก้ metadata/จัด assignee/ลบ/reopen completed ไม่เพิ่มกฎ “เฉพาะ assignee เปลี่ยนสถานะได้” เอง

เข้า in_progress/completed ต้องมี assignee≥1; completed→not_started ไม่ได้; completedต้องreopenก่อนแก้ metadata/ลบ และหลังคะแนนแรกล็อก writes ประวัติถอนงานเกิดจาก DB เท่านั้น Task delete cascade ไม่สร้าง history ถอนเทียม

หาก completed Task เหลือ0 assigneesหลัง member exit ตามC-02 จะยังเปิดกลับไม่ได้ (in_progressต้องมีassignee แต่ completedล็อกassignment) UI แจ้งข้อจำกัดตามกฎเดิม ไม่มี autoassign/reopen หรือเปลี่ยน SQL เพื่อข้ามข้อกำหนด

การอ่าน Task ของ advisor/coordinator, dashboard metrics, contribution และ concurrency/winner-COMMIT ชุดใหม่ยังนอกขอบเขต การเปิดให้กรรมการประเมินยังต้องผ่าน Topic vote เดิม ไม่ข้ามขั้นเพียงเพราะมี completed Milestone
