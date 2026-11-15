# Evaluation — Live HTTP concurrency results

วันที่ 2026-11-15 (Asia/Bangkok) · local `feature/project-continuation` บน `679913a` + working tree · ไม่มี Commit/Push

**EH01–EH10 ผ่าน10/10** บน fixture42แถวที่ผู้ใช้อนุมัติไว้แล้ว ต่อจาก [EC01–EC08](EVALUATION_CONCURRENCY_REPORT.md) ใช้ test DB เดิม ไม่มี seedหรือบัญชี Login ถาวรเพิ่ม ทุก credential/session/business actionใหม่อยู่ใน outer ROLLBACK

## สิ่งที่เพิ่มและขอบเขต

- [evaluation_http_concurrency.py](../../backend/tests/evaluation_http_concurrency.py): default offline, ระบุ manifestก่อน live run, loopback TCP/Login/Session/CSRF/APIจริง และตรวจ 3PID/lock wait/overlap/cleanup
- [test_evaluation_http_concurrency.py](../../backend/tests/test_evaluation_http_concurrency.py): safeguards19 แบบ offline/mocked orchestration
- อัปเดต Backlog/LOCAL_SETUP/SCHEMA2_INTEGRATION_HANDOFF และลิงก์จากรายงาน EC8เดิม ไม่แก้ production Backend/Frontend/Schema/RBAC/requirements/dependency/.env หรือ Submission/Milestone/Supabase ของเพื่อน

มี **5 mixed HTTP/repository cases** และ **5 dual HTTP cases** ไม่อ้างว่าทั้ง10กรณีเป็นสอง HTTP clients Task/Milestone/assigneeฝั่ง repositoryใช้ controlled SQL เดิม ไม่มีการสร้าง APIของเพื่อนซ้ำ

## วิธีพิสูจน์ว่า request ชนกันจริง

1. ตรวจชื่อ `student_project_management_v1_test`/effective app/graphตามmanifestเดิม และเก็บ full public values/metadata/ACL กับ row countsรวมAuth ก่อน case
2. เริ่ม A ด้วย operationจริง โดย test-only UOW callbackพัก HTTP A ก่อนคืน response; ถ้า Aเป็นrepositoryให้พักหลัง operationโดยยังถือtransactionไว้ ไม่แก้ production handler หรือ mock HTTP status/DBoperation
3. เริ่ม Bหลัง Aถือlockแล้ว Bทำ Login/Me จริงก่อนส่ง Evaluation request พร้อม CSRF/Originเดิม หรือใช้ repositoryตามcase ObserverยืนยันPID A/B/observerแตกต่างและ `pg_blocking_pids(B)` มี A ขณะที่ทั้งสองฝั่งยังไม่จบ
4. ปล่อย callback ตรวจ response/no-store/exact DTO/own Evaluation/phase/summary แล้วปิด A/ROLLBACKก่อนรอ Bจบ จากนั้นปิด B/ROLLBACKด้วย ตรวจ public fingerprint/fixture graph/Auth counts/metadata กลับ baseline จึงนับ PASS

HTTP workersเตรียม credentialชั่วคราวเฉพาะ actorในmanifestด้วย effective `project_owner` ที่ไม่ใช่superuser ก่อนสลับเป็น effective `project_app` ทุก business request ทั้ง7 UOWของ Auth/Team/Project/Invitation/Committee/Topic/Evaluationยืมconnectionเดียวกันและมี guardตรวจ dependency set หากเพิ่มrouterใหม่แล้วลืมoverrideต้องหยุด

Repository workers/observerเป็น direct LOGIN project_app ส่วน HTTP workersเป็น borrowed fixture connectionที่ effective app **ยังไม่ใช่หลักฐาน physical LOGIN project_app/production openerต่อ HTTP request** ไม่มี owner retryหลังappถูกปฏิเสธ

## ผลจริง

| Case | A / B | HTTP status A/B | ผล |
|---|---|---|---|
| EH01 | HTTPคะแนนแรก / repositoryแก้Task metadata | 201 / — | PASS |
| EH02 | HTTPคะแนนแรก / repositoryแก้Milestone metadata | 201 / — | PASS |
| EH03 | HTTPคะแนนแรก / repositoryถอนTask assignee | 201 / — | PASS |
| EH04 | repositoryเปิดTask completedกลับ in_progress / HTTPให้คะแนน | — / 201 | PASS |
| EH05 | repositoryให้คะแนน / HTTPให้คะแนน assignmentเดียวกัน | — / 201 | PASS |
| EH06 | HTTPกรรมการ bให้คะแนน / HTTPกรรมการ cให้คะแนน | 201 / 201 | PASS |
| EH07 | HTTPคะแนนคนสุดท้าย / HTTPTeamอ่านผล | 201 / 200 | PASS |
| EH08 | HTTPคะแนนคนสุดท้าย / HTTPaccepted Advisorอ่านผล | 201 / 200 | PASS |
| EH09 | HTTPคะแนนคนสุดท้าย / HTTPCoordinatorอ่านผล | 201 / 200 | PASS |
| EH10 | HTTPTeam reader / HTTPคะแนนคนสุดท้าย | 200 / 201 | PASS |

