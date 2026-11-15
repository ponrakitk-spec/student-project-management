# แผนและชุดทดสอบ Concurrency — Team / Project

วันที่ 2026-11-14 (Asia/Bangkok) · Branch `feature/project-continuation` · สถานะล่าสุด **RC01–RC06 PASS / Coverage ยังไม่ครบ TX ทั้งหมด**

**ผลขยาย Transaction ล่าสุด:** [RC07–RC08ผ่าน2/2](TEAM_PROJECT_TRANSACTION_FAILURES_REPORT.md) เพิ่มProjectlockโดยตรงและinjecteddeadlock40P01 พร้อมROLLBACKบนfixtureเดิม Offlineล่าสุด64ผ่าน ผลสะสม8casesจากสองrunners ไม่ใช่winner-COMMIT/HTTPหรือTXครบ

**ผลล่าสุดหลังอนุมัติ:** [ติดตั้งseed10แถวและรันRC01–RC06แล้ว PASS6/6](TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) พร้อมdirectapp/รอlockจริง/ROLLBACK/55P03 Backend291และfinaltools50ผ่าน P18เป็นInProgress ส่วนเนื้อหาขั้นเตรียม/NotRunด้านล่างเป็นประวัติก่อนอนุมัติ ไม่ใช้แทนผลล่าสุด

**ผลขั้นถัดมา:** [fixture rehearsal](TEAM_PROJECT_CONCURRENCY_FIXTURE_REHEARSAL.md) บน PostgreSQL ผ่านแล้ว สร้าง 10 แถวและทวน A/B แบบ sequential 12 รายการ จากนั้น ROLLBACK/baseline PASS; Offline ล่าสุด79ผ่าน ผลนี้ยังไม่ใช่ multi-session/lock timeout และไม่มี shared fixture ถาวร ประวัติขั้นเตรียมด้านล่างคงไว้ตามรอบที่ตรวจ

ผู้ใช้เลือก “เตรียมชุดทดสอบ Concurrency ของ Team/Project” รอบนี้เพิ่ม runner และตรวจความปลอดภัยแบบ Offline ไม่เชื่อมฐานข้อมูล ไม่สร้างข้อมูลร่วม ไม่ COMMIT และไม่เปลี่ยน API/UI/Schema/RBAC ของระบบ

## ทำไมต้องมีข้อมูลร่วมก่อน

ชุดทดสอบ API เดิมสร้างข้อมูลใน transaction เดียวแล้ว ROLLBACK ข้อมูลนั้นมองเห็นได้เฉพาะ connection ที่สร้าง การเปิด connection ที่สองไม่ได้ทำให้เห็น Team/Project ที่ยังไม่ COMMIT แม้ใช้ชื่อฐานข้อมูลเดียวกัน

runner ใหม่จึงรับ manifest ระบุ **ข้อมูลจำลองเฉพาะชุดที่มีอยู่แล้วและทั้งสอง connection มองเห็น** ไม่มีตัวเลือก seed, apply, COMMIT, auto-pick ทีมจริง หรือเปลี่ยนฐานข้อมูล ถ้ายังไม่มีข้อมูลที่ตรง manifest ต้องหยุดก่อนเขียนข้อมูล ห้ามนำ ID ของทีมที่ใช้งานอยู่มาแทน

การเตรียมข้อมูลร่วมถาวรเป็นงานอีกขั้นที่ยังไม่ได้รับอนุมัติ ข้อกำหนดปัจจุบันยังให้การทดสอบที่เขียนข้อมูลใช้ transaction และ ROLLBACK

## ไฟล์ในรอบนี้

| ไฟล์ | หน้าที่ |
|---|---|
| [team_project_concurrency.py](../../backend/tests/team_project_concurrency.py) | runner สอง worker connections กับ observer อีกหนึ่ง connection; ค่าเริ่มต้นแสดงแผนแบบ Offline |
| [test_team_project_concurrency_harness.py](../../backend/tests/test_team_project_concurrency_harness.py) | ตรวจ guard, manifest, การรอ lock, cleanup, การปิดบัง error และ baseline comparison แบบ Offline |
| [ตัวอย่าง manifest](../../backend/tests/fixtures/team_project_concurrency.example.json) | ไม่มีรหัสผ่าน และจงใจใช้ placeholder ที่ validation ไม่ยอมรับ |
| เอกสารนี้ / Backlog / Local setup / บันทึกส่งต่อ | ระบุขอบเขตที่เตรียมแล้วและข้อจำกัดก่อนรันจริง |

