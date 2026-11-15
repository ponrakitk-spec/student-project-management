# ผลติดตั้ง fixture และทดสอบ Concurrency Team / Project

วันที่ 2026-11-14 (Asia/Bangkok) · Branch `feature/project-continuation` จาก `679913a` + working tree · **RC01–RC06 PASS 6/6**

**ผลรอบถัดมา:** [RC07–RC08 Projectlock/injecteddeadlockผ่าน2/2](TEAM_PROJECT_TRANSACTION_FAILURES_REPORT.md) แล้วบนfixtureเดิม ไม่มีseed/COMMITเพิ่ม รายการคงค้าง40P01ด้านล่างเป็นสถานะ ณ รอบRC01–RC06; รอบใหม่พิสูจน์เฉพาะfailure-injection/rollback ไม่ใช่deadlockในAPIจริง และยังไม่40001/retry/winner-COMMIT

ผู้ใช้ตอบ “อนุญาต” หลังอธิบายขอบเขต [fixture 10 แถวและผล DRY RUN](TEAM_PROJECT_CONCURRENCY_FIXTURE_REHEARSAL.md) จึงบันทึกเฉพาะ seed ตั้งต้นหนึ่งครั้งใน `student_project_management_v1_test` แล้วรัน worker transactions แบบ ROLLBACK ทุกกรณี ไม่มีการอนุมัติ winner-COMMIT ของ business actions หรือการ Commit/Push Git

## สิ่งที่เปลี่ยน

| ไฟล์ / artifact | เหตุผล |
|---|---|
| [Team_Project_Concurrency_Fixture_Install.py](../../database/tools/Team_Project_Concurrency_Fixture_Install.py) | installer แยกต่างหาก ค่าเริ่มต้น Offline; apply ต้องยืนยัน test DB และ manifest นอก repository; ป้องกัน seed ซ้ำ/ไม่ overwrite/ไม่ retry เมื่อ COMMIT ไม่แน่นอน |
| [test_concurrency_fixture_install.py](../../database/tests/test_concurrency_fixture_install.py) | Offline safeguards 13 กรณี รวมยืนยัน DB, manifest, COMMIT failure, postflight failure, ไม่เปลี่ยนข้อมูลเดิมและกันสร้างชุดที่สอง |
| `%LOCALAPPDATA%\StudentProjectManagement\concurrency\team-project-v1.json` | manifest ประจำเครื่อง มี namespace/IDs ของ seed เท่านั้น ไม่มี password/credential/session และอยู่นอก Git |
| รายงานนี้ / แผน / รายงาน DRY RUN / Backlog / Local setup / handoff | อัปเดตผลจริงและขอบเขต coverage ที่ยังเหลือ |

ไม่เปลี่ยน production API/store/UI, SQL V1/RBAC/Auth, requirements, .env, dependencies หรือ source Submission/Milestone/Supabase ของเพื่อน เครื่องมือ rehearsal เดิมยังไม่มี apply mode และบังคับ ROLLBACK เหมือนเดิม

## ผลการบันทึก seed ที่ได้รับอนุมัติ

- ก่อนบันทึก direct LOGIN `project_app` ผ่าน read-only preflight: `current_database=student_project_management_v1_test`, `session_user=current_user=project_app` และไม่มี client connection อื่น
- ตรวจ installed baseline 52 functions ตรง source ก่อนเขียน ใช้ effective project_owner เฉพาะ INSERT users และ effective project_app สำหรับ Team/member/Project ผ่าน repository/controlled SQL เดิม ไม่มี Superuser ข้าม permission error
- บันทึก **users4 + teams2 + team_members3 + projects1 = 10 แถว** ไม่มี credentials/sessions หรือข้อมูลธุรกิจอื่นเพิ่ม
- ตรวจ metadata/ACL/row counts หลังติดตั้งด้วย connection ใหม่ และ hash ข้อมูล public เดิมโดยตัดเฉพาะ 10 แถวของ fixture ออก ยืนยัน **ข้อมูล public เดิมไม่เปลี่ยน**
- fsync manifest ก่อนส่ง COMMIT หาก COMMIT ตอบกลับไม่แน่นอนจะคง artifact และรายงาน `COMMIT_PENDING` ไม่สร้างชุดใหม่อัตโนมัติ หาก artifact ไม่สมบูรณ์ต้องตรวจสถานะ ไม่ลบ/overwrite แล้ว apply ใหม่เอง
- เรียก apply ซ้ำด้วย manifest เดิมได้ `ALREADY_INSTALLED`, `written=false`, `additional_rows=0` และ hash baseline ก่อน/หลังเท่ากัน
- guard เพิ่มเติมหยุดหากพบ fixture namespace ใน DB แต่ระบุ manifest อีกไฟล์ เพื่อไม่สร้างชุดที่สอง หาก manifest หายให้กู้จากข้อมูลเดิมโดยตรวจรับก่อน ห้ามเปลี่ยน path เพื่อ seed ซ้ำ

