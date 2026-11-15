# ผลทดสอบ Project lock และ Deadlock rollback

วันที่ 2026-11-14 (Asia/Bangkok) · Branch `feature/project-continuation` จาก `679913a` + working tree · **RC07–RC08 PASS 2/2**

ผู้ใช้ให้ดำเนินการต่อจาก [RC01–RC06](TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) รอบนี้ขยายเฉพาะ Transaction tests ที่ใช้ fixture เดิมและ ROLLBACK ได้ ไม่มีการอนุมัติหรือทำ winner-COMMIT ของ business actions, seed ใหม่, Schema/ACL changes หรือการแก้งาน Submission/Milestone/Supabase ของเพื่อน

## ไฟล์ที่เพิ่ม/ปรับ

| ไฟล์ | หน้าที่ |
|---|---|
| [team_project_transaction_failures.py](../../backend/tests/team_project_transaction_failures.py) | runner แยก RC07/RC08 ใช้ manifest/connection guards/rollback/cleanup/fingerprint ของ runner เดิม ค่าเริ่มต้น Offline |
| [test_team_project_transaction_failures.py](../../backend/tests/test_team_project_transaction_failures.py) | 14 Offline safeguards รวมเลือก deadlock victim ได้ทั้ง A/B, rollback ก่อนรออีกฝั่ง, state validation, ไม่ใช้ timeout แทน deadlock และไม่เปลี่ยนค่าระบบเอง |
| รายงานนี้ / Backlog / แผน / รายงาน RC01–RC06 / Local setup / handoff | บันทึกหลักฐานเพิ่มและข้อจำกัดที่ยังเหลือ |

Production Backend/Frontend, SQL V1/RBAC/Auth, .env, requirements, dependencies, installer และ fixture manifest ไม่เปลี่ยน ไม่มี Git Commit/Push และไม่เชื่อมฐานข้อมูลหลัก

## การรันและผลจริง

ทั้งสอง case ใช้เฉพาะ `student_project_management_v1_test` ผ่าน direct LOGIN `project_app` เปิด 3 connections แยก PID (A/B/observer) ตรวจ database/role/session user/Read Committed ก่อนเริ่ม และตรวจ exact fixture roster ก่อนทำงาน ไม่ใช้ owner/admin fallback

observer ตรวจว่าไม่มี client connection อื่นก่อนเริ่ม case เพื่อไม่รบกวนข้อมูลผู้ใช้ แต่ไม่ปิดหรือ terminate session ของผู้อื่น คำสั่งเขียนใช้ Team/Project repository และ controlled SQL เดิม การถือ lock โดยตรงใช้ helper ที่ app มีสิทธิ์อยู่แล้ว ไม่มี raw UPDATE/DELETE หรือ GRANT เพิ่ม

| Case | ลำดับทดสอบ | ผลที่สังเกต | ผล |
|---|---|---|---|
| RC07 | A ตั้ง actor แล้วถือเฉพาะ Project lock; B เรียก Project update ซึ่งถือ Team ก่อนขอ Project lock | `pg_blocking_pids(B)` พบ A จริง ทั้งที่ A ไม่ถือ Team lock; หลัง A ROLLBACK B แก้ name ได้และ description ที่ไม่ได้ส่งคงเดิม จากนั้น B ROLLBACK | PASS |
| RC08 | A แก้ชื่อ main Team/ถือ lock; B แก้ชื่อ empty Team/ถือ lock แล้วขอ main Team; observer เห็น B รอ A จากนั้น A ขอ empty Team | PostgreSQL เลือกหนึ่งฝั่งเป็น victim ด้วย `40P01` อีกฝั่งสำเร็จหลัง victim ROLLBACK และอ่านชื่อทีมของ victim ได้เป็นค่า baseline แล้ว ROLLBACK ด้วย | PASS |

ทุก case รายงาน `wait_observed=true`, `distinct_connections=3`, `both_workers_rolled_back=true`, `public_rows_metadata_restored=true`, `automatic_retry=false` ก่อน PASS ต้องตรวจ hash ของค่าข้อมูล public14ตารางและ metadata/ACL ตาม fingerprint เดิม รวมถึง fixture roster กลับ baseline

`40P01` เป็นผลที่คาดหวังของ **deadlock ที่จงใจสร้างเฉพาะสคริปต์ทดสอบ** ไม่ใช่หลักฐานว่า API ของระบบเกิด deadlock จริง RC08 จงใจเรียก Team locks สวนลำดับเพื่อฉีด failure ไม่เปลี่ยน parent-first lock order ในโค้ดระบบ

