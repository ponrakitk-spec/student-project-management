# ตั้งค่าเครื่องทีม — Windows/PowerShell

**การทดลองโดยผู้ใช้:** [Manual UAT](../uat/MANUAL_UAT.md) มีขั้นตอนTerminal A=rollbackBackend8001/Terminal B=Frontend3000ชี้8001 พร้อมsnapshotก่อน–หลัง ใช้สำหรับทดลองเขียนตามข้อจำกัดปัจจุบัน ไม่เปิดnormalruntime8000ด้านล่างเพื่อทดลองseedถาวร [คู่มือผู้ใช้](../user/USER_GUIDE.md)/[Demo](../user/DEMO_SCRIPT.md) อธิบายแต่ละบทบาทและpreconditionsที่ยังรอAPIเพื่อน

**Workspace overview 2026-11-15:** หลัง Loginกด **พื้นที่ทำงาน →** จากหน้าบัญชี หรือเข้า `/workspace` มีทีม/Projectจริงเฉพาะstudentและทางเข้างานสำหรับadvisor/coordinator ตาม [Contract](../api/WORKSPACE_OVERVIEW_CONTRACT.md) และ [ผลตรวจ](../progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) ใช้ API/fixture/configเดิม ไม่เพิ่มขั้นตอนติดตั้ง DB/seedหรือเปลี่ยนปลายทาง Login

คู่มือนี้ใช้ฐานข้อมูลPostgreSQLในเครื่องแต่ละคน ไม่มีDBกลาง/การเปิดLANในขอบเขตรอบนี้ การติดตั้งใหม่ครบเส้นทางยังเป็นNotVerifiedดู [ผลตรวจ](HANDOFF_VERIFICATION.md); คำสั่งด้านล่างอิงไฟล์/เครื่องมือจริง ไม่ใช่ผลfreshinstallที่ทดสอบแล้ว

## 1. โค้ดและโปรแกรม

หลังเจ้าของPushชุดhandoffแล้ว:

```powershell
git clone --branch feature/database-schema --single-branch https://github.com/ponrakitk-spec/student-project-management.git
cd student-project-management
git status --short
git log -1 --oneline
```

ต้องพบdocs/team/START_HERE.mdและbackend/invitation_api.py หากไม่มีแปลว่ายังไม่ได้baseรุ่นส่งต่อ ไม่ใช้เฉพาะcommit9d07c52เดิม

- Python3.12 และPostgreSQL18.6ตามbaselineโครงการ
- Nodeสำหรับเครื่องใหม่ใช้22.xตั้งแต่22.13.0ตามenginesในlockfileของdependencyที่เข้มที่สุดที่ตรวจพบ เครื่องเดิมทดสอบด้วย20.10.0/npm10.2.3แล้วlint/buildผ่าน แต่มีenginewarning; ยังไม่ได้พิสูจน์freshinstallบนNode22 ไม่ถือว่ารุ่นเครื่องเดิมเป็นรุ่นแนะนำ
- Browsertestsใช้MicrosoftEdgeที่ติดตั้งในWindows ไม่ต้องเปลี่ยนchannelหรือดาวน์โหลดbrowserทดแทนเอง

```powershell
py -3.12 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
& .\backend\.venv\Scripts\python.exe -m pip check
Push-Location frontend
npm ci
Pop-Location
```

ไม่copy.venv/node_modules/.nextจากเพื่อนและไม่รันnpm updateแทนnpm ci ระหว่างตั้งbaseline รักษาpackage-lock/requirementsเดิม