seed 10 แถวนี้ยังอยู่เป็นข้อมูลตั้งต้นตามที่อนุมัติ Project อยู่ภายใต้ R-01 ห้ามลบ ไม่ได้ลบ Project เพื่อ cleanup และไม่มีบัญชี Login ใหม่จาก seed นี้ Manifest เป็นของ DB ในเครื่องนี้ ไม่ใช่ไฟล์ใช้ร่วมกับ DB ของสมาชิกทีมทุกคน

## ผล PostgreSQL multi-session

ใช้ [runner เดิม](../../backend/tests/team_project_concurrency.py) โดยไม่แก้เพื่อให้ผ่าน ทุก case เปิด 3 connections แยก PID: worker A, worker B และ observer ทั้งหมด direct LOGIN/effective project_app บน test DB, Read Committed, มี timeouts และตรวจ DB/role ก่อนเริ่ม

| Case | ผลที่สังเกตจริง | ผล |
|---|---|---|
| RC01 | A โอนหัวหน้าค้างไว้ B หัวหน้าเดิมรอ lock; หลัง A ROLLBACK B แก้ทีมได้ด้วยสิทธิ์ baseline | PASS |
| RC02 | A ถอดสมาชิกค้างไว้ B สมาชิกคนนั้นรอ lock; หลัง A ROLLBACK B ออกเองได้ | PASS |
| RC03 | A แก้ description ค้างไว้ B รอแก้ name; หลัง A ROLLBACK field ที่ B ไม่ส่งคงค่า baseline | PASS |
| RC04 | A สร้าง Project ค้างไว้ B สร้างให้ทีมเดียวกันแล้วรอ; หลัง A ROLLBACK B สร้างได้ ไม่มี Project ซ้ำค้าง | PASS |
| RC05 | A เพิ่มนักศึกษาว่างเข้าทีมแรก B เพิ่มคนเดียวกันเข้าทีมที่สองแล้วรอ unique conflict; หลัง A ROLLBACK B เพิ่มได้ | PASS |
| RC06 | B แก้ชื่อทีมที่สองก่อน แล้วรอ lock ทีมแรกซึ่ง A ถืออยู่; B ได้ `55P03` ขณะ A ยังถือ lock และย้อนคืน transaction ทั้งหมด | PASS |

ทุก case มี `wait_observed=true` จาก `pg_blocking_pids(B)` ที่พบ A จริง, `both_workers_rolled_back=true`, `public_rows_metadata_restored=true` ไม่อาศัยเพียง sleep/thread-start และไม่ COMMIT business action ของ A/B

RC06 `55P03` เป็นผลที่คาดหวังของ lock timeout จึงเป็น PASS ไม่ใช่ permission error ไม่พบ permission denied ในการรันจริงและไม่ได้เพิ่มสิทธิ์ใด ๆ baseline หลังแต่ละ case รวม seed 10 แถวที่ติดตั้งไว้แล้ว ไม่รวมค่า identity sequences ที่อาจเพิ่มแม้ ROLLBACK

## การตรวจรับอื่น

