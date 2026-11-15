# Evaluation — Two-session runner and fixture preparation

วันที่ 2026-11-15 (Asia/Bangkok) · `feature/project-continuation` บน `679913a` + working tree

**ผลรอบหลังอนุมัติ:** ผู้ใช้ตอบ “อนุมัติบันทึก 42 แถวและรัน 8 กรณี” แล้ว ติดตั้ง APPLIED42แถวและรัน EC01–EC08 ผ่าน8/8 พร้อม direct app/3PID/lock wait จริง/A-B ROLLBACK อ่าน [รายงานผลจริง](EVALUATION_CONCURRENCY_REPORT.md) ส่วนด้านล่างเป็นหลักฐานขั้นเตรียมก่อนอนุมัติ ไม่ใช่สถานะรออนุมัติปัจจุบัน

ต่อจาก [rehearsal เดิม38แถว](EVALUATION_CONCURRENCY_REHEARSAL.md) ผู้ใช้ให้ดำเนินการต่อ จึงเตรียม multi-session runner และ fixture ใหม่ที่ตรงกับสถานะเริ่มต้นของทั้ง8กรณี พร้อม installer และ safeguards ยัง **ไม่ติดตั้ง fixture ถาวรและไม่รัน multi-session จริง** เพราะคำสั่งทดสอบเดิมกำหนด ROLLBACK และยังไม่ได้อนุมัติข้อมูลตั้งต้นชุดใหม่นี้

## สิ่งที่เตรียมแล้ว

| ไฟล์ | หน้าที่ |
|---|---|
| [evaluation_concurrency.py](../../backend/tests/evaluation_concurrency.py) | EC01–EC08, strict manifest, exact graph preflight, worker A/B/observer คนละ direct app connection, ตรวจ `pg_blocking_pids` และ ROLLBACK |
| [Evaluation_Concurrency_Fixture.py](../../database/tools/Evaluation_Concurrency_Fixture.py) | Offline plan / DRY RUN สร้าง graph42แถวใน UUID namespace ใหม่ ไม่มี COMMIT/export |
| [Evaluation_Concurrency_Fixture_Install.py](../../database/tools/Evaluation_Concurrency_Fixture_Install.py) | Prepared installer: default offline, apply ต้อง confirm test DB และ manifest นอก Git; ห้าม overwrite/reseed เมื่อมี manifest/seedเดิม |
| [test_evaluation_concurrency.py](../../backend/tests/test_evaluation_concurrency.py) | Safeguards16: manifest/graph/privacy/preflight/worker failure/observed wait orchestration/cleanup/redaction |
| [test_evaluation_fixture.py](../../database/tests/test_evaluation_fixture.py) | Safeguards9: default offline/namespace/row deltas/metadata/rollback/failure cleanup |
| [test_evaluation_fixture_install.py](../../database/tests/test_evaluation_fixture_install.py) | Safeguards14: apply confirmation/wrong DB/manifest durability/no duplicate seed/uncertain COMMIT/existing rows preservation |

อัปเดต Backlog/LOCAL_SETUP/SCHEMA2_INTEGRATION_HANDOFF และเพิ่มลิงก์จากรายงาน rehearsal เดิม ไม่มี production Backend/Frontend/Schema/RBAC/dependency/.env changes ไม่แก้ source Submission/Milestone/Supabase ของเพื่อน ไม่มี staging/Commit/Push

## ทำไมต้องมีข้อมูลตั้งต้นใหม่

fixture เดิม10แถวและ29แถวไม่ได้อยู่ใน phase พร้อมให้คะแนน จึงไม่ใช้ Project/บัญชีจริงแทน และไม่แก้ fixture ที่มี manifest ตรวจรับเดิม

ข้อมูลที่สร้างแล้ว ROLLBACK ใน DRY RUN จะไม่มองเห็นจาก connection อื่น A/B จึงต้องเริ่มจาก graph ที่บันทึกไว้ก่อน กรณีคะแนนแรกต้องมี0 Evaluation ส่วนกรณีคะแนนสุดท้ายต้องมี2 Evaluation อยู่แล้ว จึงจัด **2 Project แยกกัน**

- `main`: หัวข้อ approved, มี completed Milestone1/Task1 และอีก Milestone1/Task not_started1 เพื่อแยก first-score lock ออกจากข้อห้ามเดิมของ completed Task ไม่มี Evaluation ตั้งต้น
- `final`: หัวข้อ approved, มี completed Milestone1/Task1 และคะแนนของกรรมการ2คน60/70 อีกคนยังไม่ให้คะแนน คะแนน80ของคนสุดท้ายจะทำให้รวม210/เฉลี่ย70
- ทั้งสอง Project ใช้ accepted Advisor/กรรมการ3คน/Coordinator ที่เตรียมเป็น users จำลอง ไม่มี credentials/sessions หรือรหัสผ่าน Login

