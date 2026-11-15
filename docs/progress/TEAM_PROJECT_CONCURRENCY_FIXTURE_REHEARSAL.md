# ผล DRY RUN ของ fixture สำหรับ Concurrency

วันที่ 2026-11-14 (Asia/Bangkok) · Branch `feature/project-continuation` จาก `679913a` + working tree · **DRY RUN PASS (บันทึกรอบก่อนอนุมัติ seed ถาวร)**

**อัปเดตรอบถัดมา:** ผู้ใช้ตอบ “อนุญาต” หลังรับคำอธิบายแล้ว ติดตั้งseed10แถวและ [Concurrency6/6ผ่าน](TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) รายงานนี้เป็นหลักฐานรอบDRY RUNก่อนอนุมัติ ไม่ใช่สถานะติดตั้งล่าสุด เครื่องมือrehearsalยังROLLBACKเสมอ ส่วนinstallerเป็นอีกไฟล์หนึ่ง

ต่อจาก [แผน RC01–RC06](TEAM_PROJECT_CONCURRENCY_PLAN.md) ผู้ใช้ให้ดำเนินขั้นตอนถัดไป รอบนี้เตรียมและทดลองสร้างข้อมูลตามแผนด้วย transaction และ ROLLBACK เท่านั้น ไม่มีการขยายข้อยกเว้นให้ COMMIT fixture เอง

## ไฟล์ที่เปลี่ยน

| ไฟล์ | เหตุผล |
|---|---|
| [Team_Project_Concurrency_Fixture.py](../../database/tools/Team_Project_Concurrency_Fixture.py) | ค่าเริ่มต้นเป็น Offline plan; `--dry-run` สร้าง fixture ชั่วคราว ทวนคำสั่ง และตรวจคืน baseline ไม่มี apply/export mode |
| [test_concurrency_fixture.py](../../database/tests/test_concurrency_fixture.py) | 12 tests แบบ Offline สำหรับ scope/roles/row delta/rollback/error redaction และ postflight failure |
| รายงานนี้ / แผน / Backlog / Local setup / บันทึกส่งต่อ | บันทึกผลจริง แยก sequential rehearsal จาก concurrency และระบุขอบเขตที่ยังต้องอนุมัติ |

API/UI/SQL Schema V1/RBAC/Auth/.env/dependencies และ source Submission/Milestone/Supabase ของเพื่อนไม่เปลี่ยนในรอบนี้ ไม่มี Git Commit/Push

## วิธีทดลอง

1. ตรวจ test DB ด้วย connection ที่ pin `student_project_management_v1_test` แบบ read-only พบ client connection อื่น **0** ก่อนเริ่ม ไม่ปิดหรือ terminate session ของผู้ใช้
2. ตรวจ installed V1 baseline ว่ามี 52 functions ตรง source และตรวจ database/effective role/trigger mode เมื่อสลับ role ทุกครั้ง ไม่เพิ่มหรือเปลี่ยน functions/grants
3. ใช้ effective `project_owner` ที่ไม่ใช่ Superuser สร้าง users 4 แถว จากนั้นใช้ effective `project_app` สร้าง Team/leader/member/Project ด้วย repository และ controlled SQL เดิม ไม่มี owner fallback สำหรับ business operation
4. บังคับ deferred constraints และตรวจ delta ตรง **users +4, teams +2, team_members +3, projects +1** ตารางอื่นรวม auth.credentials/auth.sessions ต้องไม่เพิ่ม
5. ทวน action A และ B ของ RC01–RC06 แบบทีละรายการใน savepoint ที่ `force_rollback=True` รวม 12 action ตรวจ hash ของค่าข้อมูลคืน fixture baseline หลังแต่ละรายการ
6. ROLLBACK fixture ทั้งชุดและ outer transaction จากนั้นเปิด read-only postflight ตรวจ definitions/owners/ACL/columns/constraints/triggers/roles/จำนวนแถวทุก public/auth table และ hash ค่าข้อมูล public 14 ตารางเทียบก่อนเริ่ม ก่อน ROLLBACK และปิด connection ของเครื่องมือ

session login ของ rehearsal ใช้ deployment connection เดิมเพื่อ `SET LOCAL ROLE` ตามแนวทาง fixture ที่มีอยู่ การรัน business action ใช้ effective `project_app` ทุกครั้ง **ไม่ใช่ผล direct LOGIN project_app หรือหลาย connections** ซึ่งต้องตรวจแยกด้วย runner จริง

## ผลที่ได้

