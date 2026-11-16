# รวม Backend Submission กับระบบเดิม — 2026-11-16

**รอบต่อมา:** เจ้าของสั่งรับช่วงส่วนที่เพื่อนยังไม่ได้ทำ และยืนยัน Milestone สำหรับทีมแล้ว มี [Submission UI/Milestone API/UI และผลล่าสุด](PEER_WORK_CONTINUATION_REPORT.md) ข้อจำกัด UI/Task/transport ด้านล่างเป็นสถานะรอบรวม Backend ก่อนเริ่มงานใหม่ ให้ใช้รายงานล่าสุดเพื่อดูสถานะปัจจุบัน

Local branch `feature/team-integration` จากงานของเรา `6040702d75044645bdb67c3894be2553ee7e1351` รับ source ของเพื่อนจาก `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` (`origin/feature/database-schema2`) แบบเลือกไฟล์และผสานจุดเชื่อม ไม่ได้ merge ทั้ง branch หรือแก้ branch ต้นทาง ไม่มี Commit/Push ในรอบนี้

เจ้าของยืนยันข้อเสนอใน [integration review](../team/INTEGRATION_REVIEW_2026-11-16.md) แล้ว: รับ Backend Submission ทั้ง 7 operations ตาม [Contract](../api/SUBMISSIONS_CONTRACT.md), คง `student_project_management_v1_test`/`project_app` และพัก Supabase ไว้ก่อน ไม่เปลี่ยน Schema/RBAC หรือ Requirements

## งานที่รับและจุดที่แก้

| ไฟล์/ส่วน | สิ่งที่ทำ |
| --- | --- |
| `backend/submission_api.py`, `submission_validation.py` | รับ source เพื่อนโดยคงพฤติกรรมเดิม: session/Origin/CSRF, multipart หนึ่งไฟล์, ตรวจ PDF/PPTX และ body/file limits |
| `backend/submission_store.py` | รับ repository ของเพื่อน ใช้ `auth_store` ของเราโดยไม่เพิ่ม configurable DB/role; กำหนด transaction-local statement timeout 15s/lock timeout 3s เพื่อคุม borrowed fixture connection ด้วย |
| `backend/main.py` | เพิ่ม router, error dispatch, no-store, body-limit middleware ให้ CORS อยู่ชั้นนอก รักษา Auth/Team/Project/Invitation/Committee/Vote/Evaluation และ PATCH เดิม; รวม OpenAPI 39 paths โดยเพิ่ม Submission 7 operations/6 paths |
| `backend/requirements.txt` | คงรายการเดิม เพิ่มเฉพาะ `python-multipart==0.0.33`, `pypdf==7.0.0`, `python-pptx==1.0.2` ตาม source เพื่อน |
| `backend/tests/test_submission_api.py` | รับ 6 tests เดิมและเพิ่ม 4 tests เชื่อม workflow/สิทธิ์/atomic failure; แก้ UOW overrides ครบ 8 รายการ, กันการเปิด runtime connection หลุด fixture, เทียบ baseline+delta, เพิ่มสมาชิกก่อน pending phase และแก้ duplicate CSRF cookie ใน fixture |
| `backend/tests/test_submission_api_unit.py`, `test_submission_validation.py` | รับ tests แบบ offline/in-memory ของเพื่อน 8 กรณี |
| `backend/tests/test_auth_security.py` | คง exact OpenAPI check และเพิ่ม paths/verbs ของ Submission |
| `backend/tests/auth_browser_server.py`, `http_concurrency.py` | เพิ่ม Submission UOW เข้าชุด borrowed transaction ครบ 8 รายการ ไม่เปลี่ยนวิธี seed/commit/cleanup; HTTP concurrency helper ยังตรวจว่า override ครบทุก router |
| `backend/tests/team_api_direct_smoke.py` | เพิ่ม direct LOGIN `project_app` ตรวจ history/eligibility และห้ามส่งก่อน advisor ตอบรับ พร้อมตรวจไม่มี Submission/file เพิ่ม |
| เอกสาร | Contract, Backlog, README, Team Start Here/Local Setup, review และบันทึกรับช่วง อธิบายสถานะ Backend แยกจาก UI/Milestone/Supabase |

`auth_store.py`, Team/Project business code และ source SQL V1/Auth/RBAC คงเดิม ไม่รับไฟล์ generated `.pyc` 17 รายการ, config tests สำหรับ Supabase, SQL bootstrap หรือ Frontend รุ่นเก่าจาก peer มาทับระบบเรา

## ผลทดสอบจริง