ทุกกรณีมี `overlap_observed:true`, `database_wait_observed:true`, `both_workers_rolled_back:true`, `public_rows_auth_counts_metadata_restored:true` สำหรับ EH06–EH10ทั้งสอง HTTP responsesยังpendingระหว่าง observerยืนยันDBwait ไม่ใช่ส่งตามกันหลังresponseแรกจบ

หลัง A ROLLBACK EH01–03จึงแก้งานได้และคืนเดิมเมื่อ B ROLLBACK; EH04ให้คะแนนได้เมื่อ derived completed Milestoneกลับ baseline; EH05ไม่มีคะแนน Aค้างจึงได้201 ไม่ใช่duplicate409; EH06มีเฉพาะคะแนน BในBและยังไม่เผย partial summary; EH07–09กลับมาเหลือ2คะแนน จึง `summary:null` และ Coordinator `evaluations:[]`; EH10บันทึก80แล้วรวม210/เฉลี่ย70ภายในB ก่อนยกเลิกทั้งหมด

ตรวจ POST own DTOตรงกับ GETภายหลัง, IDsเป็นstring, scoreเป็นinteger, scopeProjectถูกต้อง, cannot-evaluate/ALREADY_EVALUATED และไม่ส่ง score/commentคนอื่นตาม [Contract](../api/EVALUATIONS_CONTRACT.md) ไม่มี SQL error/permission workaround ในผล10กรณีนี้

## Verification

| ชุด | ผล |
|---|---|
| Safeguardsใหม่ | **19 PASS** แบบoffline ป้องกันผิดmanifest/actor, overwritecredentials, drift, early response, ไม่เห็นwait, cleanupfailure และ errorredaction |
| Targeted safeguards regression | **79 PASS** = ใหม่19 + HTTPเดิม23 + DualHTTPเดิม21 + Auth security16 ไม่มีnetwork/DBในชุดนี้ |
| Baseline/fixtureก่อนlive | **PASS**, V1 52 functions/differences=[]/ACLตรง source และ fixture42แถวvalidผ่านdirectapp readonly |
| Live HTTP EH01–EH10 | **10/10 PASS** real TCP/Login/Session/CSRF/Origin/API/PGwait/3PID/overlap/A-B ROLLBACK |
| Postflight | **PASS**, baseline52 functions/ACL ตรง source และ manifests10+29+42แถว valid; shared fixture users19คนมี credentials0/sessions0 และ client connectionsอื่น0 |
| Source/เอกสาร | **PASS**, Python syntax/whitespace2ไฟล์/ลิงก์ภายใน119จุด, ไม่พบ private secret ใน7ไฟล์ที่ตรวจ; protected SQL/Auth/Invitation/dependency13ไฟล์ตรง HEAD หลัง normalize EOL และไม่มี staging |

Full Backend508/Browser100 เป็นผลหลังติดตั้งseed42จากรอบก่อน ไม่ได้รันทั้งหมดซ้ำรอบนี้ ไม่มี runtime/UI/seedเปลี่ยน จึงใช้ safeguards79+live10ตามผลกระทบ ไม่ขยายผลเป็น Backend/Browserชุดใหม่ผ่านทั้งหมด และไม่รัน build/lint/TypeScriptซ้ำ

## เรียกใช้

ใช้ manifestเดิมนอก Git หยุดงานเขียน test DBอื่นก่อนlive run Runnerเปิดพอร์ตloopbackชั่วคราวเอง ไม่ใช้/ปิดserverที่ผู้ใช้เปิดบน3000/8000/8001 Defaultแสดงแผนอย่างเดียว ไม่อ่านcredentials/เปิดnetwork

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_http_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_evaluation_http_concurrency backend.tests.test_http_concurrency backend.tests.test_dual_http_concurrency backend.tests.test_auth_security -q
$evaluationFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\evaluation-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Fixture_Install --check --manifest $evaluationFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.evaluation_http_concurrency --run-rollback --fixture $evaluationFixtureManifest
```

ไม่มี apply/COMMIT/seed mode ห้ามสร้างLoginถาวรหรือmanifestจากProjectจริงเพื่อรันแทน หากfixtureไม่ตรงให้หยุดตรวจตามรายงานติดตั้งเดิม

## งานที่ยังเหลือ

- Winner-COMMITยังไม่อนุมัติ/ไม่ทดสอบ ผลนี้พิสูจน์การ serializeและ recheckหลังA ROLLBACK ไม่พิสูจน์ loserเมื่อA COMMIT
- สองHTTPclientsactorเดียวกันยังไม่ทดสอบ EH05เป็นrepositoryA/HTTPBเพื่อไม่ต้องบันทึก credentialsร่วมถาวร ไม่เพิ่มวิธีLoginใหม่เอง
- Physicalproject_app HTTPworkers/production connection factoryรายrequest, HTTPTask/Milestone APIของเพื่อน, ทุกordering/40001/retry/randomload และUATระบบรวมยัง Not Verified
- Peer Submission/Milestone/Task integrationยังไม่รวม ไม่ย้ายไปSupabase และไม่ใช้DBหลัก

P18คง In Progress Done6/20=30%ตามchecklistเดิม ไม่มีงานหลักปิดเพิ่มจากจำนวนtests