### จำนวนแถวที่เสนอให้ติดตั้งภายหลัง

| ตาราง | แถว |
|---|---:|
| users | 7: students2, advisors4, coordinator1 |
| teams / team_members / projects | อย่างละ2 = 6 |
| advisor_invitations / project_submissions / project_submission_files | อย่างละ2 = 6 |
| committee_assignments / committee_topic_votes | อย่างละ6 = 12 |
| milestones / tasks / task_assignees | อย่างละ3 = 9 |
| committee_evaluations | 2 |
| **รวม** | **42** |

นี่คือ graph ใหม่42แถว ไม่ใช่การติดตั้ง rehearsal เดิม38แถว และไม่รวมข้อมูลทดลองที่แต่ละ worker จะเพิ่มชั่วคราว ไม่สร้าง user role ใหม่; กรรมการยังเป็น advisor ตาม V1

## วิธีที่ runner จะตรวจ concurrency หลังอนุมัติ

ทุกกรณีตรวจชื่อ DB/physical session `project_app`/isolation READ COMMITTED/graph และ fingerprint ก่อนทำงาน A ถือ Project lock จาก operation จริง Observer มี PID แยกและตรวจว่ารายชื่อ `pg_blocking_pids(B)` มี A ก่อนออก transaction A ด้วย ROLLBACK จากนั้นรอ B จบและ ROLLBACK ด้วย ตรวจ graph/public row values/metadata/ACL คืนเดิมก่อนนับ PASS

| ID | A ที่ยังไม่ ROLLBACK | B ที่ควรรอ A | สิ่งที่ตรวจหลัง A ROLLBACK |
|---|---|---|---|
| EC01 | คะแนนแรก | แก้ Task metadata | B แก้ได้ตาม baseline ไม่มี first score ค้าง |
| EC02 | คะแนนแรก | แก้ Milestone metadata | B แก้ได้ตาม baseline |
| EC03 | คะแนนแรก | ถอน assignee ของ not_started Task | B ถอนได้ มี historyชั่วคราว และคืนเดิมเมื่อ B ROLLBACK |
| EC04 | เปิด Task completed กลับ in_progress | ให้คะแนน | B ตรวจ phase ใหม่และให้คะแนนได้หลัง A ถูกยกเลิก |
| EC05 | assignmentเดียวกันให้คะแนน | ให้คะแนน assignmentเดิม | เหลือเฉพาะคะแนน B ภายใน B; คะแนน A ไม่รั่วมา |
| EC06 | กรรมการคนแรกให้คะแนน | คนที่สองให้คะแนน | B เห็นเฉพาะแถวคะแนนของตน และยังไม่เปิด partial summary |
| EC07 | กรรมการคนสุดท้ายให้คะแนน | Team/Advisor/Coordinator อ่านผล | หลัง A ROLLBACK ยังมีเพียง2คะแนน; summary=null/individuals=[] |
| EC08 | Team reader ถือ Project lock | คะแนนคนสุดท้าย | B บันทึกและเห็นรวม210/เฉลี่ย70ได้หลัง A ROLLBACK |

ความคาดหวังนี้ต่างจาก ordered pair ที่ A ยังอยู่ใน session เดียว: เช่น EC01–03 ordered pair ต้องถูก P0001 แต่ waiter หลัง A ROLLBACK ต้องทำได้ ไม่ยก single-session failure มาเป็นผล concurrent success

Runner ไม่มี seed/COMMIT mode; ใช้เฉพาะ manifest ที่ validate ได้ ไม่รับ secrets/DSN/DBอื่น/IDsเลขไม่ถูกต้อง/namespaceของผู้ใช้จริง ภายใน worker ใช้ repository/controlled SQL เดิม ไม่มี HTTP Login/API request หรือ owner fallback

## ผลตรวจจริงรอบเตรียม