## กรณีที่ runner เตรียมไว้

ทุกกรณีด้านล่างให้ A ทำการเปลี่ยนแปลงค้างไว้ก่อน เปิด B ให้รอ A และใช้ observer ตรวจ `pg_blocking_pids(B)` ว่ามี PID ของ A จริง ไม่ถือว่า `sleep` หรือ thread เริ่มทำงานแล้วเป็นหลักฐานการรอ lock

| ID | A ทำก่อนและยังไม่จบ transaction | B ทำพร้อมกัน | เกณฑ์หลัง A ROLLBACK |
|---|---|---|---|
| RC01 | โอนหัวหน้าจาก A ให้สมาชิก B | หัวหน้าเดิมแก้ชื่อทีม | B ต้องรอ; หลังปลด lock หัวหน้าเดิมยังมีสิทธิ์เพราะการโอนถูกย้อนคืน |
| RC02 | หัวหน้าถอดสมาชิก | สมาชิกคนนั้นออกเอง | B ต้องรอ; หลังย้อนคืนการถอด สมาชิกออกเองได้ใน transaction ของ B |
| RC03 | แก้ description ของ Project | แก้เฉพาะ name ของ Project | B ต้องรอ; description ที่ไม่ได้ส่งต้องเป็นค่า baseline ไม่ใช่ค่าที่ A ย้อนคืนไปแล้ว |
| RC04 | สร้าง Project ให้ทีมที่ยังไม่มี Project | สร้าง Project ให้ทีมเดียวกัน | B ต้องรอ; เมื่อ A ย้อนคืน B สร้างได้โดยไม่มี Project ซ้ำค้าง |
| RC05 | เพิ่มนักศึกษาที่ไม่มีทีมเข้าทีมแรก | เพิ่มคนเดียวกันเข้าทีมที่สอง | B ต้องรอ unique-key conflict; หลัง A ย้อนคืน B เพิ่มเข้าทีมที่สองได้ |
| RC06 | แก้ชื่อทีมแรกและถือ lock ไว้ | แก้ชื่อทีมที่สองก่อน แล้วขอ lock ทีมแรก | B ต้องเจอ `55P03` ก่อน A ปลด lock และ ROLLBACK ทั้ง transaction รวมการแก้ชื่อทีมที่สอง |

ทุกกรณีให้ B ROLLBACK ด้วย และตรวจ hash ของ **ค่าข้อมูลทุกแถวใน public 14 ตาราง** เทียบ baseline ไม่ใช่ตรวจเฉพาะจำนวนแถว พร้อมเปรียบเทียบ definitions/columns/constraints/triggers/owners/ACL และ role attributes ที่ runner เก็บไว้

ข้อจำกัดการตรวจ baseline: ไม่อ่านค่า credential/session ใน auth และไม่รวมค่า identity sequences เพราะ runner ไม่เรียก Auth operations และ sequence อาจเพิ่มแม้ ROLLBACK ต้องรันบน test DB ในเครื่องที่ไม่มีผู้ใช้อื่นหรือ Browser fixture เขียนข้อมูลพร้อมกัน

RC01–RC04 ส่วนใหญ่รอที่ Team lock ตามลำดับ parent-first ของ repository จึงไม่อ้างว่าพิสูจน์การแย่ง Project lock โดยตรงครบทุกเส้นทาง RC05 เน้น unique conflict ข้ามทีม RC06 เรียก lock helper โดยตรงหลังทำ business write เพื่อรักษา SQLSTATE ดิบ; ไม่ใช่การรับรอง HTTP error/retry policy ใหม่

## สิ่งที่ยังพิสูจน์ไม่ได้ด้วย winner-ROLLBACK

หาก A เปลี่ยนหัวหน้าแล้ว **COMMIT** ผู้ใช้เดิมต้องสูญเสียสิทธิ์หลัง B รอ lock แต่ RC01 ย้อนคืน A จึงต้องได้ผลตรงข้าม คือหัวหน้าเดิมยังทำงานต่อได้ ต้องแยกสองสถานการณ์นี้ออกจากกัน

