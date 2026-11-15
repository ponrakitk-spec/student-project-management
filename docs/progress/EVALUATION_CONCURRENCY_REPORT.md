# Evaluation concurrency — Installed fixture and PostgreSQL results

วันที่ 2026-11-15 (Asia/Bangkok) · local `feature/project-continuation` บน `679913a` + working tree · ไม่ Commit/Push

**รอบต่อมา:** [Evaluation HTTP EH01–EH10ผ่าน10/10](EVALUATION_HTTP_CONCURRENCY_REPORT.md) ใช้seed42เดิม ไม่มีข้อมูลถาวรเพิ่ม รายงานนี้เป็นผล direct-app EC8รอบติดตั้ง

**ผล: ติดตั้ง fixture42แถวตามอนุมัติ และ EC01–EC08 ผ่าน8/8** ใช้ direct LOGIN `project_app` ทั้ง A/B/observer คนละ PID ตรวจรอ lock จริง แล้ว ROLLBACK A/B ทุกกรณีคืน baseline ที่มี seed42แถวนี้

## คำอนุมัติและขอบเขต

ผู้ใช้ตอบ **“อนุมัติบันทึก 42 แถวและรัน 8 กรณี”** หลังตรวจ [preparation/จำนวนแถว/ผลกระทบ](EVALUATION_CONCURRENCY_PREPARATION.md) นี่คือข้อยกเว้นเฉพาะบันทึก fixture ใน `student_project_management_v1_test` ไม่ใช่สิทธิ์ COMMIT business actions, เพิ่ม grants, เปลี่ยน Schema หรือใช้ฐานข้อมูลอื่น

Installer COMMIT เฉพาะ users7 (students2/advisors4/coordinator1), teams/members/projects/invitations/submissions/files อย่างละ2, assignments6, topic votes6, milestones/tasks/assignees อย่างละ3 และ Evaluationตั้งต้น2 รวม42แถว ไม่มี credentials/sessions/บัญชี Login ใหม่

Manifest อยู่ `%LOCALAPPDATA%\StudentProjectManagement\concurrency\evaluation-v1.json` นอก Git มีเฉพาะ fixture identifiers/namespace ไม่มีรหัสผ่าน Seed42แถวคงอยู่ตามอนุมัติ รวม Project2รายการที่ R-01ห้ามลบ และอาจปรากฏให้ Coordinator เห็นเป็น approved Project ไม่ใช่ข้อมูลค้างโดยไม่ได้รับอนุญาต

ก่อน COMMIT ตรวจ exact row delta/definitions/owners/ACL และ hash ของ public rowsเดิมที่ไม่ใช่ fixture ไม่เปลี่ยน เขียน manifestแบบexclusive/flush/fsyncก่อน COMMIT หลัง COMMITเปิด connectionใหม่ตรวจ snapshot/fingerprint และ direct app graph ผ่าน ไม่แก้ข้อมูลเดิม/Schema/RBAC หรือ fixtureเดิม10+29แถว

## ผลหลาย session จริง

ทุกกรณีใช้ READ COMMITTED ตาม runtime helper A ทำ operationจริงและคง transaction ไว้ Bผ่าน graph preflight แล้วจึงเริ่ม operation Observerแยก connection ตรวจ `pg_blocking_pids(B)` มี A พร้อม guard3PIDแตกต่าง ก่อนออก transaction A ด้วย ROLLBACK จากนั้น B ทำงานต่อและ ROLLBACKด้วย

| กรณี | การชนกัน | ผลหลัง A ROLLBACK | ผล |
|---|---|---|---|
| EC01 | คะแนนแรก / Task metadata | B รอ Project lock แล้วแก้ Task not_startedได้ ไม่เห็นคะแนน A | PASS |
| EC02 | คะแนนแรก / Milestone metadata | B รอแล้วแก้ Milestoneได้ตาม baseline | PASS |
| EC03 | คะแนนแรก / ถอน Task assignee | B รอแล้วถอนได้พร้อม historyชั่วคราว ก่อนคืนเดิมเมื่อ ROLLBACK | PASS |
| EC04 | เปิด Task completedกลับ in_progress / ให้คะแนน | B รอแล้วตรวจ phaseใหม่ พบ completed Milestoneเดิมคืนมาและให้คะแนนได้ | PASS |
| EC05 | ให้คะแนน assignmentเดียวกัน | B รอแล้วมีเฉพาะคะแนนของ B ภายใน B ไม่มีคะแนน A ที่ยกเลิกแล้ว | PASS |
| EC06 | ให้คะแนนคนละกรรมการ | B รอแล้วมีเฉพาะคะแนนของตน Team/Advisor/Coordinatorยังไม่เห็น partial summary | PASS |
| EC07 | คะแนนคนสุดท้าย / Team–Advisor–Coordinator reader | B รอแล้วเห็นเพียง2คะแนนตั้งต้น จึง summary=null/evaluations=[] ไม่มีผลรวมจากคะแนน A | PASS |
| EC08 | Team reader / คะแนนคนสุดท้าย | B รอ readerปล่อย Project lock แล้วบันทึกคะแนน80และเห็นรวม210/เฉลี่ย70ภายใน B | PASS |

ทุก case รายงาน `wait_observed:true`, `both_workers_rolled_back:true`, `public_rows_metadata_restored:true`, `direct_app_login:true` ตรวจทั้ง full public row values/metadata/ACL และ exact fixture graphหลัง Bจบ ไม่ใช้เวลา sleepหรือmockเป็นหลักฐาน lock wait และไม่มี SQL permission error/admin fallback ในผล8กรณีนี้