| ชุด | ผล |
|---|---|
| Safeguards ใหม่ | **39 PASS** = runner16 + fixture9 + installer14 เป็น offline/mocked orchestration ไม่ใช่39 live races |
| Targeted regression | **94 PASS** = ชุดใหม่39 + rehearsalเดิม13 + Evaluation validator12 + Auth security16 + Evaluation API14 |
| DRY RUN graph42 | **PASS** isolated16/ordered8, baseline_restored=true, committed=false, manifest_exported=false |
| Installer exclusion บน graphจริงใน ROLLBACK | **PASS** parse/payload roundtrip, exact42 row delta, hashของ public rowsเดิมไม่เปลี่ยน และคืน snapshot/fingerprintหลัง ROLLBACK ไม่มีไฟล์ manifest ถูกเขียน |
| Baseline ก่อนซ้อม | **PASS**, 52 functions/differences=[]/effective app privileges/Public ACL |
| ตรวจหลังซ้อม | **PASS**, baseline52/ACL ตรงเดิม; shared manifests10+29แถว valid; users namespace `spms-ec-` =0 และไม่มี evaluation manifest นอก Git จึงยังไม่ติดตั้งข้อมูลถาวร |
| Source/เอกสาร | **PASS**, syntax6ไฟล์/ลิงก์ภายใน114จุด/ไม่พบ private secret ใน11ไฟล์ที่ตรวจ; protected SQL/dependency7ไฟล์ตรง HEAD หลัง normalize EOL และไม่มี staging |
| Multi-session EC01–EC08 | **NOT RUN** รออนุมัติ fixture42แถว ไม่อ้างจาก mocked wait orchestration |
| Persistent apply/postflight | **NOT RUN** ส่วน COMMIT/manifest fsync ตรวจใน unit testsด้วย mocks เท่านั้น |

Owner ที่ไม่ใช่ superuserเตรียม users ใน DRY RUN และ effective `project_app` ทำ business operations ทุกคำสั่ง ส่วน direct LOGIN ของ worker จะตรวจจริงเมื่อรันหลาย session หลังอนุมัติ ไม่ใช้ผล borrowed owner connection ยืนยัน physical app worker

Full Backend456/Browser100/build/lint/TypeScript เป็นผลรอบ Evaluation implementation เดิม ไม่ได้รันซ้ำรอบนี้เพราะไม่มี runtime/UI changes ROLLBACKไม่คืน sequence values

## คำสั่งที่รันได้ขณะยังไม่อนุมัติข้อมูลถาวร

หยุดโปรแกรมอื่นที่กำลังเขียน test DB ก่อน DRY RUN เพื่อให้ fingerprintไม่ปะปนกับงานอื่น

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_concurrency
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture_Install
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_evaluation_concurrency database.tests.test_evaluation_fixture database.tests.test_evaluation_fixture_install database.tests.test_evaluation_concurrency_rehearsal backend.tests.test_evaluation_validation backend.tests.test_auth_security backend.tests.test_evaluation_api -q
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture --dry-run
```

## ประวัติขอบเขตที่ขออนุมัติก่อนใช้คำสั่ง apply

ขอข้อยกเว้นเฉพาะ **บันทึก graph42แถวถาวร** ใน `student_project_management_v1_test` และ manifestนอก Git ที่ `%LOCALAPPDATA%\StudentProjectManagement\concurrency\evaluation-v1.json` จากนั้นรัน EC01–EC08 โดย A/B ROLLBACK ทั้งหมด ไม่แก้ข้อมูลเดิม/Schema/RBAC/บัญชี Login

หากอนุมัติ fixture42แถวจะคงอยู่เพื่อรันทดสอบซ้ำ มี Projectจำลอง2รายการที่ R-01ห้ามลบ และอาจปรากฏในรายการ Coordinator ตามสิทธิ์ approved Project หากยังไม่อนุมัติจะไม่มีข้อมูลใหม่ค้าง และยังพิสูจน์ lock wait ของ8กรณีนี้ไม่ได้ การอนุมัติ seed เดิมหรือคำสั่งให้พัฒนาต่อไม่ถูกใช้เป็นสิทธิ์ COMMIT ชุดใหม่นี้เอง

คำสั่งชุดนี้รันหลังคำอนุมัติเฉพาะ42แถวแล้ว อ่านผลในรายงานรอบติดตั้งก่อนเรียกซ้ำ Installerจะตรวจ manifestเดิมแทนการ seedใหม่:

```powershell
$evaluationFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\evaluation-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture_Install --apply --confirm-database student_project_management_v1_test --manifest $evaluationFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_concurrency --preflight --fixture $evaluationFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_concurrency --run-rollback --fixture $evaluationFixtureManifest
```

Installerปฏิเสธเมื่อมี clientอื่นเชื่อม test DB และจะไม่ seedซ้ำเมื่อพบ manifest/ข้อมูลเดิม ต้องตรวจผลทีละคำสั่ง หากเกิด COMMIT uncertainty หรือ postflightผิดให้หยุด ไม่มี automatic retry/สร้างnamespaceใหม่ทับ เพราะ R-01ห้ามลบ Projectเพื่อจัดการความไม่แน่นอน

Peer Submission/Milestone integration, HTTP Evaluation concurrency, winner-COMMIT, Task-Evaluationทุกordering/TXครบ และ UAT ยัง Not Verified P18คง In Progress อัตราปิด checklist6/20=30% ไม่มีงานหลักปิดเพิ่ม