## 2. Privateconfig

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) {
    Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
}
```

กรอกด้วยeditorบนเครื่องตน ไม่ส่งในGit/แชท:

| ค่า | ใช้งาน |
|---|---|
| AUTH_DB_HOST/PORT/PASSWORD | Runtimeproject_app; passwordต้องตรงroleproject_appในPostgreSQLของเครื่องตน |
| DB_HOST/PORT/USER/PASSWORD | ผู้ดูแลติดตั้ง/rollbackfixtures; installerเดิมคาดloginpostgresแล้วSETROLEowner/appตามงาน ไม่ใช้เป็นAPIfallback |
| DB_NAME | ใส่testDBตามtemplateเพื่อความปลอดภัยของlegacyconnector แต่runtime/toolsหลักpinDBเอง |

backend/.env.auth.exampleยังเป็นtemplateย่อยสำหรับruntime-only; templateครบสำหรับเครื่องทีมคือbackend/.env.example อย่าoverwrite.envเดิม มีconfigครบไม่ได้แปลว่าDBพร้อม ต้องทำ [Database Setup](DATABASE_SETUP.md)

FrontenddefaultAPIคือhttp://localhost:8000 ไม่ต้องสร้าง.env.local หากต้องระบุให้ใช้frontend/.env.exampleและใส่เฉพาะpublicAPIorigin ห้ามใส่DBsecretในNEXT_PUBLIC_*

## 3. เปิดระบบหลังDBพร้อม

Terminalจากroot:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

อีกTerminal:

```powershell
cd frontend
npm run dev -- --hostname localhost --port 3000
```

เข้าhttp://localhost:3000/login และhttp://localhost:8000/docs ใช้browserhostlocalhostตามOrigin/Cookieที่ยืนยัน ไม่เปลี่ยนเป็น127.0.0.1/LANเอง

Normalruntimeบันทึกข้อมูลเมื่อoperationสำเร็จ การทดสอบอัตโนมัติใช้rollbackfixtureด้านล่างแทนการกดnormalUIเพื่อseedข้อมูลถาวร

## 4. ตรวจรับbaselineก่อนเริ่มfeature

จากroot ไม่รันsuiteนี้พร้อมเพื่อนบนDBเดียวกัน:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Static_Gate
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Install --check-runtime
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_team_update_api backend.tests.test_team_leader_transfer_api backend.tests.test_team_membership_exit_api backend.tests.test_invitation_api backend.tests.test_committee_api backend.tests.test_topic_vote_api database.tests.test_test_database database.tests.test_advisor_provision database.tests.test_coordinator_provision backend.tests.test_team_project_concurrency_harness backend.tests.test_team_project_transaction_failures database.tests.test_concurrency_fixture database.tests.test_concurrency_fixture_install backend.tests.test_topic_vote_concurrency database.tests.test_topic_vote_fixture database.tests.test_topic_vote_fixture_install backend.tests.test_http_concurrency backend.tests.test_dual_http_concurrency backend.tests.test_evaluation_validation backend.tests.test_evaluation_api database.tests.test_evaluation_concurrency_rehearsal backend.tests.test_evaluation_concurrency database.tests.test_evaluation_fixture database.tests.test_evaluation_fixture_install -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --test-installed --workflow
```

StaticGateไม่ใช่PostgreSQLruntimecheck หากDB/role/grantsไม่ตรงให้หยุดอ่านerror อย่ารันinitialinstallerซ้ำบนตารางที่มีอยู่หรือเพิ่มappUPDATEเพื่อให้ผ่าน

คำสั่งregressionอัปเดตถึงTeam/Projectupdate/Leadertransfer/Leave-removalในlocalfeature/project-continuationแล้ว [Backend242/Browser73/build/lint/TypeScriptผ่าน](../progress/TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md) พร้อมROLLBACK Browser63เป็นผลรอบtransferก่อนหน้า ไม่รวมSubmission/Milestoneของเพื่อนที่ยังไม่ได้merge ผลเก่าในhandoff2026-11-07เป็นคนละsnapshot

ผลล่าสุด 2026-11-15: คำสั่ง Full Backend ด้านบน **PASS508** รวม Evaluation rehearsal13/runner16/fixture9/installer14 เพิ่มจากฐาน456; Browser **PASS100** หลังติดตั้ง seed42แถวพร้อม ROLLBACK/fixture connections0 และ EC8หลายsessionผ่านจริง ดู [Concurrency report](../progress/EVALUATION_CONCURRENCY_REPORT.md) ส่วน lint/TypeScript/build ผ่านใน [รอบ Evaluation implementation](../progress/EVALUATIONS_IMPLEMENTATION_REPORT.md) ไม่ได้รันซ้ำเพราะ runtime/UIไม่เปลี่ยน ผลนี้ยังไม่ใช่ Submission/Milestone API ของเพื่อนหรือ winner-COMMIT/TX/UAT ครบระบบ

Evaluation เปิดจาก Project/รายการกรรมการ/accepted Advisor/Coordinator เดิม ฟอร์มกรรมการจะเปิดเมื่อหัวข้อล่าสุด approved และมี derived completed Milestone ≥1 เท่านั้น Browser runner เตรียม phase fixtures ชั่วคราวด้วย controlled SQL และยกเลิกทั้งหมดหลังทดสอบ จึงไม่ได้สร้าง Project พร้อมประเมินหรือบัญชี Login ถาวรให้ทดลองเอง Shared concurrency fixtures10+29แถวยังคงเดิม ต้องเชื่อม API ของเพื่อนก่อนตรวจรับ workflow รวม

