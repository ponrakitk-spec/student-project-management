# Student Project Management System

**ชุดส่งต่อ branch รวม (2026-11-16):** ผู้ใช้อนุมัติเผยแพร่งานวันนี้บน `feature/team-integration` รวม Submission/Milestone/Task และการเตรียม Supabase ดู [สรุปชุดส่งต่อและจุดพักงาน](docs/team/INTEGRATION_RELEASE_2026-11-16.md) Supabase **ยังไม่ติดตั้งจริง** ข้อความ “ยังไม่ Commit/Push” ด้านล่างเป็น snapshot ของรอบพัฒนาแต่ละช่วง ให้ตรวจ commit/remote ปัจจุบันจาก Git

**Supabase เตรียมเชื่อมต่อ (2026-11-16):** ผู้ใช้เลือกฐานข้อมูลกลางและคง Login เดิม เพิ่มโหมด `supabase_test` แบบ opt-in, Project/TLS/role guards และ SQL deployment draft จากเพื่อน ดู [คู่มือ](docs/team/SUPABASE_SETUP.md) และ [รายงาน](docs/progress/SUPABASE_PREPARATION_REPORT.md) **ยังไม่สร้าง/ติดตั้ง/ทดสอบบน Project จริงหรือย้ายข้อมูล** ค่าเริ่มต้นและชุดทดสอบเดิมยังใช้ local test DB ไม่ Commit/Push

**Task/ผู้รับผิดชอบล่าสุด (2026-11-16):** เพิ่ม Task API/UI ของทีมตาม [Contract](docs/api/TASKS_CONTRACT.md) และ [รายงาน](docs/progress/TASK_IMPLEMENTATION_REPORT.md) เข้า Project → Milestone → งานย่อยและผู้รับผิดชอบ เพื่อสร้าง/มอบหมาย/ทำงานให้เสร็จและอ่านประวัติ Milestone เปลี่ยนสถานะตาม Task จริงและเปิด Evaluation เมื่อผ่านเงื่อนไขเดิม งานยังอยู่ local `feature/team-integration` ไม่ Commit/Push

**พัฒนาต่อจากงานเพื่อน (2026-11-16):** เพิ่มหน้า `/projects/submissions`, `/advisor/submissions` และ Milestone API/UI สำหรับทีมที่ `/projects/milestones` ตาม [รายงานรอบนี้](docs/progress/PEER_WORK_CONTINUATION_REPORT.md) ใช้ branch `feature/team-integration` ที่ยังไม่ Commit/Push; ไม่รวม Task API หรือ Supabase runtime ข้อความสถานะก่อนหน้านี้ด้านล่างเป็นประวัติของแต่ละรอบ

**รวมงานล่าสุด (2026-11-16):** branch `feature/team-integration` เชื่อม Backend Submission ของเพื่อนกับระบบเดิมแล้ว ตาม [Contract](docs/api/SUBMISSIONS_CONTRACT.md) และ [รายงาน integration](docs/progress/SUBMISSION_INTEGRATION_REPORT.md) ยังคง PostgreSQL test DB/`project_app` เดิม ส่วน Submission UI, Milestone API/UI และ Supabase runtime ยังไม่รวม ชุด integration ยังไม่ได้ Commit/Push

**พักพัฒนา/ชุดส่งต่อ (2026-11-15):** อ่าน [สรุปงานที่เพิ่มจากฐาน 679913a และผลตรวจชุดส่งต่อ](docs/team/RELEASE_PREPARATION_2026-11-15.md) งานรอบนี้ใช้ branch `feature/project-continuation` และยังไม่รวม branch ของเพื่อน ตรวจ commit/remote ที่ได้รับก่อนเริ่มงาน

ระบบจัดการโครงงานนักศึกษา ใช้ FastAPI + PostgreSQL และ Next.js/TypeScript

**สำหรับทีมที่จะรับงานSubmission/Milestone:** เริ่มที่ [Team Start Here](docs/team/START_HERE.md), [ตั้งค่าWindows](docs/team/LOCAL_SETUP.md), [Databaseแยกเครื่อง](docs/team/DATABASE_SETUP.md) และ [ผลตรวจชุดส่งต่อ](docs/team/HANDOFF_VERIFICATION.md) ใช้โค้ดbasecommitเดียวกันหลังเจ้าของPushแล้ว ข้อมูล/บัญชีในPostgreSQLไม่ติดไปกับGit