| ชุด | ผล | ขอบเขต |
|---|---|---|
| Installer + rehearsal + runner Offline safeguards ก่อน apply | PASS49 / 0.073s | ใช้ mocks ไม่มี DB ใน unittest ชุดนี้ |
| Fixture installation / fresh postflight / direct app | PASS | COMMIT เฉพาะ seed10 แถวตามอนุมัติ; ข้อมูลเดิมและ Schema/ACL คงเดิม |
| PostgreSQL RC01–RC06 | PASS6 / 2.538s | เวลารวม preflight; winner-ROLLBACK ไม่ใช่ HTTP/browser concurrency |
| Repeat apply + independent hash comparison | PASS | อ่านตรวจชุดเดิม ไม่เพิ่มแถว; ตรวจ client connection อื่นหลังจบได้0 |
| Backend regression + Offline tools | PASS291 / 42.810s | 242เดิม + tool safeguards49; ชุด DB ทั้งหมดคืน baseline ที่มี seed แล้ว |
| Final tool safeguards หลังเพิ่ม guard กัน manifest คนละไฟล์ | PASS50 / 0.075s | Installer13 + rehearsal12 + runner25; ไม่เปลี่ยน API/DB business code หลัง regression291 |

ไม่ได้รัน Browser/build ใหม่ เพราะ production Frontend/Backend ไม่เปลี่ยนในรอบนี้ ผล Browser73 เป็นผลรอบ Exit ไม่ใช่หลักฐาน Concurrency ผ่าน Browser

## วิธีรันซ้ำบนเครื่องนี้

จาก root และอย่าให้การกด UI/ชุดทดสอบอื่นเขียน test DB พร้อมกัน:

```powershell
$concurrencyManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture_Install --check --manifest $concurrencyManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency --run-rollback --fixture $concurrencyManifest
```

คำสั่งที่ใช้ติดตั้งครั้งที่ได้รับอนุมัติ (ไม่ใช่คำสั่ง seed อัตโนมัติใน regression):

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture_Install --apply --confirm-database student_project_management_v1_test --manifest $concurrencyManifest
```

ค่าเริ่มต้นที่ไม่ส่ง apply/check เป็น Offline plan ไม่อ่าน .env/ต่อ DB ไฟล์ manifest ไม่ได้อยู่ใน Git ดังนั้น clone ไม่ได้คัดลอกข้อมูลหรือ IDs ของ DB นี้ไปให้เพื่อน แต่ละเครื่องต้องตั้ง baseline และเตรียม fixture ที่ตรง DB ของตนตามขอบเขตที่ตรวจรับเอง

## สิ่งที่ยังเหลือ

- A **COMMIT** การโอนหัวหน้า/ถอดสมาชิก แล้ว B ต้องเห็นสิทธิ์ใหม่หลังรอ lock: ยังไม่ทดสอบ การอนุมัติ seed ครั้งนี้ไม่ใช่อนุมัติ COMMIT ทุก test
- Lost update เมื่อ A/B ต่าง COMMIT field คนละตัว, ผู้แพ้ duplicate conflict หลังผู้ชนะ COMMIT: ยังไม่ทดสอบ RC03–RC05 เป็น winner-ROLLBACK
- Project lock โดยตรงทุกเส้นทาง, HTTP/Browser หลาย session, `40P01` deadlock, `40001` serialization และ retry policy: ยังไม่พิสูจน์
- TX-01/02/03/04/05 ที่เกี่ยวกับ Evaluation/Vote/Milestone/Task ยังไม่รัน โดยเฉพาะ RC02 ไม่มี Task จึงไม่ปิด TX-04/C-02/history ขณะอีกคนแก้ Task
- TX-06 มีหลักฐานเฉพาะ lock timeout และ transaction rollback ใน runner นี้ ไม่ใช่ coverage ครบทั้งแถว
- ไม่รวม/แก้ Submission/Milestone/Supabase ของเพื่อน; คง B01–B03 และบันทึกจุดเชื่อมใน [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

P18 เปลี่ยน **Blocked → In Progress** เพราะ fixture พร้อมและมีผล multi-session จริงบางส่วนแล้ว แต่ยังไม่ Done คง Done5/20=25%; สถานะรวมเป็น Done5 / In Progress14 / Not Started1 / Blocked0 ไม่มี Git Commit/Push หรือการเข้าถึงฐานข้อมูลหลัก