**ข้อจำกัดของผล:** เป็น winner-ROLLBACK จึงยังไม่พิสูจน์ Bถูกห้ามแก้ Taskหลัง A COMMIT หรือ duplicate loserหลังคะแนน A COMMIT เรื่อง first-score guard/duplicate เมื่อคะแนนอยู่ใน transactionเดียวกันพิสูจน์ใน rehearsal/API suiteแล้ว แต่ไม่นำมารวมอ้างว่า winner-COMMITผ่าน

## Tests และ regression

| ชุด | ผล / ขอบเขต |
|---|---|
| Safeguards ใหม่ | 39 PASS: runner16/fixture9/installer14 แบบ offline |
| Targeted regressionก่อนติดตั้ง | 94 PASS รวม safeguards/rehearsal/validation/Auth security/Evaluation API |
| DRY RUN42แถว | isolated16/ordered8 PASS และคืน baseline ไม่มี COMMIT/export |
| Installer exclusionบน graphจริง | PASS ใน outer ROLLBACK; public rowsเดิมไม่เปลี่ยน/manifest payload roundtripผ่าน |
| Persistent installation | APPLIED42, committed=true, manifest_saved=true, direct_app_login=true, existing_public_rows_unchanged=true, schema_acl_unchanged=true |
| Direct app preflight | PASS แบบอ่านอย่างเดียวก่อนเริ่ม EC8 |
| EC01–EC08 | 8/8 PASS, directapp/3PID/observed wait/A-B ROLLBACK |
| Full Backendหลังติดตั้ง | **508 PASS** ตามคำสั่งใน LOCAL_SETUP รวม39 safeguardsใหม่+13 rehearsalเพิ่มจากฐาน456 ไม่ใช่508live races |
| Full Browserหลังติดตั้ง | **100 PASS**, browser_database_rollback=PASS/fixture_connections=0 |
| Postflightหลัง regression | **PASS**, V1 52 functions/differences=[]/effective app ACL; manifests10+29+42แถว valid; applyซ้ำ ALREADY_INSTALLED/additional_rows=0/written=false |
| Auth/cleanup | **PASS**, shared fixture users19คนมี credentials0/sessions0, temporary Browser users0, fixture connections0/other app connections0 และไม่มี runnerฟังพอร์ต3000/8001ค้าง |
| Source/เอกสาร | **PASS**, Python syntax6ไฟล์/ลิงก์ภายใน123จุด, ไม่พบ private secret ใน12ไฟล์ที่ตรวจ; protected SQL/dependency7ไฟล์ตรง HEAD หลัง normalize EOL, whitespaceผ่านและไม่มี staging |

Production Backend/Frontend/SQL ไม่เปลี่ยนในรอบนี้ จึงไม่รัน build/lint/TypeScriptซ้ำ ผลผ่านชุดเหล่านั้นอยู่ใน [Evaluation implementation](EVALUATIONS_IMPLEMENTATION_REPORT.md) Regressionครั้งนี้ตรวจผลของ persistent seedต่อระบบเดิมโดยเฉพาะ

## ไฟล์ที่เพิ่ม/อัปเดต

เพิ่ม runner/test ใน `backend/tests/evaluation_concurrency.py`, `test_evaluation_concurrency.py`; fixture/installerใน `database/tools/Evaluation_Concurrency_Fixture.py`, `Evaluation_Concurrency_Fixture_Install.py`; safeguardsใน `database/tests/test_evaluation_fixture.py`, `test_evaluation_fixture_install.py` รายละเอียดหน้าที่/guardsอยู่ใน [preparation](EVALUATION_CONCURRENCY_PREPARATION.md)

อัปเดต Backlog/LOCAL_SETUP/SCHEMA2_INTEGRATION_HANDOFF และสถานะจาก rehearsal/preparationให้เชื่อมรายงานนี้ ไม่แก้ Source Submission/Milestone/Supabase ของเพื่อน ไม่มี dependency/.env/Requirements/Schema/RBAC changes และไม่ staging/Commit/Push

## วิธีรันซ้ำบนเครื่องนี้

หยุดงานเขียน test DB อื่นก่อนรัน ไม่สร้าง manifestใหม่/แก้ IDs/ใช้ Projectจริงแทน ไม่เผยแพร่ manifestนอก Git

```powershell
$evaluationFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\evaluation-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture_Install --check --manifest $evaluationFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_concurrency --run-rollback --fixture $evaluationFixtureManifest
```

เครื่องทีมที่ cloneโค้ดไม่ได้รับ seedหรือmanifestนี้ไปด้วย การอนุมัติครั้งนี้เฉพาะเครื่อง/test DBนี้ ไม่ติดตั้งให้เครื่องอื่นหรือย้ายไป Supabaseอัตโนมัติ หากmanifestหายหรือข้อมูลไม่ตรงให้หยุดตรวจ ไม่ seedซ้ำ/ลบ Projectเพื่อจัดการความไม่แน่นอน

## งานที่ยังเหลือ

- Winner-COMMIT ยังไม่อนุมัติ/ไม่ทดสอบ การอนุมัติ seed42แถวไม่ขยายไป COMMIT ของ A/B
- HTTP Evaluationมี [EH10 mixed5/dualHTTP5](EVALUATION_HTTP_CONCURRENCY_REPORT.md) รอบต่อมาแล้ว ส่วน sameactordualHTTP/physicalapp HTTPworkers/production connection factoryรายrequest/ทุกordering/randomload/40001-retry ยัง Not Verified
- Peer Submission/Milestone/Task API→Evaluation end-to-end, C-02ทุก race, fresh-machine install และ UATระบบรวมยังไม่ครบ

P18ยัง In Progress มีผล EC8เพิ่มจาก RC8/VC8/HTTP14/DH9เดิม แต่ยังไม่ครบ TX-01–TX-06 อัตราปิด checklistคง Done6/20=30% ไม่เพิ่มจากจำนวน tests