| กลุ่มถัดไป | เกณฑ์เมื่อมีขอบเขต winner-COMMIT ที่อนุมัติแล้ว |
|---|---|
| โอนหัวหน้า / ถอดสมาชิก | หลังรอ lock ต้องอ่านสิทธิ์หรือสมาชิกภาพที่เปลี่ยนไปแล้ว ไม่ใช้ค่าก่อนรอ |
| PATCH Project คนละ field | name และ description จากสองคำขอต้องคงอยู่ ไม่ทับด้วยค่าเก่า |
| สร้าง Project ซ้ำ / เพิ่มนักศึกษาคนเดียวเข้าคนละทีม | ผู้ชนะได้ข้อมูลหนึ่งชุด ผู้แพ้ได้ business conflict โดยไม่มีแถวกำพร้า |
| Deadlock / serialization / retry | แยก `40P01`, `40001`, `55P03`; ตรวจ atomicity และกำหนด retry ที่ปลอดภัยก่อนเพิ่มพฤติกรรมระบบ |

กลุ่มนี้ **ยังไม่ implement และไม่รัน** ไม่มี auto-retry POST หรือเพิ่มสิทธิ์เพื่อทำให้ผ่าน ชุด RC ไม่ใช่ตัวแทน TX-01–TX-06 ทั้งหมด โดยเฉพาะ Evaluation/Vote/Milestone/Task ยังต้องวาง integration scope แยกกับเจ้าของงาน

## ข้อมูลร่วมที่ต้องตรวจรับก่อนรัน

manifest ต้องมี version 1 และ database เป็น `student_project_management_v1_test` เท่านั้น namespace ต้องเป็น `spms-ct-` ตามด้วยเลขฐานสิบหกตัวเล็ก 32 ตัว ไม่มี credentials/session/token ใน manifest และทุก ID เป็น positive BIGINT string

| รายการ | จำนวน | เงื่อนไขที่ runner ตรวจ |
|---|---:|---|
| users | 4 | role=student; label `leader_a`, `member_b`, `leader_c`, `free_student`; email ตรง `<namespace>.<label>@example.test` |
| teams | 2 | ชื่อ `<namespace>.main` และ `<namespace>.empty` |
| team_members | 3 | main มี leader_a=leader และ member_b=member; empty มี leader_c=leader; free_student ยังไม่มีทีม |
| projects | 1 | อยู่ main, ชื่อ `<namespace>.project`, created_by=leader_a; empty ยังไม่มี Project |
| workflow children / history | 0 | ไม่มี invitation/submission/committee/milestone ของ Project นี้ และไม่มี assignment history ของสี่คนนี้ |

รวม fixture **10 แถว** ใน public โดยไม่ต้องสร้าง auth.credentials หรือ auth.sessions เพราะรอบนี้เรียก repository ผ่าน actor ที่ระบุใน fixture ไม่ทดสอบ Login/CSRF ผ่าน HTTP

หากจะสร้าง fixture เหล่านี้ให้มองเห็นข้าม connection ต้องตกลงขอบเขตบันทึกถาวรก่อน การสร้าง users ใช้ project_owner ตามแนวทางเดิม ส่วน business operations ใช้ project_app ห้ามใช้ Superuser ข้าม permission error ข้อนี้เป็นแผน ยังไม่มีการสร้าง/COMMIT หรือเตรียม installer ที่ apply ได้ในรอบนี้

รอบถัดมาเพิ่ม rehearsal tool ซึ่งสร้าง fixture **ชั่วคราวและ ROLLBACK แล้ว** ตรวจจำนวนแถวตรงตามตารางข้างต้น ไม่มี apply/export mode ดูผลและขอบเขตบันทึกถาวรที่ [รายงาน DRY RUN](TEAM_PROJECT_CONCURRENCY_FIXTURE_REHEARSAL.md)

R-01 ห้ามลบ Project จึงไม่เสนอ seed แล้ว DELETE Project เพื่อ cleanup การทดสอบแต่ละครั้งคืนข้อมูลกลับ baseline fixture เดิมด้วย ROLLBACK; fixture เริ่มต้นที่บันทึกถาวรจะยังอยู่จนกว่าจะมีวิธีจัดการที่อนุมัติชัดเจน

## คำสั่ง Windows / PowerShell