**Evaluation rehearsal เพิ่มเติม 2026-11-15:** มี [สคริปต์ซ้อม8สถานการณ์](../progress/EVALUATION_CONCURRENCY_REHEARSAL.md) พร้อมคำสั่งเฉพาะ; default offline และ `--dry-run` ใช้ fixture38แถวชั่วคราวใน test DB แล้ว ROLLBACKทั้งหมด ผ่าน isolated16/ordered8/targeted64 ยังไม่ใช่ multi-session/HTTP concurrency ไม่มี apply/export และห้ามนำ IDs ที่ ROLLBACK ไปใช้ต่อ ชุด Full Backend456/Browser100 ด้านบนเป็นผลรอบ Evaluation implementation ก่อนเพิ่มเครื่องมือซ้อมนี้

**Evaluation multi-session ต่อมา:** [Preparation](../progress/EVALUATION_CONCURRENCY_PREPARATION.md) ผ่านชุดใหม่39/targeted94/DRY RUN แล้ว ผู้ใช้อนุมัติ seed42แถวเฉพาะเครื่องนี้ ติดตั้งและ [EC01–EC08ผ่าน8/8](../progress/EVALUATION_CONCURRENCY_REPORT.md) พร้อม directapp/3PID/lock waitจริง/A-B ROLLBACK Manifestอยู่ `%LOCALAPPDATA%\StudentProjectManagement\concurrency\evaluation-v1.json` นอก Git; cloneไม่ได้คัดลอก fixture/manifestไปเครื่องทีม การอนุมัตินี้ไม่ครอบคลุมติดตั้งเครื่องอื่นหรือ winner-COMMIT และห้ามนำ IDs จาก DRY RUN มาใช้ต่อ

**Evaluation HTTP ต่อมา:** [EH01–EH10ผ่าน10/10](../progress/EVALUATION_HTTP_CONCURRENCY_REPORT.md) บนmanifest42เดิม realTCP/Login/CSRF/API/3PID/overlap/A-B ROLLBACK มี5mixedกับ5dualHTTP ไม่สร้างcredentialถาวรและไม่แก้APIเพื่อน Safeguardsใหม่19/รวม79ผ่าน คำสั่งเฉพาะอยู่ในรายงาน FullBackend508/Browser100ด้านบนเป็นผลรอบติดตั้งก่อนเพิ่มrunnerนี้ ไม่ใช่ผลfullใหม่