| รายการ | ผล | ขอบเขต |
|---|---|---|
| ค่าเริ่มต้น | PASS `OFFLINE_PLAN` | ไม่อ่าน .env/ต่อ DB ไม่มี apply mode หรือ manifest export |
| Offline safeguards เฉพาะ fixture tool | PASS **12 tests** | mocked control flow ไม่ใช่ PostgreSQL locking |
| Fixture safeguards + runner safeguards | PASS **37 tests / 0.050s** | 12 ใหม่ + 25 ของ runner |
| รวม Offline Auth validation/security/DB boundary | PASS **79 tests / 0.403s** | 12+25+42 ไม่มี real DB connection ใน unittest ชุดนี้ |
| สร้าง fixture บน PostgreSQL | PASS | 10 แถวตาม delta ข้างต้น ไม่สร้าง credentials/session |
| Sequential action rehearsal | PASS **12 รายการ** | RC01–RC06 × A/B; ไม่มีคำสั่งสองฝั่งทำงานพร้อมกัน |
| Postflight หลัง ROLLBACK | PASS `baseline_restored=true` | metadata/ACL/row counts และ public row values กลับ baseline; ไม่รวม sequence values |
| ตรวจ connection หลังจบอีกครั้ง | PASS **0 client connections อื่น** | ตรวจแบบ read-only บน test DB แล้วปิด connection ผู้ตรวจเอง |
| ตรวจไฟล์รอบนี้ | PASS | Python AST/whitespace/relative links73จุด; ไม่พบค่าลับจาก .env ใน7ไฟล์ขอบเขต; SQL/RBAC/Auth sourceที่ตรวจยังตรง HEAD และเครื่องมือไม่มี `.commit()` call |
| การบันทึกถาวร / export manifest | **ไม่ได้ทำ** | `committed=false`, `manifest_exported=false` |
| RC01–RC06 multi-session | **Not Run / Not Verified** | `multisession_tested=false`; ยังไม่มี shared fixture ที่อนุมัติ |
| Lock timeout `55P03` / deadlock / serialization | **Not Verified** | RC06 B ใน rehearsal ขอ lock ที่ไม่มีใครถือ จึงต้องสำเร็จ ไม่ใช่ผล timeout |

ไม่พบ permission error ในการทดลองนี้ ไม่มี SQLSTATE failure ให้รายงาน และไม่ได้เพิ่มสิทธิ์เพื่อทำให้ผ่าน หากเกิด failure เครื่องมือรายงาน stage/SQLSTATE ที่หาได้จาก exception context โดยไม่แสดง exception text/SQL parameters/DSN หรือ secrets

Postflight ไม่ hash ค่า credentials/session เพราะรอบนี้ไม่เขียนสองตารางนั้น แต่ตรวจจำนวนแถวด้วย owner snapshot เช่นเดียวกับชุดทดสอบเดิม Identity sequence อาจเพิ่มแม้ ROLLBACK จึงไม่อ้างว่าคืนเลข ID

คำสั่งที่ใช้จาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_concurrency_fixture backend.tests.test_team_project_concurrency_harness backend.tests.test_auth_validation backend.tests.test_auth_security database.tests.test_test_database -q
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture --dry-run
```

## ขอบเขตขั้นถัดไปที่ต้องตรวจรับ

เพื่อเปิด worker A/B คนละ connection ต้องมี fixture เดียวกันที่มองเห็นข้าม transaction ได้ ข้อมูล DRY RUN ถูกย้อนคืนแล้ว และ ID จาก rehearsal ใช้แทนข้อมูลร่วมไม่ได้ เครื่องมือจึงไม่ export manifest ที่ชี้ข้อมูลซึ่งไม่มีอยู่จริง

ข้อเสนอสำหรับการอนุมัติบันทึกข้อมูลร่วมหนึ่งครั้ง:

- **ฐานข้อมูลเดียว:** `student_project_management_v1_test`
- **ข้อมูล:** student จำลอง 4 คน, Team 2 ทีม, membership 3 รายการ และ Project 1 รายการ รวม 10 แถวตาม namespace สุ่มเฉพาะชุด ชื่อ/อีเมล/roster ตรงตาม [fixture specification](TEAM_PROJECT_CONCURRENCY_PLAN.md#ข้อมูลร่วมที่ต้องตรวจรับก่อนรัน)
- **สิทธิ์ที่ใช้:** project_owner เฉพาะสร้าง users; project_app ทำ business operations เดิม ไม่มี Superuser ข้าม permission error
- **ไม่รวม:** Schema/RBAC/role/password/.env/Auth credentials/sessions หรือข้อมูลเดิม; ไม่สร้างบัญชีที่ใช้ Login ได้ ไม่ใช้ฐานข้อมูลหลัก
- **หลังบันทึก:** ตรวจ manifest ด้วย direct project_app แล้วรัน RC01–RC06 โดยทุก worker transaction ROLLBACK และตรวจ baseline ที่รวม fixture เริ่มต้นนี้
- **ผลคงอยู่:** fixture 10 แถวจะยังอยู่ใน test DB; R-01 ห้ามลบ Project จึงไม่เสนอ seed แล้ว DELETE Project เพื่อ cleanup และไม่ล้าง/สร้าง DB ใหม่เอง
- **ยังไม่รวม:** winner-COMMIT ของ business actions, HTTP concurrency, TX-01–TX-06 ทั้งหมด หรือการ retry อัตโนมัติ

หากไม่อนุมัติให้บันทึก จะคงผล DRY RUN และ Offline ไว้ได้ แต่ยังรัน multi-session บน fixture นี้ไม่ได้ การอนุมัติบันทึกครั้งเดียวนี้เป็นข้อยกเว้นเฉพาะ seed เริ่มต้น ไม่เปลี่ยนกฎ ROLLBACK ของ test cases

ขณะจบรายงาน **ยังไม่อนุมัติ/ยังไม่บันทึก fixture ถาวร** และเครื่องมือปัจจุบันไม่มี apply mode ขั้นบันทึกจริงต้องมี installer/manifest handling ที่ทดสอบก่อน execute แยกต่างหาก ห้ามแก้เครื่องมือ rehearsal ให้ COMMIT เงียบ ๆ

P18 ยัง Blocked เฉพาะขั้น multi-session และ coverage ที่เหลือ ไม่เปลี่ยน Done5/20=25% บันทึกจุดเชื่อมของเพื่อนไว้ใน [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md) โดยไม่แก้งานของเพื่อน