| ชุด | ผล | ขอบเขต |
| --- | --- | --- |
| ติดตั้ง requirements / pip check | PASS | Python 3.12 venv เดิม ติดตั้ง 3 packages ใหม่พร้อม transitive dependencies โดยไม่เปลี่ยน versions เดิม; ไม่ใช่ fresh-machine install |
| Static Gate | PASS | V1 14 tables/28 FK/52 functions/24 triggers และ R-01; static check ไม่แทน runtime |
| Baseline readonly | PASS | test DB ที่ pin ไว้, 52 function definitions ตรง source และ effective app ACL ตรงเดิม |
| Targeted Submission + Auth security | 34 PASS | Submission integration 10 + validation 5 + in-memory HTTP 3 + Auth security 16; ไม่มี fixture ถาวรเพิ่ม |
| Full Backend | **545 PASS**, 66.537s | โหลด `test_*.py` จาก backend/tests และ database/tests รวม 34 modules; 527 เดิม + Submission 18 ไม่ใช่ 545 live concurrency cases |
| Full Backend cleanup | PASS | เทียบก่อน/หลังชุดด้วย readonly owner snapshot และ fingerprint: full public row values, metadata/owners/ACL และ Auth row counts คืนเดิม; sequence values ไม่รวมในการเทียบ |
| Direct LOGIN app smoke | PASS | `session_user=current_user=project_app`, test DB ถูกต้อง; history 200/eligibility false/upload 409 เมื่อยังไม่มี advisor; ไม่มี Submission/file ค้างและ metadata/ACL/counts คืน baseline |
| Browser regression | **109/109 PASS**, 1.6 นาที | UI เดิมทั้งหมด; `browser_database_rollback=PASS`, `fixture_connections=0` หลัง runner จบ ไม่ใช่ Submission UI tests |
| Postflight/ตรวจไฟล์ | PASS | หลัง Browser ตรวจ baseline 52 functions/ACL อีกครั้งตรงเดิม; Python syntax/ลิงก์เอกสาร/whitespace ผ่าน ไม่พบค่าลับจาก `.env` ตามค่าที่ตรวจ ไม่มี Frontend source หรือ protected Auth/Team/Project/SQL เปลี่ยน |

คำสั่งทดสอบเฉพาะส่วนจาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_submission_api backend.tests.test_submission_validation backend.tests.test_submission_api_unit backend.tests.test_auth_security -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
```

คำสั่ง Full Backend ที่รวม 34 modules อัปเดตไว้ใน [LOCAL_SETUP](../team/LOCAL_SETUP.md) ส่วน Browser ใช้ `npm run test:e2e` จาก frontend โดยต้องให้ 3000/8001 ว่างและไม่รันพร้อมการเขียน DB ชุดอื่น

## จุดเชื่อมที่พิสูจน์เพิ่ม

1. นักศึกษาสมัคร/Login → Team/Project/accepted advisor → upload PDF จริง → advisor review ผ่าน HTTP → Coordinator เห็น Project และแต่งตั้ง 3 กรรมการ → กรรมการดาวน์โหลด/ลงมติ → Team อ่านผล → Evaluation ครบและอ่านรวม/เฉลี่ยได้ โดย 8 UOW ใช้ outer ROLLBACK เดียวกัน
2. ช่วง Milestone/Task ระหว่าง Vote กับ Evaluation เตรียมผ่าน V1 controlled functions ตามกฎเดิมและ derived completed status เท่านั้น ไม่ใช่หลักฐานว่า Milestone HTTP API ของเพื่อนพร้อมใช้
3. กรรมการครบและขอแก้ไข → leader ส่งรอบใหม่ได้; history เก็บรอบเดิม, coordinator อ่านไฟล์ approved เดิมได้แต่ pending รอบใหม่ 404, กรรมการที่ได้รับแต่งตั้งอ่านไฟล์ได้ตาม G-12
4. สมาชิกอ่านไฟล์ได้ก่อนออกทีม; หลังออกได้ 404 และไม่เห็นประวัติทีมเดิม ส่วนสมาชิกที่ยังไม่ใช่ leader ส่งไม่ได้
5. จำลอง failure หลัง insert Submission/file ก่อนตอบ DTO ได้ sanitized 500 และทั้งสองตารางกลับ baseline ไม่มี false 201/orphan

การรันชุดเพื่อนครั้งแรกพบ fixture ล้มเหลว 2 จุด: duplicate cookie และเพิ่มสมาชิกหลัง pending (SQLSTATE P0001 ตาม phase guard) แก้เฉพาะ fixture/ลำดับการทดสอบแล้ว ชุดสุดท้ายผ่านทั้งหมด ไม่มีการแก้ DB rule หรือเพิ่มสิทธิ์เพื่อให้ผ่าน

## ข้อจำกัดและงานถัดไป

- Submission UI `/projects/submissions`, `/advisor/submissions` และ Milestone API/UI ยังไม่อยู่ใน remote snapshot ของเพื่อน ไม่ได้สร้างซ้ำในรอบรวม Backend
- ทดสอบ HTTP + PostgreSQL ชุดใหม่ผ่าน TestClient/ASGI และ effective `project_app` บน fixture connection ที่เตรียม staff ด้วย owner; direct app smoke แยกพิสูจน์ read/negative guard ไม่อ้างว่า positive upload→review ครบใช้ direct LOGIN app หรือ live TCP แล้ว
- การรวมหลาย transaction พร้อมกันของ Submission API ใหม่, winner-COMMIT, parser/security boundary ทุกแบบ, fresh Windows install และ Manual UAT ระบบรวมยัง Not Verified/Not Run ตามประเภทหลักฐาน
- ไม่ย้าย runtime ไป Supabase, ไม่รัน roles/bootstrap, ไม่เปลี่ยน `.env`, ไม่แก้ DB หลัก และไม่มีข้อมูลทดสอบ COMMIT ค้าง
- P11/P17/P19 คง In Progress; Done checklist ยัง 6/20=30% ไม่คำนวณความคืบหน้าจากจำนวน tests

ขั้นต่อไปคือรับ Submission UI/Milestone source ที่เพื่อนพร้อมส่ง แล้วทบทวน Contract และทดสอบเส้นทางใหม่ร่วมกัน รายละเอียดที่มาของเพื่อนและ B01–B03 อยู่ใน [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)