**สำหรับทดลองใช้งาน/เตรียมส่งอาจารย์:** อ่าน [คู่มือผู้ใช้](docs/user/USER_GUIDE.md), [Manual UATแบบROLLBACK](docs/uat/MANUAL_UAT.md) และ [ลำดับDemo](docs/user/DEMO_SCRIPT.md) ใช้API8001สำหรับทดลองเขียนตามข้อจำกัดเดิม ไม่ใช้normalmode8000เพื่อseedข้อมูลถาวร UAT20กรณียังNot Runโดยผู้ใช้

## สถานะปัจจุบัน

- **พื้นที่ทำงาน (2026-11-15):** เพิ่ม `/workspace` จากลิงก์ในหน้าบัญชี นักศึกษาเห็นทีม/Projectของตนจาก APIจริง ส่วน advisor/coordinatorมีทางเข้างานตามบทบาท ตาม [Contract](docs/api/WORKSPACE_OVERVIEW_CONTRACT.md) และ [ผลตรวจ](docs/progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) ขอบเขตนี้ยังไม่รวม Dashboard metrics/Timeline/Contribution
- **Evaluation ล่าสุด (2026-11-15):** กรรมการให้คะแนนจำนวนเต็ม 0–100 พร้อมความคิดเห็น บันทึกครั้งเดียว; Team/acceptedAdvisor/กรรมการเห็นรวมและเฉลี่ยเมื่อครบ ส่วน Coordinator เห็นรายบุคคลหลังครบ ตาม [Contract](docs/api/EVALUATIONS_CONTRACT.md) และ [รายงานผลทดสอบ](docs/progress/EVALUATIONS_IMPLEMENTATION_REPORT.md) ยังไม่รวม Submission/Milestone API ของเพื่อนหรือ UAT ระบบรวม
- **Topic votes (2026-11-15):** กรรมการลงมติและอ่านVoteตนเอง/ผลรวมเมื่อครบ; TeamและacceptedAdvisorอ่านรายชื่อ/ผลรวม/ความคิดเห็นที่ไม่แนบผู้ลงมติหลังครบ; CoordinatorดูVoteรายบุคคล ตาม [Contract](docs/api/TOPIC_VOTES_CONTRACT.md) และ [รายงานผลทดสอบ](docs/progress/TOPIC_VOTES_IMPLEMENTATION_REPORT.md)
- Coordinator: รายการProjectหลังอาจารย์อนุมัติและเพิ่ม/เปลี่ยน/ถอดกรรมการก่อนVoteแรกที่ `/coordinator/projects`; [CLIเตรียมบัญชีcoordinatorบนเครื่อง](docs/database/COORDINATOR_ACCOUNT_PROVISIONING.md) ให้ผู้ดูแลกรอกเอง