**บัญชีCoordinator:** ผู้ใช้เลือก [กรอกชื่อ/email/passwordผ่านCLIบนเครื่องเอง](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) ให้ใช้Terminalที่รับhiddenpasswordได้ ไม่ส่งรหัสผ่านในแชท ค่าเริ่มต้นDRY RUN; การบันทึกบัญชีที่กรอกเองใช้applyแยกตามคู่มือ ไม่มีauto-provisionจากAPIหรือtests:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Coordinator --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Coordinator --dry-run
```

เมื่อบันทึกบัญชีแล้ว Loginจากlocalhost:3000และกดจัดการกรรมการโครงงาน Projectจะแสดงเมื่อมีapprovedSubmissionจริงเท่านั้น Browserfixtureใช้DB-onlyphasegraphซึ่งROLLBACKไม่ทิ้งข้อมูลไว้ให้normalUI ไม่แก้G-12ให้เห็นทุกProjectเพื่อสาธิต

**Topic votes:** advisorเปิด“งานกรรมการ”จากหน้าบัญชีเพื่อเลือกProjectที่ตนได้รับแต่งตั้ง ลงมติได้เมื่อlatestSubmissionapproved/กรรมการ≥3และตนยังไม่ลง; acceptedAdvisorใช้“โครงงานที่ปรึกษา”; studentเข้าจากProject→รายชื่อกรรมการและผลหัวข้อ; Coordinatorเข้าจากหน้าจัดกรรมการ→ดูการลงมติรายบุคคล ตาม [Contract](../api/TOPIC_VOTES_CONTRACT.md) ไม่มีบัญชีหรือapprovedphaseข้อมูลใหม่ค้างหลังBrowser จึงไม่รับรองว่าหน้าnormalUIของแต่ละเครื่องมีProjectพร้อมทดลองแล้ว ไม่เพิ่มseed/แก้Submissionเพื่อนเอง

**Topic/Committee Concurrency:** [ติดตั้งsharedfixture29แถวตามอนุมัติและVC01–VC08ผ่าน8/8แล้ว](../progress/TOPIC_VOTE_CONCURRENCY_REPORT.md) directapp/3PID/รอlockจริง/A-BROLLBACK Offlineรวม71ผ่าน seedตั้งต้น29แถวคงอยู่ การตรวจและทดสอบบนเครื่องที่ติดตั้งแล้วใช้manifestเฉพาะDBนี้นอกGit ไม่ใช้manifestTeam/ProjectหรือProjectจริงแทน:

```powershell
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Topic_Vote_Concurrency_Fixture_Install --check --manifest $topicFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.topic_vote_concurrency --run-rollback --fixture $topicFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_topic_vote_fixture_install backend.tests.test_topic_vote_concurrency database.tests.test_topic_vote_fixture backend.tests.test_team_project_concurrency_harness database.tests.test_test_database -q
```

rehearsal `Topic_Vote_Concurrency_Fixture --dry-run` ยังROLLBACKเสมอ ไม่มีapply/COMMIT/exportmode ส่วนinstallerแยกใช้บันทึก29แถวตามอนุมัติแล้วและrepeatapplyไม่เพิ่มข้อมูล ห้ามนำIDsที่ROLLBACKไปทำmanifestหรือเปลี่ยนpathเพื่อสร้างseedชุดที่สอง ไม่เปลี่ยนSchema/RBACหรือfixtureเดิม10แถว ยังไม่winner-COMMIT/HTTP/TXครบ

**HTTP Concurrencyล่าสุด:** [ผ่าน14/14กับOffline88](../progress/HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) ใช้Aถือtransactionผ่านrepositoryและBLogin/APIผ่านTCPจริง พอร์ตloopbackอัตโนมัติ ทุกbusinessrequestเป็นeffectiveproject_app Bเตรียมcredentialชั่วคราวด้วยownerก่อนserveแล้วROLLBACKรวมsession ไม่เพิ่มบัญชีหรือseedถาวร ใช้สองmanifestเดิมและไม่เขียนDBจากที่อื่นพร้อมกัน:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.http_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_http_concurrency backend.tests.test_auth_security backend.tests.test_team_project_concurrency_harness backend.tests.test_topic_vote_concurrency database.tests.test_test_database -q
$teamFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.http_concurrency --run-rollback --team-fixture $teamFixtureManifest --vote-fixture $topicFixtureManifest
```

คำสั่งแรก/ชุดunittestเป็นOffline คำสั่งสุดท้ายเปิดtestserverชั่วคราวและเขียนในouterROLLBACK ต้องใช้privatefixtureconfigเดิม; ห้ามเปลี่ยนruntimeให้ใช้admin หรือนำผลนี้อ้างว่าสองHTTPclients/winner-COMMIT/physicalproject_appของB/UATผ่านแล้ว

**สองHTTPclientsล่าสุด:** [DH01–DH09ผ่าน9/9/Offline60/HTTPเดิม14regressionผ่าน](../progress/DUAL_HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) Loginจริงคนละactor ใช้credentialชั่วคราวแยกtransactionและeffectiveproject_appทั้งสอง APIrequestซ้อนกันก่อนresponseและพบDBwaitจริง จากนั้นA/BROLLBACK ไม่ใช่winner-COMMIT/physicalLOGINapp/ผู้ใช้เดียวกันสองฝั่ง ใช้manifestเดิม:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.dual_http_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_dual_http_concurrency backend.tests.test_http_concurrency backend.tests.test_auth_security -q
$teamFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.dual_http_concurrency --run-rollback --team-fixture $teamFixtureManifest --vote-fixture $topicFixtureManifest
```

หยุดงานเขียนtestDBอื่นระหว่างLivecases จุดพักUOWเป็นtest-onlycallbackไม่ใช่productionAPI ไม่รันCOMMITเพื่อให้สองconnectionเห็นcredentialของผู้ใช้เดียวกัน และไม่ใช้credentialsจริงของทีมแทนfixtureusers

Concurrency ล่าสุด [RC01–RC06ผ่าน6/6บนPostgreSQLหลังติดตั้งseedตามอนุมัติ](../progress/TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) แต่ยังไม่ครบwinner-COMMIT/HTTP/TX ดู [แผนและข้อจำกัด shared fixture](../progress/TEAM_PROJECT_CONCURRENCY_PLAN.md) คำสั่งสองรายการนี้เป็น Offline ไม่สร้าง fixture/อ่าน .env/ต่อ DB:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_team_project_concurrency_harness -v
```