runner ไม่กำหนดตายตัวว่า A หรือ B ต้องเป็น victim ต้องมีผลหนึ่ง `40P01` และอีกหนึ่ง success เท่านั้น หากเป็น `55P03`, ทั้งคู่สำเร็จ หรือทั้งคู่ล้มเหลวจะไม่ผ่าน ตรวจ `deadlock_timeout` แบบ read-only ให้สั้นกว่า test deadline; ถ้าไม่เหมาะสมให้หยุด ไม่ SET ค่านี้ด้วย Superuser/เพิ่มสิทธิ์เอง

## หลักฐานการตรวจรับ

| การตรวจ | ผล | ขอบเขต |
|---|---|---|
| ค่าเริ่มต้น runner | PASS `OFFLINE_PLAN` | ไม่อ่าน .env/ต่อ DB และไม่รายงาน runtime PASS |
| Offline safeguards ใหม่ | PASS14 tests | ใช้ mocks; ไม่ใช่ผล PostgreSQL deadlock |
| ใหม่14 + safeguards เดิม50 | PASS64 / 0.080s | Runnerเดิม25 + rehearsal12 + installer13; ไม่มี DB connection ใน unittest ชุดนี้ |
| PostgreSQL RC07–RC08 | PASS2 / 1.588s | ใช้ manifest/seed เดิม ไม่มี COMMIT หรือ seed เพิ่ม |
| RC08 SQLSTATE | `40P01` ตามคาด | victimหนึ่งฝั่ง ย้อนคืนทั้ง transaction; survivorตรวจชื่อฝั่งvictimกลับbaseline |
| RC01–RC06 | PASS6 จาก [รอบก่อนหน้า](TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) | ไม่รันซ้ำรอบนี้ ผลสะสมของสอง runners ครอบคลุม8cases ไม่ใช่รันใหม่8cases |
| Backend291 / Browser73 / build | ผลรอบก่อนหน้า | ไม่รันซ้ำเพราะ production source/config ไม่เปลี่ยน และ runner/tests ใหม่ตรวจเฉพาะ scope ที่เพิ่ม |

baseline ยังคง fixture 10 แถวที่ผู้ใช้อนุมัติไว้ก่อนหน้านี้ การ ROLLBACK รอบนี้คืน baseline นั้น ไม่ลบ seed และไม่รวมค่า identity sequences ในการรับรอง snapshot ไม่ hash ค่า auth.credentials/sessions เพราะไม่มี Auth operations ใน runner

## คำสั่ง Windows / PowerShell

จาก root บนเครื่องที่มี approved fixture/manifest เดิมแล้ว และไม่มีชุดทดสอบหรือ UI อื่นเขียน test DB พร้อมกัน:

```powershell
$concurrencyManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_transaction_failures
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_team_project_transaction_failures backend.tests.test_team_project_concurrency_harness database.tests.test_concurrency_fixture database.tests.test_concurrency_fixture_install -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_transaction_failures --run-rollback --fixture $concurrencyManifest
```

Manifest/DBไม่ตรงต้องหยุด ไม่สร้างข้อมูลร่วมใหม่หรือใช้ ID ของทีมอื่นเพื่อให้ผ่าน และไม่ใช้ installer apply เป็นส่วนหนึ่งของ test

## ขอบเขตที่ยังไม่ครบ

- TX-06 มีหลักฐาน lock timeout (`55P03`, RC06) และ injected deadlock (`40P01`, RC08) กับ rollback แล้ว แต่ `40001` serialization และ retry policy ยังไม่พิสูจน์ ไม่ปิด TX-06 ทั้งแถว
- ไม่เพิ่ม auto-retry หรือเปลี่ยน HTTP error contract การทดสอบนี้เรียก repository/helper ไม่ใช่หลาย HTTP requests/Browser sessions
- RC07 พิสูจน์ว่า Project update รอ Project lock โดยตรงได้ ไม่ได้พิสูจน์ lock graph ทุก API/Trigger หรือปิด A-05 ทั้งหมด
- winner-COMMIT, fresh authorization หลังอีกฝั่ง COMMIT และ lost update เมื่อทั้งคู่ COMMIT ยังไม่ทดสอบ การอนุมัติ seed ครั้งก่อนยังไม่ครอบคลุม test แบบนี้
- TX-01–TX-05/Evaluation/Vote/Milestone/Task ยังไม่รัน RC08 ใช้ Team metadata จึงไม่ปิด TX-04/C-02/history กับงาน Task ที่เพื่อนพัฒนา
- ไม่แก้ source/รวม branch เพื่อน คง B01–B03 และ [บันทึกจุดเชื่อม](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ไว้

P18 ยัง In Progress, Done5/InProgress14/NotStarted1/Blocked0 จาก20งาน จึงคง25%ตามสูตรเดิม ไม่มีการปิดงานหลักจากการเพิ่มสองcase