- Backend Auth: สมัคร student, Login, Logout และ GET /api/v1/auth/me
- Backend Team: POSTสร้างทีม/GETทีมของตน และ GET/POST /api/v1/teams/me/members สำหรับอ่านรายชื่อทีมตน/หัวหน้าเพิ่มmemberด้วยอีเมล ตาม [Members Contract](docs/api/TEAM_MEMBERS_CONTRACT.md); ไม่มีทีมตอบ404 TEAM_NOT_FOUND ตามG-12
- Frontend Auth: /register, /login และหน้าข้อมูลบัญชีที่ / แบบ Feature-based ใน src/features/auth
- Database V1: public 14 ตาราง / 86 columns / 28 foreign keys; ส่วนขยาย Auth แยก auth.credentials และ auth.sessions
- Session คงที่ 8 ชั่วโมง; อีเมลจำลองได้แต่ต้องรูปแบบถูกต้อง รหัสผ่าน ≥8 ตัว มี A–Z และตัวเลขอย่างละ ≥1
- Frontend Team: /teamsสร้าง/อ่าน/แก้ทีม เพิ่มmemberด้วยอีเมล โอนหัวหน้า และออก/ถอดสมาชิกตามสิทธิ์/phaseที่ยืนยันแล้ว ไม่มีuser directory อ่านวิธีทดลองแต่ละบทบาทในคู่มือผู้ใช้
- Project: หัวหน้าสร้างหนึ่งProjectต่อทีม สมาชิกอ่านของทีมตน และหัวหน้าแก้ชื่อ/คำอธิบายตามphaseผ่านหน้า/projects ไม่มีDELETE ตาม [Create Contract](docs/api/PROJECT_CREATE_CONTRACT.md)/[Update Contract](docs/api/PROJECT_UPDATE_CONTRACT.md)
- Advisor invitations: /projects/advisor-invitationsให้ทีมอ่านประวัติ/หัวหน้าส่งและยกเลิก ส่วน/advisor/invitationsให้อาจารย์ตอบรับ/ปฏิเสธ เลือกจากรายชื่อและตรวจสิทธิ์ตามG-12; มีบัญชีadvisor1บัญชีที่ผู้ดูแลบันทึกตามอนุมัติแล้ว ไม่ใช่บัญชีที่ค้างจากtests
- เตรียมบัญชีadvisor: มี [CLIสำหรับผู้ดูแลและผลบันทึก](docs/database/ADVISOR_ACCOUNT_PROVISIONING.md) DefaultDRY_RUN/ROLLBACK รับรหัสผ่านผ่านhiddenTerminal ไม่แก้บัญชีเดิม --applyบันทึกบัญชีที่อนุมัติ1บัญชีแล้ว บัญชีอื่นยังต้องอยู่ในขอบเขตที่อนุมัติ

รายละเอียดและหลักฐานล่าสุด: [Backlog](docs/progress/BACKLOG.md), [Schema V1 Reference](docs/database/SCHEMA_V1_REFERENCE.md), [Auth Contract](docs/api/AUTH_CONTRACT.md), [Auth Installation Report](docs/database/AUTH_INSTALLATION_REPORT.md), [Advisor Invitations Report](docs/progress/ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md)

## โครงสร้าง

| โฟลเดอร์ | เนื้อหา |
|---|---|
| backend/ | FastAPI, Auth, dependencies และ HTTP/unit tests |
| frontend/ | Next.js routes/features และ Browser tests |
| database/schema/ | SQL V1 และ RBAC ต้นฉบับ |
| database/auth/ | SQL review ส่วนขยาย Auth |
| database/tests/ | Static/DB regression และ helpers ที่ tests อื่น import ใช้ |
| database/tools/ | เครื่องมือตรวจ/ติดตั้ง อ่านข้อจำกัดก่อนรัน |
| docs/ | ข้อกำหนด, API contracts, ผลทดสอบ, backlog และเอกสารประวัติ |

## GitHub กับฐานข้อมูลของทีม

Clone โค้ดไม่ได้คัดลอก PostgreSQL service, database, roles, รหัสผ่าน หรือข้อมูลในเครื่องเจ้าของโปรเจกต์ไปด้วย Repository นี้มี SQL และเครื่องมือสำหรับเตรียมฐานข้อมูล แต่ยังไม่มีชุด bootstrap เครื่องใหม่ที่ตรวจรับครบทุกขั้น

| วิธีทำงาน | สมาชิกต้องเตรียมอะไร | ข้อมูลที่มองเห็น |
|---|---|---|
| แต่ละคนใช้ PostgreSQL ในเครื่องตนเอง — แนะนำสำหรับพัฒนา | ติดตั้ง PostgreSQL, เตรียม roles/schema/RBAC/Auth และตั้ง .env ของตนเอง | โครงสร้างตรงกันเมื่อใช้ baseline รุ่นเดียวกัน แต่บัญชี/ข้อมูลแต่ละเครื่องแยกกัน |
| แต่ละคนรัน Backend ในเครื่อง แล้วเชื่อม DB กลาง | ผู้ดูแลเตรียม test DB กลางและสิทธิ์เครือข่าย; แต่ละ Backend ตั้ง AUTH_DB_HOST/PORT/PASSWORD ส่วนตัวให้ตรงปลายทาง | อ่าน/เขียนฐานข้อมูลชุดเดียวกัน การทดสอบจึงอาจกระทบกัน |

ทั้งสองแบบใช้ชื่อ **student_project_management_v1_test** เท่านั้น ห้ามใช้/เข้าถึงฐานข้อมูลหลัก student_project_management ตามขอบเขตปัจจุบัน ยังไม่ได้ตั้ง DB กลางหรือเปิดเครือข่ายในงานนี้