รันจาก root ได้ทันทีโดยไม่ต่อ DB:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_team_project_concurrency_harness -v
```

สองโหมดต่อไปนี้ใช้ **ภายหลังข้อมูลร่วมได้รับการตรวจรับแล้ว** เท่านั้น ตัวอย่าง manifest ใน Git ใช้รันจริงไม่ได้ เก็บ manifest ที่กรอกแล้วไว้นอก repository และไม่ใส่รหัสผ่าน:

```powershell
$concurrencyFixture = Join-Path $env:TEMP 'spms-team-concurrency.local.json'
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency --preflight --fixture $concurrencyFixture
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency --run-rollback --fixture $concurrencyFixture
```

ก่อนโหมดเขียนข้อมูล ให้ตรวจ installed baseline ตาม [Local setup](../team/LOCAL_SETUP.md) และปิดชุดทดสอบ/การกด UI ที่เขียน test DB เดียวกันก่อน ทั้ง worker และ observer เชื่อมด้วย `open_auth_connection` ซึ่ง pin test DB/project_app และไม่มี admin fallback ทุก connection ตรวจ database/effective role/session_user/Read Committed ก่อนเริ่มงาน ใช้ actor context ภายใน transaction และบังคับ deferred constraints ก่อนจบ operations

runner กำหนด statement/lock timeouts จำกัดเวลารอ ใช้ connection แยกจริง 3 PID และปิด connection ที่ตัวเองเปิด ไม่ปิดหรือ terminate session ของผู้ใช้ เมื่อผิดพลาดแสดงเฉพาะ fixed reason code/SQLSTATE ไม่แสดง exception text, SQL parameters, DSN, อีเมล หรือข้อมูลลับ

## ผลตรวจรอบเตรียม

| การตรวจ | ผล | ความหมาย |
|---|---|---|
| Offline runner safeguards | **PASS 25 tests** | ใช้ mocks; guard/manifest/cleanup/wait-evidence/control flow ผ่าน ไม่ใช่ PostgreSQL runtime |
| Offline safeguards + Auth validation/security + DB connection boundary | **PASS 67 tests / 0.414s** | 25 ใหม่ + 42 เดิม ไม่มีการอ่าน .env หรือต่อ PostgreSQL ใน tests เหล่านี้ |
| ค่าเริ่มต้นของ runner | **PASS OFFLINE_PLAN** | แสดง 6 cases พร้อม `database_connected=false`; ไม่มี runtime PASS ปลอม |
| เรียก preflight ด้วย placeholder example | **PASS ตามเกณฑ์ปฏิเสธ / exit 1** | ได้ `MANIFEST_NAMESPACE` ก่อนเปิด connection ไม่ใช่ PostgreSQL runtime failure |
| Python AST / whitespace / ลิงก์เอกสาร | **PASS** | Python ใหม่ทั้งสองไฟล์ parse ผ่าน, ไม่พบ trailing whitespace, ลิงก์ relative 62 จุดในเอกสารที่เปลี่ยน resolve ได้ |
| RC01–RC06 บน PostgreSQL | **Not Run / Not Verified** | ยังไม่มี shared fixture ที่ตรวจรับ |
| winner-COMMIT / HTTP concurrency / TX-01–TX-06 ครบ | **Not Run / Not Verified** | ยังไม่อยู่ใน runner หรือขอบเขตรันรอบนี้ |
| Backend242 / Browser73 | ผลจากรอบ [Exit](TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md) | ไม่รันซ้ำรอบนี้ เพราะ production source ไม่เปลี่ยน ไม่ใช้ผลเก่ารับรอง Concurrency |

P18 ยัง **Blocked สำหรับรันครบ requirement** แต่ขั้นเตรียม runner เสร็จแล้ว คง Done5/20=25% ไม่ปิด A-05 หรือ P09 จาก Offline tests

## จุดต่อกับงานเพื่อน

- ไม่แก้ Submission/Milestone/Supabase หรือ merge branch เพื่อน ใช้ Team/Project repository ของ branch ปัจจุบันและ controlled SQL เดิมเท่านั้น
- RC02 ไม่มี Task จึงไม่อ้างว่าพิสูจน์ C-02/history ขณะอีกคนแก้ Task พร้อมกัน (TX-04); ผล Task แบบ single-session อยู่ในรายงาน Exit เดิม
- เมื่อรับ Milestone/Task ของเพื่อน ต้องออกแบบ TX-04 และ Project lock ร่วมกับการถอน assignee ใหม่ รวมถึง `get_*_uow` overrides ให้ทุกคำขอใช้ connection ที่ตั้งใจทดสอบ
- ดูปัญหา B01–B03 และประวัติส่งต่อใน [บันทึกเชื่อมงานเพื่อน](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ไม่เปลี่ยน runtime ไป Supabase และไม่มี Commit/Push ในรอบนี้