Offline safeguards ใหม่25กรณีผ่าน แยกจาก Backend242/Browser73เดิม อย่าใช้ผลนี้อ้างว่า multi-session ผ่านแล้ว และอย่าใช้ทีมจริงแทน dedicated fixture เพื่อรัน `--run-rollback`

ขั้น [fixture rehearsal](../progress/TEAM_PROJECT_CONCURRENCY_FIXTURE_REHEARSAL.md) ตรวจผ่านแล้ว: 10แถว/12sequentialactions พร้อมROLLBACK และ Offlineรวม79ผ่าน ไม่มี shared fixtureถาวรหรือ apply mode คำสั่งแรกเป็นOffline ส่วน `--dry-run` เชื่อมtest DBและเขียนเฉพาะtransactionที่ย้อนคืน ต้องหยุดการเขียนtest DBจากชุดอื่นก่อนรัน:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_concurrency_fixture -v
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture --dry-run
```

ผล rehearsal ไม่ใช่ multi-session/lock timeout และไม่ export manifest ของ ID ที่ ROLLBACK ไปแล้ว รอบถัดมาเจ้าของอนุมัติการบันทึกข้อมูลร่วมเฉพาะseedเริ่มต้นแล้ว ผลติดตั้ง/RC6อยู่ด้านล่าง ไม่เปลี่ยนพฤติกรรมROLLBACKของrehearsal

**บนเครื่องที่ติดตั้งseedแล้ว:** ใช้manifestของDBในเครื่องนั้น ซึ่งอยู่นอกGit อย่าคัดลอกIDsข้ามDBหรือเปลี่ยนpathเพื่อสร้างseedชุดที่สอง การติดตั้งครั้งนี้ได้รับอนุมัติและตรวจrepeatapplyไม่เพิ่มแถวแล้ว ไม่มีauto-seedในคำสั่งtest:

```powershell
$concurrencyManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Team_Project_Concurrency_Fixture_Install --check --manifest $concurrencyManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_concurrency --run-rollback --fixture $concurrencyManifest
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_concurrency_fixture_install database.tests.test_concurrency_fixture backend.tests.test_team_project_concurrency_harness -q
```

RCทุกcaseROLLBACKกลับbaselineที่มีseed10แถว แต่seedยังคงอยู่ตามอนุมัติ R-01ห้ามลบProject การอนุมัติseedไม่ครอบคลุมwinner-COMMITของbusinessactions Backend regression291และfinaltool safeguards50ผ่านตาม [รายงาน](../progress/TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md)

ส่วนขยาย [RC07–RC08 Projectlock/injecteddeadlock](../progress/TEAM_PROJECT_TRANSACTION_FAILURES_REPORT.md) ผ่าน2/2และOfflineรวม64ผ่าน ใช้fixture/manifestเดิม ไม่รันinstallerหรือเพิ่มseed คำสั่งสุดท้ายจงใจสร้างdeadlockในtestเท่านั้นเพื่อคาดหวัง40P01และROLLBACK ไม่เปลี่ยนlock orderของAPI:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_team_project_transaction_failures backend.tests.test_team_project_concurrency_harness database.tests.test_concurrency_fixture database.tests.test_concurrency_fixture_install -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_project_transaction_failures --run-rollback --fixture $concurrencyManifest
```

จากfrontend:

```powershell
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
npm run test:e2e
```

ปิดnormalFrontend3000ก่อนbuild/Browserและให้8001ว่าง ใช้npmrunnerเพื่อได้uniquefixturetag Backendfixture8001เตรียมstaffด้วยnon-superuserownerในtransactionแล้วserveทุกrequestเป็นeffectiveproject_app; runtime8000ยังเป็นdirectLOGINapp Roleboundaryดู [รายงานInvitations](../progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) ไม่ใช่หลักฐานrealmulti-sessionconcurrency

เมื่อเพิ่มfeatureใหม่ ให้รันtestsเฉพาะงานก่อน แล้วregression/Browserที่ได้รับผลกระทบและพิสูจน์ROLLBACKcleanup อย่าเพิ่มpermanentfixturesเพื่อหลบข้อจำกัด