สำหรับ DB กลาง ผู้ดูแลต้องกำหนด listen_addresses, pg_hba.conf และ firewall ให้เฉพาะเครื่องที่อนุญาต รวมถึงพิจารณาการเข้ารหัสช่องทาง ห้ามให้ Frontend ต่อ PostgreSQL หรือใส่ DB password ลง NEXT_PUBLIC_* ส่วน Frontend/Backend ที่รันในแต่ละเครื่องยังใช้ localhost:3000/8000 ตามแบบที่ยืนยัน การเปิด Backend/Frontend กลางบน LAN/HTTPS ต้องทบทวน Origin/CORS/Cookie แยก ดู [PostgreSQL connection settings](https://www.postgresql.org/docs/18/runtime-config-connection.html) และ [client authentication](https://www.postgresql.org/docs/18/client-authentication.html)

## เตรียมเครื่องสมาชิกทีม

คำสั่งด้านล่างเป็น PowerShell จาก root ของ Repository หลัง clone branch ที่มีงานล่าสุดแล้ว

### 1. Dependencies

ใช้ Python 3.12 ตาม environment ที่ทดสอบ และ PostgreSQL 18.6 ตาม baseline โปรเจกต์ สำหรับ Windows64-bit แนะนำ Node22.x ตั้งแต่22.13.0 ตาม engines ของแพ็กเกจที่ล็อกไว้สำหรับ platform นี้ ปัจจุบันเครื่องเดิมใช้ Node20.10.0 และพบ engine warning ของ eslint-visitor-keys5.0.1 แม้ lint/build ผ่าน จึงไม่ถือว่าเป็น Node รุ่นแนะนำสำหรับเครื่องใหม่ ยังไม่ได้ทดสอบ fresh install บน Node22 ในงานนี้

```powershell
py -3.12 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
Push-Location frontend
npm ci
Pop-Location
```

อย่าส่งต่อ .venv, node_modules หรือ .next ให้ติดตั้งใหม่ตาม requirements/lockfile ของ commit เดียวกัน

### 2. Database baseline — ยังต้องเตรียมแยกก่อนใช้งานจริง

ผู้ดูแลของแต่ละ PostgreSQL instance ต้องเตรียมตามลำดับที่ตรวจรับ:

1. Roles: postgres สำหรับติดตั้ง/บริหาร, project_owner เป็น NOLOGIN และไม่ใช่ superuser, project_app เป็น LOGIN ที่ไม่มีสิทธิ์ elevated หรือสมาชิกของ owner/broad data roles
2. Database student_project_management_v1_test เจ้าของ project_owner และสิทธิ์ CONNECT ที่จำเป็น
3. ติดตั้ง SQL V1 และ RBAC ด้วย project_owner ตามขั้นตอนที่อนุมัติสำหรับ **ฐานข้อมูลว่าง** ไม่ใช้ตัวติดตั้งเริ่มต้นกับ DB ที่มีตารางอยู่แล้ว
4. ติดตั้งส่วนขยาย Auth ตาม [Database README](database/README.md) และ [Installation Report](docs/database/AUTH_INSTALLATION_REPORT.md) ให้ owner/grants ตรงแบบ ไม่มีบัญชีจำลองถาวรจากการติดตั้ง
5. ตรวจชื่อ DB, roles/ownership, functions/triggers และ effective privileges ก่อนทดสอบข้อมูลด้วย transaction/ROLLBACK

ข้อจำกัดที่พบจาก source ปัจจุบัน:

- P06: ติดตั้ง6function repair และ EXECUTE helper1รายการใน test DB ตามอนุมัติแล้ว มี52 V1 functions ตรงsource ตรวจ direct project_app สร้างTeam→leader→Projectผ่าน โดยข้อมูลจำลอง ROLLBACK ดู [V1 Baseline Installation Report](docs/database/V1_BASELINE_INSTALLATION_REPORT.md)
- แก้ Preflight/เครื่องมือติดตั้ง V1 ทั้ง5ตัวให้ใช้ Test_Database ซึ่ง pin test DB และไม่ import backend.database แล้ว ไม่ต้องตั้ง DB_NAME ไป DB หลักเพื่อให้ RBAC Apply ผ่าน Preflight บังคับ read-only ตั้งแต่เริ่ม connection
- .gitattributes บังคับ SQL ใน database/ เป็น LF เพื่อรักษา checksum ข้ามเครื่อง ไม่เปลี่ยน SQL V1/Auth ต้นฉบับ
- ผลหลังติดตั้ง: direct Team8, owner/Team9, Workflow57, boundary/Auth74 และ Auth DB40ผ่าน บน installed baseline โดยไม่ลงแพตช์ซ้ำ ทุกชุดคืนbaseline52functionsหลังROLLBACK ยังไม่ใช่ fresh install ของเครื่องทีม/Concurrency หรือ Team APIที่พัฒนาแล้ว

ถ้าเลือกย้ายฐานข้อมูลด้วย dump/restore ให้ทำแผนแยก ไม่อัปโหลด dump ที่มีข้อมูลบัญชี/hash/session ลง GitHub และต้องเตรียม roles ก่อน restore เพื่อรักษา ownership/grants ดู [PostgreSQL backup/restore](https://www.postgresql.org/docs/18/backup-dump.html) ยังไม่มีการ export/restore ในงานนี้

### 3. Private config

สร้าง backend/.env จาก template **เฉพาะเมื่อยังไม่มีไฟล์**:

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) {
    Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
}
```

กรอกค่าจริงในเครื่องตนเอง ไม่ส่งใน GitHub/แชท:

| ตัวแปร | ใช้กับอะไร |
|---|---|
| AUTH_DB_HOST | host ของ PostgreSQL; ค่าเริ่มต้น localhost สำหรับ DB ในเครื่อง |
| AUTH_DB_PORT | port ของ PostgreSQL; ค่าเริ่มต้น 5432 |
| AUTH_DB_PASSWORD | รหัส PostgreSQL ของ project_app ใน instance นั้น ไม่ใช่รหัสนักศึกษา |

Auth runtime pin DB เป็น student_project_management_v1_test และ role เป็น project_app ในโค้ด ไม่ใช้ postgres/project_owner แทน app Templateครบคือbackend/.env.example ส่วน.env.auth.exampleเป็นruntime-onlysubset ทั้งสองไม่มีรหัสจริงและรหัสแต่ละเครื่องไม่จำเป็นต้องเหมือนกัน

DB tests/installer บางตัวต้องใช้ DB_HOST, DB_PORT, DB_USER และ DB_PASSWORD สำหรับ fixture/deployment เพิ่มใน backend/.env โดยผู้ดูแลตามขั้นตอนที่อนุมัติ ไม่ใช้ admin config แทน AUTH_* เครื่องมือ V1 ปรับให้ ignore DB_NAME แล้ว pin test DB โดยตรง ไม่ต้องเตรียม DB หลักสำหรับงานนี้

Frontend เริ่มต้นเรียก http://localhost:8000 โดยไม่ต้องสร้าง config ถ้าต้องระบุใช้ frontend/.env.example เป็นแบบสำหรับ .env.local และตั้งเฉพาะ NEXT_PUBLIC_API_BASE_URL ห้ามใส่ password/secret ใน Frontend

### 4. เปิดระบบเมื่อ baseline/config พร้อมแล้ว

Terminal แรก จาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal ที่สอง:

```powershell
cd frontend
npm run dev -- --hostname localhost --port 3000
```

เข้า http://localhost:3000 และ Swagger ที่ http://localhost:8000/docs ใช้ host localhost ให้ตรง Origin/Cookie ที่ยืนยัน เซิร์ฟเวอร์ปกติออกแบบให้บันทึกข้อมูลเมื่อสมัคร/Login สำเร็จ; การทดสอบเขียนข้อมูลของทีมยังต้องใช้ชุด rollback-only ตามขอบเขต ไม่ใช้การกดหน้าจอปกติแทน ROLLBACK tests

## การตรวจสอบ

ไม่เชื่อม DB:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tests.Database_Schema_V1_Static_Gate
Push-Location frontend
npm run lint -- --no-cache
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
Pop-Location
```

หลัง baseline/private config พร้อมและอยู่ในขอบเขตทดสอบที่อนุมัติ:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_invitation_api database.tests.test_test_database database.tests.test_advisor_provision -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.team_api_direct_smoke
```

Browser tests ต้องติดตั้ง Microsoft Edge และเว้น ports3000/8001 ให้ชุดทดสอบเปิดเอง จาก frontend ใช้ npm run test:e2e ซึ่งเรียก fixture rollback-only ไม่ใช้ Backend ปกติ ดู [Frontend README](frontend/README.md) สำหรับวิธีใช้/ข้อจำกัด ไม่รันพร้อมกับ normal Frontend3000

ผลจากรอบพัฒนา Auth ก่อนงานจัดไฟล์: Backend65 + Browser5, lint/TypeScript/build และ baseline หลัง ROLLBACK ผ่าน ผลนี้ไม่ใช่ fresh install ของทีม หรือหลักฐานว่า business workflows/Concurrency พร้อมแล้ว

ตรวจ installed Team DB ด้วย [V1_Baseline_Prepare](database/tools/V1_Baseline_Prepare.py): default/--check เป็น read-only ปัจจุบัน PASS ส่วน --test-installed --workflow ใช้ baselineจริงโดยไม่ทำDDLและ ROLLBACK fixtures ทั้งหมด เพิ่ม direct app regression ที่ database/tests/Team_Create_Installed_Regression.py ตัวติดตั้งแยก V1_Baseline_Install default read-only และ --apply ต้องอยู่ในขอบเขตอนุมัติ ไม่ใช้ initial schema installer ลงทับฐานข้อมูลเดิม

รอบ Advisor invitations ล่าสุด: Backend174testsผ่าน (Auth65+Team37+member18+Project21+invitation24+boundary9), Browser42/42 (5+8+8+9+12), lint/TypeScript/build และdirect app boundary smokeผ่าน ทุกfixtureคืนbaseline52functionsและข้อมูลเดิม ไม่เปลี่ยนSQL/grants/.env Browserใช้ownerเตรียมบัญชีชั่วคราวก่อนswitchเป็นeffectiveproject_appทุกrequest ไม่ใช่directLOGINappทั้งsuite อ่านรายงานสำหรับroleboundaryและข้อจำกัด ยังไม่Concurrencyจริง/fresh installเครื่องทีมหรือsuccessful runtime dataCOMMIT

รอบCLIadvisorต่อมา: เพิ่ม17testsและRegressionรวม191ผ่าน พร้อม--check/TTYdryrunจริง ต่อมาผู้ใช้อนุมัติ--applyบันทึกadvisor1บัญชีสำเร็จ Login/Me/inbox/Logoutผ่านdirectproject_appโดยROLLBACKsessionทดสอบ และprovisioning17testsหลังapplyผ่าน ไม่แก้API/Frontendจึงไม่รันBrowser/lint/buildซ้ำ ค่าBrowser42ด้านบนเป็นผลรอบInvitation อ่านคู่มือสำหรับหลักฐานแต่ละรอบ

รอบส่งต่อทีมล่าสุด: รันRegression191/Browser42/lint/TypeScript/buildและinstalledDBworkflow57ผ่านใหม่ พร้อมROLLBACKcleanup ตรวจsecret/configexamples/localimports/เอกสาร/sourceSQLแล้ว ดู [Handoff Verification](docs/team/HANDOFF_VERIFICATION.md) สำหรับขอบเขตจริง โดยเฉพาะfreshinstallบนเครื่องสมาชิกที่ยังNotVerified ยังไม่stage/Commit/Pushในรอบเตรียมนี้

## ก่อน Commit/Push

- เก็บ source, SQL, tests/tools, docs, requirements, package.json/package-lock.json และ config ตัวอย่างที่ไม่มี secrets
- ไม่เพิ่ม .env จริง, virtual environments, dependencies/cache, test artifacts หรือ DB backups
- ตรวจ git status --short และ git diff --cached ก่อน commit; สคริปต์ DB/tools และไฟล์ Auth หลายไฟล์เดิมเป็น untracked ต้องเลือกเพิ่มให้ครบ
- .gitignore ไม่ลบรหัสที่เคย commit ไปแล้ว หากพบการเผยแพร่รหัสในอดีตให้จัดการแยก งานนี้ไม่ได้ commit/push หรือแก้ประวัติ Git
