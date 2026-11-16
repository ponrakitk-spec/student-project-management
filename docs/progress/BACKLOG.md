# Backlog — Student Project Management System

**พักและส่งต่อ 2026-11-16:** ผู้ใช้ให้หยุดรอข้อมูล Project Supabase และอนุมัติ Commit/Push งานวันนี้บน `feature/team-integration` ตาม [บันทึกชุดส่งต่อ](../team/INTEGRATION_RELEASE_2026-11-16.md) ผล Backendล่าสุด603/direct app smokeผ่าน ผลBrowser130/lint/TypeScript/buildอ้างรอบTaskก่อนเพิ่มbackend-only Supabase profile ไม่มี cloud install/data migration หรือการปิดUATจากการเผยแพร่

**Supabase preparation 2026-11-16:** ผู้ใช้เลือกใช้เป็นฐานข้อมูลกลางของทีมโดยคง Login เดิม เตรียม explicit target/Project-ref/TLS/limited-role guards, namespace `spms_auth`, deployment drafts และ read-only preflight ตาม [คู่มือ](../team/SUPABASE_SETUP.md)/[รายงาน](SUPABASE_PREPARATION_REPORT.md) ยังไม่ยืนยัน Project/ติดตั้ง/ทดสอบ cloud/ย้ายข้อมูลหรือเปลี่ยน `.env` จริง ผล local ไม่ใช่ Supabase readiness และไม่เพิ่ม Done จากการเตรียมนี้ ไม่ใช้ Supabase Auth/Storage/Data API

**Task/Assignee/History 2026-11-16:** ผู้ใช้ยืนยัน [Contract](../api/TASKS_CONTRACT.md) ครบ workflow สำหรับทีม และอนุมัติจบรอบทดลองก่อนทดสอบแล้ว เพิ่ม Task API10operations/UI พร้อม UOW10รายการตาม [รายงาน](TASK_IMPLEMENTATION_REPORT.md) ผล Backend578/Browser130/focused8/direct app workflow/lint/TypeScript/build ผ่าน พร้อม ROLLBACK/fixture connections0 เปิดทางทำ Task→Milestone completed→Evaluation ผ่าน API/UIจริง ไม่แก้Schema/RBACหรือเพิ่มข้อมูลถาวร P13/P17/P19ยัง In Progress เพราะ UAT/fresh setup/concurrency/บทบาทอื่นที่ยังไม่ยืนยัน; Done6/20=30%คงเดิม

**รับช่วงงานเพื่อนต่อ 2026-11-16:** เจ้าของสั่งทำส่วนที่เพื่อนยังไม่ทำ และยืนยัน Milestone สำหรับทีมแล้ว เพิ่ม Submission UI สองบทบาท + Milestone API5operations/UI ตาม [รายงานต่อเนื่อง](PEER_WORK_CONTINUATION_REPORT.md) และ [Milestone Contract](../api/MILESTONES_CONTRACT.md) ผล Full Backend553/Browser122/focused13/direct app CRUD/lint/TypeScript/build ผ่าน พร้อม ROLLBACK/baseline/fixture connections0 Task API/หน้าบทบาทอื่น/Supabase ยังนอก scope; P11/P13/P17/P19 ยัง In Progress และ Done6/20=30% คงเดิม

**ล่าสุด Integration 2026-11-16:** ผู้ใช้ยืนยันรวม Backend Submission จากเพื่อน `31c4fcb` เข้าสู่ local `feature/team-integration` ฐาน `6040702` ตาม [รายงาน integration](SUBMISSION_INTEGRATION_REPORT.md) มี 7 operations/6 paths และ 8 UOW overrides; Full Backend545/Browser109/ROLLBACK cleanup ผ่าน คง DB/role/Schema/RBAC เดิม ไม่รวม Supabase runtime หรือ Submission UI/Milestone API/UI ของเพื่อน P11/P17/P19 ยัง In Progress และ Done6/20=30% คงเดิม; จำนวน tests ไม่ใช่เปอร์เซ็นต์ความสำเร็จของระบบ

**ล่าสุด เตรียมคู่มือ/UAT 2026-11-15:** เพิ่ม [คู่มือผู้ใช้](../user/USER_GUIDE.md), [Demo](../user/DEMO_SCRIPT.md) และ [Manual UAT20กรณี](../uat/MANUAL_UAT.md) ที่แยกexpected/ผลจริง/Not Readyพร้อมวิธีทดลองเขียนผ่าน8001/ROLLBACK ทวนdefault directapp serverด้วย9APIrequestsและteardownคืนmetadata-ACL-rowcounts/fixtureconn0ผ่าน ไม่ใช่ผลManual UATหรือfreshmachineinstall P20เปลี่ยนNot Started→In Progress; Done6/In Progress14/Not Started0/Blocked0 คง6/20=30% ไม่มีsource/Schema/RBAC/peer/seedถาวร/Gitเปลี่ยน

**ล่าสุด Workspace overview 2026-11-15:** ผู้ใช้ยืนยัน [Contract](../api/WORKSPACE_OVERVIEW_CONTRACT.md) เพิ่ม `/workspace` และลิงก์จากบัญชี studentอ่านทีม/Projectจริง advisor/coordinatorมีทางเข้างานตามบทบาท [Browserใหม่9/Full109/lint/TypeScript/buildผ่าน](WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) พร้อมROLLBACK/fixtureconn0 ไม่มีBackend/Schema/RBAC/peer/seedเปลี่ยน ไม่ใช่ST-01 metricsเต็มหรือการปิดU03/P15 Done6/20=30%คงเดิม Remoteเพื่อนตรวจสดยัง31c4fcb ไม่รวมงานเพื่อน/Commit/Push

**ล่าสุด Evaluation HTTP concurrency 2026-11-15:** [EH01–EH10ผ่าน10/10](EVALUATION_HTTP_CONCURRENCY_REPORT.md) บนseed42เดิม: mixedHTTP/repository5และdualHTTP5 realTCP/Login/Session/CSRF/API/3PID/overlap/DBwait/A-B ROLLBACKคืน public values/Auth counts/metadata Safeguardsใหม่19/รวม79ผ่าน ไม่มีcredential/seedถาวร/production/SQL/RBAC/peer/Gitเปลี่ยน ยังไม่sameactordualHTTP/physicalappHTTPworkers/winner-COMMIT/TX-UATครบ P18คง In Progress Done6/20=30%

**ล่าสุด Evaluation concurrencyหลังอนุมัติ 2026-11-15:** ผู้ใช้ตอบ “อนุมัติบันทึก 42 แถวและรัน 8 กรณี” [ติดตั้งและ EC01–EC08ผ่าน8/8](EVALUATION_CONCURRENCY_REPORT.md) directapp/3PID/observed lock wait/A-B ROLLBACKคืนbaselineที่มีseed42แถว ไม่มี Loginใหม่/Schema-RBAC-peer-Gitเปลี่ยน FullBackend508/Browser100หลังติดตั้งผ่านพร้อมROLLBACK/fixtureconn0 ไม่ใช่ HTTP/winner-COMMIT/TXครบ P18คง In Progress Done6/20=30%

**รอบเตรียมก่อนอนุมัติ Evaluation multi-session 2026-11-15:** เพิ่ม [runner/fixture42แถว/installer/safeguards](EVALUATION_CONCURRENCY_PREPARATION.md) ชุดใหม่39/targeted94 testsผ่าน DRY RUN isolated16/ordered8และinstaller exclusionบนgraphจริงคืน baseline ไม่มี COMMIT/manifest export ในขั้นเตรียม; ผลอนุมัติ/ติดตั้ง/หลายsessionอยู่ด้านบน ไม่แก้ runtime/SQL/RBAC/peer/Git P18คง In Progress และ Done6/20=30%

**ล่าสุด Evaluation rehearsal 2026-11-15:** เพิ่ม [ชุดซ้อม Concurrency8สถานการณ์](EVALUATION_CONCURRENCY_REHEARSAL.md) DRY RUN บน test DB ผ่าน isolated16/ordered8 พร้อม ROLLBACK/metadata-ACL-full public valuesคืน baseline Safeguardsใหม่13/targeted regression64ผ่าน Base fixture38แถวและข้อมูลระหว่างกรณีเป็นชั่วคราวทั้งหมด ไม่มี COMMIT/manifest export/Schema-RBAC-peer changes ยังไม่ multi-session/lock wait/HTTP/winner-COMMIT; P18คง In Progress และ Done6/20=30% ไม่เพิ่มจากจำนวน tests

**ล่าสุด Evaluation 2026-11-15:** ผู้ใช้ยืนยันครบ API/UI และสิทธิ์ดูผลตาม [Contract](../api/EVALUATIONS_CONTRACT.md) แล้ว พัฒนา 5 operations / 4 API paths และ 4 UI routes; กรรมการเห็นของตน รวม/เฉลี่ยเปิดเมื่อครบ และ Coordinator เห็นรายบุคคลหลังครบเท่านั้น [Backend456/Browser100/lint/TypeScript/buildผ่าน](EVALUATIONS_IMPLEMENTATION_REPORT.md) รวม Evaluation API14/validator12/Browser10 พร้อม ROLLBACK/fixture connections0 ไม่แก้ SQL/RBAC/งานเพื่อนหรือเพิ่มข้อมูลถาวร P14 Done เฉพาะ Contract ที่ยืนยัน อัตราปิด checklist เพิ่มเป็น6/20=30%; peer integration/P17, Evaluation concurrency/P18 และ UAT/P19 ยังเปิดอยู่

**ล่าสุด 2026-11-15 — สองHTTPclients:** [DH01–DH09ผ่าน9/9](DUAL_HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) Login/CSRF/TCPจริงทั้งสองฝั่งคนละactor พักAก่อนresponseแล้วตรวจทั้งสองrequestpending+pg_blocking_pids/3PIDก่อนปล่อยA-BROLLBACK Offline60/HTTPชุดเดิม14รันใหม่ผ่าน ไม่มีข้อมูลถาวร/production/SQL/grant/peer/Gitเปลี่ยน ยังไม่sameactor/winner-COMMIT/physicalappworkers/UAT คงDone5/20

**ต่อเนื่อง 2026-11-15 — HTTP Concurrency:** เพิ่ม[LiveTCPHTTP14กรณี](HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) Aใช้repository/Bใช้Login-Session-CSRF/APIจริงบนloopbackพอร์ตเฉพาะ; ผ่าน14/14พร้อมpg_blocking_pids/3PID/A-BROLLBACK/Authcounts-metadata-fullpublicvaluesคืนbaseline HRC06คาดหวัง500/55P03 Offline88ผ่าน ไม่สร้างfixtureหรือLoginถาวรเพิ่ม ไม่แก้production/SQL/RBAC/peer/Git ยังไม่สองHTTPclients/winner-COMMIT/physicalLOGINappของB/UAT คงDone5/20

**ล่าสุด 2026-11-15 — Vote/Committee Concurrencyหลังอนุมัติ:** [ติดตั้งfixture29แถวและVC01–VC08ผ่าน8/8](TOPIC_VOTE_CONCURRENCY_REPORT.md) directLOGINapp/3PID/รอlockจริง/A-BROLLBACKคืนmetadata-ACL-fullpublicvalues Repeatapplyไม่เพิ่มแถวและfixtureTeam/Projectเดิม10แถวยังผ่าน Offline71/FullBackend386/Browser90หลังติดตั้งผ่าน ไม่มีruntime/SQL/grant/peer/Gitเปลี่ยน Seed29แถวคงอยู่ตามอนุมัติ ไม่ใช่winner-COMMIT/HTTP/TXครบ คงDone5/20

**ผลรอบTopicimplementation 2026-11-15:** ผู้ใช้ยืนยัน [Topic votes Contract](../api/TOPIC_VOTES_CONTRACT.md) ครบVote/รายชื่อ/ผลตามสิทธิ์ และกรรมการเห็นVoteตนเอง+ผลรวมเมื่อครบ พัฒนา7operations/6routesพร้อมacceptedAdvisorlistแล้ว [Backend349/Browser90/lint/TypeScript/buildผ่าน](TOPIC_VOTES_IMPLEMENTATION_REPORT.md) พร้อมROLLBACK/baseline52functions/ACL ผลConcurrencypartialรอบถัดมาอยู่ด้านบน ไม่เปลี่ยนSchema/RBACหรือSubmission/Milestoneเพื่อน P12ยังInProgressเพราะTX02/UATและการตรวจรับระบบรวมยังไม่ครบ ไม่เดาเปอร์เซ็นต์จากจำนวนtests

ตรวจล่าสุด: 2026-11-14 · Branch งานต่อ `feature/project-continuation` จาก `679913a` ซึ่งส่งขึ้น `origin/feature/database-schema` แล้ว · ตรวจงานเพื่อน `origin/feature/database-schema2` ที่ `31c4fcb` โดยยังไม่รวม runtime

**ผลตรวจรอบใหม่:** [รายงาน 2026-11-14](2026-11-14_CONTINUATION_REVIEW.md) และ [บันทึกรับช่วงงานเพื่อน](../team/SCHEMA2_INTEGRATION_HANDOFF.md) พบ Submission Backend เพิ่มใน branch เพื่อน แต่ยังไม่ผ่าน integration/UI ครบและมี fixture/connection policy ที่ต้องสะสาง ตาราง/ผลทดสอบเดิมด้านล่างเป็นหลักฐานสะสม ณ 2026-11-07 ไม่ใช่การรัน DB/Browser ใหม่วันนี้ คง Done5/20 ไม่มีงานปิดเพิ่ม

**แบ่งงานยืนยันแล้ว:** เพื่อนดูแล Submission และ Milestone และเตรียม Supabase สำหรับอนาคต เราเว้น source ทั้งสอง feature/งาน Supabase ไว้ [Project update](../api/PROJECT_UPDATE_CONTRACT.md) ผู้ใช้อนุมัติแล้วและ implemented/tested ผ่าน Backend202/Browser49/direct app/lint/TypeScript/build พร้อม ROLLBACK ตาม [รายงาน](PROJECT_UPDATE_IMPLEMENTATION_REPORT.md) ไม่เปลี่ยนนโยบาย DB ปัจจุบัน

**ผลรอบ Team update ล่าสุด:** ผู้ใช้อนุมัติพัฒนาตามแนวทางแล้ว เพิ่ม [PATCH/ฟอร์มแก้ชื่อและคำอธิบายทีม](../api/TEAM_UPDATE_CONTRACT.md) ผ่าน Backend214/Browser56/direct app/lint/TypeScript/build พร้อม ROLLBACK ตาม [รายงาน](TEAM_UPDATE_IMPLEMENTATION_REPORT.md) ไม่แก้งานเพื่อนหรือ SQL/grants; ยังไม่ Commit/Push

**ผลรอบโอนหัวหน้าล่าสุด:** ผู้ใช้ยืนยัน “เริ่มโอนหัวหน้าก่อนตามร่าง” พัฒนา [โอนหัวหน้า](../api/TEAM_LEADER_TRANSFER_CONTRACT.md) แล้วผ่านBackend227/Browser63/directapp/lint/TypeScript/buildพร้อมROLLBACKตาม [รายงาน](TEAM_LEADER_TRANSFER_IMPLEMENTATION_REPORT.md) ยังไม่เพิ่มออก/ถอดสมาชิก ไม่เปลี่ยนSQL/grantsและไม่Commit/Push

**รอบออก/ถอดสมาชิก:** ผู้ใช้ยืนยัน “ทำทั้งออกและถอดตามร่าง” [Exit Contract](../api/TEAM_MEMBERSHIP_EXIT_CONTRACT.md) implemented/verifiedแล้ว Backend242/Exit15/directappผ่าน และหลังพอร์ตmanualว่าง productionbuild/Browser73รวมExit10/lint/TypeScriptผ่านพร้อมROLLBACK ตาม [รายงาน](TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md) ยังไม่ปิดP09/P13ทั้งแถว เจ้าของแจ้งmanualtransferผ่าน บันทึกแยกเป็นuser-reportedresultในรายงานtransfer

**รอบเตรียม Concurrency:** ผู้ใช้เลือกเตรียมชุดทดสอบ Team/Project เพิ่ม [runner/แผน RC01–RC06](TEAM_PROJECT_CONCURRENCY_PLAN.md) แบบ winner-ROLLBACK พร้อม manifest guard และ Offline safeguards25/รวมOffline67ผ่าน ยังไม่ต่อ DB/สร้าง shared fixture/COMMIT หรือเปลี่ยน production source ผล PostgreSQL Concurrency ยัง Not Run และ P18 ยัง Blocked

**รอบ fixture DRY RUN:** เพิ่ม [เครื่องมือและรายงาน rehearsal](TEAM_PROJECT_CONCURRENCY_FIXTURE_REHEARSAL.md) สร้าง fixture10แถวในtest DBและทวน12actionsแบบ sequential ผ่าน พร้อมROLLBACK/metadata/ACL/rowsคืนbaseline Offlineใหม่12/รวม79ผ่าน ไม่สร้าง shared fixtureถาวร ไม่ใช่ผลmulti-sessionหรือ55P03; P18ยังBlockedและไม่แก้งานเพื่อน

**รอบ Concurrency จริงหลังอนุมัติ:** ผู้ใช้ตอบ “อนุญาต” ให้บันทึกseed10แถวในtest DB ติดตั้งและตรวจข้อมูลเดิม/Schema/ACLไม่เปลี่ยนแล้ว [RC01–RC06ผ่าน6/6](TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md) ด้วยdirectapp/3connections/รอlockจริง/ROLLBACKทุกcase รวม55P03ตามคาด Backend291ผ่าน และfinaltool safeguards50ผ่าน P18เปลี่ยนBlocked→InProgress แต่ยังไม่ครบTX/winner-COMMIT/HTTP ไม่มีDoneเพิ่มหรือGitCommit/Push

**รอบ Transaction ต่อมา:** เพิ่ม [RC07–RC08 Project lock/injected deadlock](TEAM_PROJECT_TRANSACTION_FAILURES_REPORT.md) ผ่าน2/2บนfixtureเดิมพร้อมdirectapp/3PID/40P01/ROLLBACK ข้อมูลกลับbaseline Offlineใหม่14/รวม64ผ่าน ผลสะสม8casesจากสองรอบ ยังไม่40001/retry/HTTP/winner-COMMIT/TXครบ ไม่แก้productionหรือseedเพิ่ม

**รอบ Coordinator/Committee ล่าสุด:** ผู้ใช้ยืนยัน [Contractครบดูรายการ/เพิ่ม/เปลี่ยน/ถอด](../api/COMMITTEE_ASSIGNMENTS_CONTRACT.md) และเลือกกรอกบัญชีผ่านCLIเอง พัฒนาAPI/UI/CLIแล้ว [Backend332/Browser81รวมCommittee8/lint/TypeScript/buildผ่าน](COMMITTEE_ASSIGNMENTS_IMPLEMENTATION_REPORT.md) พร้อมROLLBACK ไม่สร้างcoordinatorถาวร ไม่ทำVote/EvaluationAPIหรือTeam/AdvisorrosterUI ไม่แก้Submission/Milestoneของเพื่อนและไม่Commit/Push P12ยังInProgressเพราะยังไม่ครบVote

ฐานอ้างอิง: [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Review Report](../database/Database_Schema_V1_A02_A05_Review_Report.md) และแผน 4 สัปดาห์ใน [handoff](../codex_project_handoff/PROJECT_HANDOFF_CODEX.md)

นี่คือรายการติดตามจากการ audit โค้ดและหลักฐานในบทสนทนา ไม่ใช่การอนุมัติให้ทำทุกแถว ผู้รับผิดชอบ/กำหนดส่งยังไม่ระบุ; ลำดับถัดไปเป็นข้อเสนอ ต้องรักษาขอบเขตคำสั่งผู้ใช้

**ส่งต่อให้ทีม:** [เริ่มต้น/ตั้งค่า](../team/START_HERE.md), [ทีมS: Submission](../team/SUBMISSION_WORK_PACKAGE.md), [ทีมM: Milestone](../team/MILESTONE_WORK_PACKAGE.md) และ [Git/ผลตรวจ](../team/HANDOFF_VERIFICATION.md) ชื่อทีมS/Mเป็นworkpackages ไม่ใช่การระบุเจ้าของงานบุคคลหรืออนุมัติHTTPContractที่ยังเปิดอยู่

## ความหมายสถานะและหลักฐาน

- **Done**: ผ่านเกณฑ์เฉพาะงานย่อยนั้น ไม่ขยายผลเป็นทั้งระบบ
- **In Progress**: มี implementation/artifact บางส่วน แต่ยังไม่ครบเกณฑ์ ไม่ได้หมายถึงมีผู้พัฒนากำลังทำขณะนี้
- **Not Started**: ไม่พบ implementation ของงานนั้นใน Workspace ที่ตรวจ
- **Blocked**: มีเงื่อนไขหรือสิทธิ์อนุมัติที่ต้องผ่านก่อนดำเนินงานส่วนที่ติด
- **Not Verified**: ป้ายกำกับหลักฐานที่ยังตรวจไม่ได้ ใช้คู่กับสถานะ; ไม่เดาผลงานที่อาจอยู่นอก Workspace
- **DB-only**: เรียก SQL ผ่านสคริปต์ ไม่ใช่ผ่าน FastAPI/Frontend

## รายการหลัก 20 งาน — คง ID จากรายงาน audit

| ID | งาน / ข้อกำหนด | สถานะ | หลักฐานปัจจุบัน | เงื่อนไขปิดงาน / งานถัดไป |
|---|---|---|---|---|
| P01 | Frontend starter | Done | [page.tsx](../../frontend/src/app/page.tsx), package/config; ล่าสุด lint/TypeScript/production build ผ่าน | Done เฉพาะ scaffold/build ไม่ใช่ business screens เสร็จ |
| P02 | Backend starter | Done | [main.py](../../backend/main.py); GET / ตอบ 200 ใน ASGI smoke แบบไม่ต่อ DB | Done เฉพาะ skeleton ไม่รวม business API |
| P03 | Requirements/ERD/UI specification สอดคล้อง V1 | In Progress | มี Data Dictionary/ERD, reference ล่าสุด และต้นทาง UI; แก้ความคลาดเคลื่อน C-01/R-01 ในเอกสารอ้างอิงแล้ว | ยืนยัน U01–U09 ที่จำเป็น, acceptance criteria และ design artifacts ที่ยังขาด; ไม่ถือว่ามี Figma แล้ว |
| P04 | SQL Schema/RBAC ตาม V1 | In Progress | [Schema](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql), [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql); มี tests บางเส้นทาง | ครบ requirement-to-test mapping และพิสูจน์ integration/security/concurrency ก่อนปิด |
| P05 | ชุด single-session Workflow Regression 57 กรณี | Done | ล่าสุดรัน57/57 ผ่านใน V1_Baseline_Prepare --test-installed --workflow บน persistent baseline52functions ไม่มี temporary patch พร้อม forced deferred/ROLLBACK | Done เฉพาะชุดที่รัน ไม่ใช่ concurrency/ทุกกฎของ V1 |
| P06 | test DB baseline ที่มีแพตช์ V1 ถาวร | Done | [ติดตั้งตามอนุมัติ](../database/V1_BASELINE_INSTALLATION_REPORT.md) COMMITเฉพาะ6functions+EXECUTE helper1รายการ มี52functionsตรงsource; direct app Team8/owner-Team9/Workflow57/Auth74+40ผ่าน และคืนbaselineหลังROLLBACK; applyซ้ำตรวจรับไม่เขียนทับ | Doneเฉพาะbaseline repair/เส้นทางDBนี้ ไม่รวมfresh installของเครื่องทีม/Concurrency/API |
| P07 | Backend DB request integration | In Progress | Auth→Team→member→Project create/currentใช้SQLจริงผ่านdirect project_app ASGI/Browser rollback fixture ไม่มีadmin fallback บังคับTeam deferred checksและจบUOWก่อนตอบsuccess | businessAPIอื่น/authorizationตามV1ยังไม่ครบ และsuccessful runtime data COMMITยังไม่ทดสอบ |
| P08 | Authentication และ API authorization / G-12 | In Progress | Auth4endpoints/Frontend, advisorCLI17tests/บัญชีadvisorตามอนุมัติเดิม และ [coordinatorCLI11tests](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) พร้อมdefaultDRY RUN/owner guard/hiddenpassword ผู้ใช้เลือกกรอกcoordinatorเอง [regression332ผ่าน](COMMITTEE_ASSIGNMENTS_IMPLEMENTATION_REPORT.md) | บัญชีcoordinatorถาวรผู้ใช้เตรียมเอง; existing-account/recovery/rate-limitและG-12ระบบเต็มยังไม่ครบ ไม่ปิดทั้งแถวจากprovisioning |
| P09 | Team/member/Project / C-01,C-02,C-07,R-01 | In Progress | ล่าสุดExit15/Backend242/directappและBrowser73รวมExit10/buildผ่าน มีleave/removeAPI+UIตาม[Contract](../api/TEAM_MEMBERSHIP_EXIT_CONTRACT.md) ใช้SQL/สิทธิ์เดิมและROLLBACK พร้อมmetadata/transferเดิม | Concurrencyจริงและการตรวจรับระบบรวมยังไม่ครบ ไม่ปิดทั้งแถวจากsingle-sessionAPI/UI |
| P10 | Advisor invitation | Done | [Contract/API/UIครบworkflow](../api/ADVISOR_INVITATIONS_CONTRACT.md): invitation24tests/Browser12ผ่านจริง รวมactor/role/transfer/exit/privacy/finalimmutable/rollback ตาม [รายงาน](ADVISOR_INVITATIONS_IMPLEMENTATION_REPORT.md) | Doneเฉพาะขอบเขตที่ยืนยัน ไม่รวมadmin provisioning(P08)/multi-session(P18)/ระบบsecurity-UAT |
| P11 | Submission/file/review/revision | In Progress | [รับ Backend เพื่อนและพัฒนา UI ต่อ](PEER_WORK_CONTINUATION_REPORT.md): upload/history/eligibility/detail/download/review/revision มี API/UI จริงและ Browser7กรณีใหม่ผ่าน; file validation อยู่ Backend | ยังไม่ Manual UAT/fresh setup/Browser positive PPTX และ parser/security ทุก boundary ไม่ถือว่าผ่านทุก case จาก basic workflow |
| P12 | Committee appointment/vote | In Progress | [API/UI/roster/resultsครบContract](TOPIC_VOTES_IMPLEMENTATION_REPORT.md) และ[VC8ผ่านจริง](TOPIC_VOTE_CONCURRENCY_REPORT.md) Vote-roster/รอบใหม่ชนreader/directapp/3PID/winner-ROLLBACK คืนbaselineที่มีseed29แถว | ยังไม่winner-COMMIT/HTTP/peerSubmissionAPIพร้อมVote/UATบัญชีจริงครบworkflow ไม่ปิดทั้งแถวจากcoverageบางส่วนของTX02 |
| P13 | Milestone/Task/Assignee/history / D-01,C-02 | In Progress | [Milestone+Task+Assignee/history สำหรับทีม](TASK_IMPLEMENTATION_REPORT.md) มี API/UI และตรวจ D-01/FK/derived status/C-02/first-score lock/exit/cascade ด้วย HTTP+DB และ Browserจริงแล้ว | ยังไม่ Manual UAT/fresh setup/Task concurrencyชุดใหม่ และหน้าอ่านบทบาทอื่นที่ยังไม่ยืนยัน; completed0assigneesหลังexitยังreopenไม่ได้ตามกฎเดิม |
| P14 | Evaluation และการเปิดเผยผล | Done | [API/UI ครบ Contract ที่ยืนยัน](EVALUATIONS_IMPLEMENTATION_REPORT.md); API14/validator12/Browser10 รวม Backend456/Browser100 ผ่าน ตรวจ score/immutable/first-score lock/รวม-เฉลี่ย/สิทธิ์ก่อนและหลังครบ/ROLLBACK | Done เฉพาะ API/UI/สิทธิ์ที่ยืนยันและทดสอบ prerequisite ด้วย controlled SQL; ไม่รวม Submission/Milestone API ของเพื่อน(P17), Evaluation concurrency(P18) หรือ UAT ระบบรวม(P19) |
| P15 | หน้าจอ Student/Leader ST-01–ST-09 | In Progress | ST-02/ST-04/ST-06และบางส่วนST-03/ST-05เดิม เพิ่ม [Workspace overview](WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) ตามContractใหม่พร้อมDesktop/Mobile/Browser9รวม109ผ่าน | Workspaceเป็นsummary/navigationที่ยืนยัน ไม่ใช่ST-01 metrics/Timeline/Contributionเต็ม ไม่นับเพิ่มเป็นอีก1ใน9หน้าหรือถือว่าผ่านACทุกหน้า |
| P16 | Business API Contract | In Progress | Auth/Team/Project/Invitations/Committee/Vote/Evaluation, Submission/Milestone และ [Task/Assignee/historyสำหรับทีม](../api/TASKS_CONTRACT.md) ยืนยันและ implemented ตามรายงานแต่ละรอบแล้ว | หน้าอ่าน Milestone/Task ของบทบาทอื่น, dashboard metrics/contribution และธุรกิจอื่นยังต้องยืนยันก่อนเพิ่ม |
| P17 | Frontend→Backend→DB integration | In Progress | [Task Browser flow](TASK_IMPLEMENTATION_REPORT.md) สร้างProjectใหม่→Submission/review→appointment/vote→Task UI assign/complete→Evaluation UI ผ่าน API/UIจริง ไม่ใช้ SQL ทำphaseของProjectกรณีนี้; UOW10รายการ | ยังไม่ Manual UAT/fresh setup/ทุกขั้นผ่าน UIล้วน (บางขั้นเตรียมผ่าน API) หรือทุก HTTP request เป็น physical LOGIN app ไม่ปิดแถวจาก automated happy path อย่างเดียว |
| P18 | Concurrency / TX-01–TX-06 | In Progress | [RC8+VC8เดิม](TOPIC_VOTE_CONCURRENCY_REPORT.md), HTTP14/[DH9](DUAL_HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md), [EC8](EVALUATION_CONCURRENCY_REPORT.md) และ [EH10จริง](EVALUATION_HTTP_CONCURRENCY_REPORT.md) mixed5/dualHTTP5/realLogin/3PID/overlap/DBwait/A-B ROLLBACKคืนbaseline Safeguards79ผ่าน ไม่มีseedใหม่ | ยังไม่ winner-COMMIT/sameactordualHTTP/physicalLOGINappของHTTPworkers/productionconnectionfactory/40001-retry/Taskทุก ordering/TXครบ ไม่ขยายผล winner-ROLLBACK เป็น loserหลังCOMMIT |
| P19 | API security/System/UAT | In Progress | Auth/Team/Project/Submission/Milestone และ Vote/score มี authorization/session/CSRF/Origin/atomic/no-store/privacy tests ตามรายงาน ส่วน direct app แยกพิสูจน์ขอบเขตเฉพาะ ไม่ใช่ทุก request | ยังไม่ SEC-07/08 ครบ, rate limiting, parser security ทุก boundary, fresh setup และ UAT ระบบเต็ม ไม่ใช้จำนวน tests แทนการตรวจรับ |
| P20 | User manual/Demo ส่งมอบ | In Progress | [คู่มือผู้ใช้](../user/USER_GUIDE.md)/[Demo](../user/DEMO_SCRIPT.md)/[Manual UAT24กรณี](../uat/MANUAL_UAT.md) เพิ่ม UA23/24 สำหรับ Task/history และ flow ถึง Evaluation มีโหมด8001/ROLLBACK แต่ยังไม่มี Manual UATผลจริง | ผู้ใช้/ผู้รับงานต้องทดลองและบันทึกผล ไม่ถือว่าการมีเอกสารหรือ automated tests เท่ากับ Demo/UAT ผ่าน |

## สิ่งที่ทำในรอบจัดโฟลเดอร์ (ไม่นำมาเพิ่มตัวหาร 20 งาน)

- ย้าย SQL 2, Python scripts 8 และเอกสาร DB 2 ตาม [ผัง](../../database/README.md)
- ปรับ path/import และคำสั่งเรียกใช้ โดยคงเนื้อหา SQL และ logic ธุรกิจเดิม
- เพิ่ม reference/backlog/template และปรับ handoff ให้ชี้กฎล่าสุด; ต้นทาง sources เก็บเดิม
- ไม่เปลี่ยน Backend/Frontend, ไม่อ่านค่า secrets, ไม่เชื่อมต่อ DB, ไม่ Commit/Push

### ผลตรวจหลังย้ายไฟล์ วันที่ 2026-11-06

| รายการ | ผล / ขอบเขต |
|---|---|
| Python syntax | PASS ทั้ง 8 สคริปต์ |
| Import/path | PASS 16 กรณี: 8 สคริปต์ × module จาก root / direct path จาก frontend; ตรวจแบบไม่เรียก main ของ DB scripts และแทน backend connection module ด้วย stub เพื่อไม่อ่าน .env |
| Static Gate | PASS จาก `python -B -m database.tests.Database_Schema_V1_Static_Gate`; ไม่เชื่อม DB |
| SQL integrity / installer checksum | SQL ทั้ง 2 ไฟล์ byte-for-byte เหมือนก่อนย้าย; SHA256 ของ Schema ยังตรง installer |
| Logic ของ Python | เปรียบเทียบ AST ของ functions/classes ทั้ง 8 ไฟล์: เหมือนเดิม ยกเว้นข้อความชี้ตำแหน่ง SQL เมื่อหาไฟล์ไม่พบใน Static Gate |
| เอกสาร | ลิงก์ภายใน 61 จุด resolve ได้; 20 Task IDs ไม่ซ้ำและจำนวนสถานะตรงสูตร |
| ไฟล์นอกขอบเขต | checksum ของ Backend/Frontend และ sources เดิม 27 ไฟล์ไม่เปลี่ยน; ไม่อ่านค่า .env |
| PostgreSQL regression หลังย้าย | **Not Run** ในรอบนี้; ผล 57/57 ด้านบนเป็นผลก่อนย้าย ไม่ใช่การรันซ้ำ |

## วิธีคำนวณความคืบหน้า

คงฐาน20งานจากauditเพื่อเปรียบเทียบข้ามรอบ: **Done6, In Progress14, Not Started0, Blocked0** P20เริ่มมีคู่มือ/Demo/UATplanจึงเป็นIn Progress แต่ยังไม่มีผู้ใช้ตรวจรับ ไม่มีDoneเพิ่ม เกณฑ์ระบบรวม/peer integration/Concurrency/UAT ยังคงอยู่ใน P17–P20

`Done / Total × 100 = 6 / 20 × 100 = 30%`

ให้น้ำหนักเท่ากัน นับเฉพาะ Done ไม่ให้คะแนน50%แก่งานที่ยังไม่จบ ตัวเลขเป็นอัตราปิด checklist ไม่ใช่ effort/time หรือ coverage ทั้งระบบ P10 ปิดจาก invitation API/UI ครบ และ P14 ปิดจาก Evaluation API/UI/สิทธิ์ที่ยืนยัน พร้อมผลทดสอบคะแนนแรก/immutable/รวม-เฉลี่ย การปิด P14 เพิ่ม25%→30% ไม่ได้ปิด Auth/งานทีมทั้งหมด/การเชื่อม peer API/Concurrency/UAT ประวัติด้านล่างเป็นผล ณ แต่ละรอบ

อัปเดตรอบ API Contract วันที่ 2026-11-06: P16 เปลี่ยน Not Started → In Progress; ตัวหารคง 20 ไม่มีงาน Done เพิ่ม ผู้ใช้ยืนยันสร้างทีมพร้อมผู้สร้างเป็นหัวหน้าแล้วเพิ่มสมาชิกภายหลัง และไม่มี SSO ที่แอปใช้ได้ ข้อเสนอ Firebase Email/Password ยังรอตัดสินใจ ไม่ใช่ Auth ที่ implement แล้ว รอบนี้แก้เฉพาะเอกสาร ไม่รัน DB/API tests

อัปเดตขอบเขต Auth วันที่ 2026-11-06: ผู้ใช้ยืนยันว่าเป็นโปรเจกต์ส่งอาจารย์และทดสอบภายในทีม ใช้อีเมลจำลองที่มี `@` และตั้งรหัสผ่านเองได้ ไม่ต้องมีกล่องอีเมลจริง เพิ่มข้อเสนอ Firebase Authentication Emulator ใน Contract; ยังรอยืนยันการตรวจรูปแบบอีเมล ความยาวรหัสผ่าน และวิธีจัดเตรียม/ผูกบัญชี ไม่ได้ติดตั้งหรือ implement Auth และยังไม่ได้รันการทดสอบ Login/DB สถานะ P08 กับเปอร์เซ็นต์ยังคงเดิม

อัปเดตล่าสุด — validation วันที่ 2026-11-06: ผู้ใช้ยืนยันตรวจรูปแบบอีเมล ไม่จำกัด Gmail และรหัสผ่าน ≥8 ตัว มีตัวพิมพ์ใหญ่ ≥1/ตัวเลข ≥1 เพิ่ม helper พร้อม unit tests PASS 17 tests และ dependencies email-validator/dnspython (`pip check` ผ่าน) โดยไม่เรียก DB/อ่าน .env ไม่ได้เชื่อม helper เข้ากับ endpoint หรือสร้างบัญชี P08 เปลี่ยน Not Started → In Progress; ไม่มีงาน Done เพิ่ม จึงยัง 15% วิธี Auth/provisioning/mapping/session ยังคงเปิดใน U01

อัปเดตการเลือก Auth วันที่ 2026-11-06: ผู้ใช้เลือก **Backend ดูแล Login เอง ไม่ใช้ Firebase** แทนข้อเสนอเดิม ทำ Auth Design เสนอ Argon2id + server-side session และส่วนขยาย auth.credentials/auth.sessions; สองตารางนี้ยังไม่อนุมัติและยังไม่มี migration/grants/DB writes ต้องยืนยันวิธีสร้างบัญชีและ role ของบัญชีใหม่ก่อนทำ Signup สถานะ P08 ยัง In Progress และความคืบหน้ายัง 15%

อัปเดตล่าสุด — Auth SQL review วันที่ 2026-11-06: ผู้ใช้ยืนยัน student สมัครเอง/ผู้ดูแลเตรียม advisor-coordinator และอนุมัติให้เตรียม migration/RBAC ตามแบบที่อธิบาย เพิ่ม SQL draft 2 ไฟล์ใน database/auth โดย storage include RBAC ใน transaction เดียวและจบ ROLLBACK เสมอ ร่างให้สมัคร student ผ่าน controlled function/lookup hash ผ่าน function/จัดการ session ด้วยสิทธิ์จำกัด ไม่มี direct users write หรือ credentials table access ให้ app รอบนี้ยังไม่เชื่อม DB/รัน grants/COMMIT และไม่แก้ SQL V1 เดิม สถานะ P08 ยัง In Progress ความคืบหน้ายัง 15%

ผลตรวจไฟล์ Auth SQL รอบนี้: parser PostgreSQL 18.6 (pglast 8.7) ผ่าน 24 statements, PL/pgSQL bodies 4 จุดและ SQL function body 1 จุด; AST checks ของ transaction/guard/โครงสร้าง/ขอบเขต GRANT ผ่าน รายละเอียดใน Auth Design ส่วน 9 ทั้งหมดเป็น offline ไม่ใช่ผล PostgreSQL runtime/ACL/Login PASS; unit tests validation 17 กรณีเป็นผลรอบพัฒนา helper ไม่ได้รันซ้ำในรอบ SQL review

อัปเดตล่าสุด — Auth DB regression วันที่ 2026-11-06: ผู้ใช้ให้ดำเนินการขั้นทดสอบต่อ ตรวจ baseline แบบ read-only แล้วทดสอบบน student_project_management_v1_test ได้ **PASS 40/40** ตาม Auth Design ส่วน 10 ทดลอง DDL/RBAC/fixtures ด้วย project_owner และคำสั่ง app ด้วย project_app ไม่ใช้ superuser ข้ามคำสั่งที่ถูกปฏิเสธ แก้เฉพาะ expected SQLSTATE ใน test ลบ user จาก 23503 เป็น 23001 หลังยืนยัน ON DELETE RESTRICT ทำงานถูกต้อง ไม่มีการแก้ SQL/grants เพิ่ม หลัง ROLLBACK metadata/ACL/row counts คืน baseline 14 ตาราง/0 แถว (ไม่รวม sequence values) ยังไม่ COMMIT/ติดตั้ง Auth ถาวร/ทำ HTTP Login; P08 ยัง In Progress และเปอร์เซ็นต์ยัง 15%

อัปเดตล่าสุด — Backend Auth วันที่ 2026-11-06: ผู้ใช้สั่งพัฒนา hash/verify + Register/Login/Logout และยืนยัน session 8 ชั่วโมง/localhost:3000,8000 เพิ่ม auth_security/auth_store/auth_api, ต่อ main.py และ config example ที่ไม่มี secrets ไม่แก้ .env จริง/Frontend/SQL Runtime pin project_app + test DB ไม่มี admin fallback; HTTP tests ยืม connection ที่ effective role เป็น app และใช้ savepoints ภายใน outer ROLLBACK ได้ PASS 57 tests (17+16+24) พร้อม baseline verification; ไม่ใช่ V1 Workflow 57 เดิม แยก dev dependencies เป็น httpx2 ให้ตรง Starlette และ pip check ผ่าน P19 เปลี่ยน Not Started→In Progress เพราะมี Auth negative tests จริง แต่ไม่มี Done เพิ่ม จึงยัง 15%

อัปเดตล่าสุด — ติดตั้ง Auth วันที่ 2026-11-06: ดำเนินการต่อจากขั้นติดตั้งถาวร เพิ่ม Auth_Install (dry-run/--apply/--check-runtime) แล้ว COMMIT เฉพาะ Auth DDL/grants ลง student_project_management_v1_test ไม่มี fixture/role/password changes ปรับ tests รองรับ installed baseline และ UUID emails โดยตรวจ function bodies/owner/ACL ก่อนใช้งาน แก้เฉพาะ validator ให้รู้จัก NOT NULL catalog ของ PG18 ไม่แก้ SQL review Tests 57+40 ก่อน/หลังติดตั้งผ่านและคืน baseline 16 ตาราง/0 แถวหลัง ROLLBACK เปิด Backend ที่ localhost:8000 GET /,/docs,/openapi.json ผ่าน รอผู้ใช้ตั้ง AUTH_DB_PASSWORD ซึ่งผู้ใช้ยืนยันว่าจะตั้งเอง; ไม่แสดง secrets ยังไม่รับรอง direct app-password connection และ P06 V1 v1_lock_team ยังค้าง ไม่มี Done เพิ่มจึงยัง 15%

อัปเดตล่าสุด — ตรวจ config/runtime วันที่ 2026-11-06: ผู้ใช้แจ้งว่าตั้ง AUTH_DB_PASSWORD แล้ว ตรวจ read-only direct connection ผ่านและ smoke 7 จุดด้วย project_app session จริง ไม่มี SET ROLE/admin fallback: Register201/wrongLogin401/Login200/CSRF403/Logout204/ROLLBACK cleanup/live TCP unknownLogin401 ไม่แสดง config/password/token/hash และไม่แก้ .env/source/schema/grants/role ผล smoke แยกจาก suite 57 และ DB-only 40 เดิม ยังไม่ทดสอบ successful runtime COMMIT หรือ Browser/Frontend/Team ไม่มี Done เพิ่มจึงยัง 15%

อัปเดตล่าสุด — Frontend Auth/Me 2026-11-07: ผู้ใช้เลือก Feature-based src/features/auth เพิ่ม GET /api/v1/auth/me + หน้า register/login/บัญชี/Logout เชื่อม API จริง ไม่เปลี่ยน SQL/RBAC/Requirements/.env/backend.database ผล suite 65 (17+16+32), lint/TypeScript/build และ Browser 5/5 ผ่าน ตรวจ Desktop/Mobile และ baseline หลัง ROLLBACK/ไม่มี fixture connection ค้าง ใช้ test DB เท่านั้น Browser fixture 8001 ไม่เปลี่ยน default API8000; เพิ่ม Playwright และ test runner ที่ไม่เก็บ fixtures ถาวร P17 เปลี่ยน Not Started→In Progress เพราะมี Auth integration จริง แต่ยังไม่มี business flow จึงไม่มี Done เพิ่มและยัง 15% U02 ยืนยันแล้ว; U01 security/provisioning ที่เหลือยังเปิด

- หน้าจอST-01–ST-09ที่มีimplementation: 5/9 (ST-02/ST-04/ST-06และบางส่วนST-03/ST-05ตามscopeที่ยืนยัน); ไม่ใช่5หน้าDoneหรือการผ่านACทุกหน้า advisor inboxนับแยกจาก9หน้าstudentเดิม
- ผล Workflow DB รอบก่อน: 57/57 PASS เป็นอัตราผ่านของชุดนั้น ไม่ใช่ requirement coverage 100%
- รายการ U01–U09 ใน [reference](../database/SCHEMA_V1_REFERENCE.md) ยังไม่นับเพิ่มในตัวหารจนยืนยันขอบเขต
- หากแตก/รวม/เพิ่ม/ตัดงาน ให้บันทึกเหตุผลและฐานตัวหารก่อน/หลัง ไม่เปลี่ยนตัวเลขเงียบ ๆ

## ลำดับที่เสนอให้พัฒนาต่อ

1. [บันทึกadvisor1บัญชีตามอนุมัติแล้ว](../database/ADVISOR_ACCOUNT_PROVISIONING.md): ยืนยันSubmission/file ContractตามV1เป็นworkflowถัดไปก่อนเขียนAPI/UI ไม่เพิ่มstatusหรือขั้นCoordinatorนอกข้อกำหนด
2. เตรียมแผน fixtureร่วม/Concurrencyให้ตรวจรับ ก่อนขออนุญาตCOMMITข้อมูลจำลองเฉพาะส่วนที่จำเป็น แยกจากDDL repairที่ติดตั้งแล้ว
3. ขยายProjectรายละเอียด/metadataที่อนุญาตตามphaseเป็นContractแยก ไม่เพิ่มProject DELETEตามR-01
4. ขยาย invitations→submissions→committee→tasks→evaluation พร้อม tests ตามแต่ละงาน; พิสูจน์ concurrency เมื่อ prerequisites พร้อม
5. ปิด security/UAT และคู่มือ โดยใช้ [Progress Report Template](PROGRESS_REPORT_TEMPLATE.md) อัปเดตหลักฐานทุกครั้ง

## ประเด็นบำรุงรักษาที่แยกจากฟังก์ชันธุรกิจ

| ID | ประเด็น | สถานะ / ขอบเขตถัดไป |
|---|---|---|
| M01 | Test-only connection boundary | แก้ Preflight/เครื่องมือ V1ทั้ง5ตัวแล้ว: pin DB/readonly guard ไม่ import backend engine; offline boundary9ผ่าน ไม่ใช่ fresh-install proof |
| M02 | ส่งต่อโค้ดใน Git | commit9d07c52/Pushแล้วตามอนุมัติรอบก่อน; งานเตรียมTeam DBรอบใหม่นี้ยังไม่Commit/Push |
| M03 | ไฟล์ __pycache__ ที่ root อยู่ก่อนแล้ว | .gitignoreที่rootกันcacheแล้ว ไม่ได้ลบไฟล์ในเครื่อง |
| M04 | เก็บผลทดสอบต่อเนื่องเป็น artifact ที่อ้างเวอร์ชันได้ | Auth Design ส่วน 10–11 เป็นหลักฐานรุ่นก่อนติดตั้ง; Installation Report มีสถานะติดตั้ง/tests 57+40 และ hashes รุ่นรองรับ installed baseline; V1 Workflow 57 เดิมยังอ้างบทสนทนา ต้องแยก suite/ขอบเขตและไม่เผย secrets |

อัปเดตล่าสุด — ติดตั้ง V1 baseline 2026-11-07: ผู้ใช้อนุมัติ “ติดตั้งและทดลองได้เลย” ติดตั้ง6definitionsตามsourceและEXECUTE v1_lock_team1รายการด้วยeffective project_owner ไม่มีfixture/role/password changes มี52V1functionsตรงsource direct project_app ไม่มีowner switchผ่าน8cases, owner-Team9/installed Workflow57/boundary+Auth74/AuthDB40ผ่าน ข้อมูลทั้งหมดROLLBACKคืนinstalled baseline; installerซ้ำ ALREADY_INSTALLED_VERIFIED/committed=false P06 Done และ checklistเป็น20% ยังไม่GitCommit/Pushใหม่ ไม่ใช่TeamHTTP/Concurrency/fresh-install proof

อัปเดตล่าสุด — Team API 2026-11-07: ผู้ใช้ยืนยันrequest/response/status/session-CSRFตามร่างแล้ว ImplementPOST /api/v1/teamsเฉพาะTeam+ผู้สร้างleader เพิ่มteam_api/team_store, ต่อmain.py/handlers และtest fixtureให้ทั้งAuth/Teamrollback Tests101=Auth65+Team27+boundary9 และdirect project_app ASGI/TCPผ่าน ตรวจmetadata/ACL/rowcountsคืนbaseline52functions/0แถว ไม่แก้Schema/RBAC/Frontend/.env และไม่GitCommit/Pushใหม่ P09/P16ยังInProgressเพราะmember/read/Project/UIยังไม่ครบ ไม่มีDoneเพิ่มจึงคง20%

อัปเดตล่าสุด — Team Frontend/current-team 2026-11-07: ผู้ใช้ยืนยันGETทีมของตนตามG-12 ไม่มีทีม404TEAM_NOT_FOUND แทนข้อเสนอเดิม200data:null พัฒนา/teamsในfeatures/teamsพร้อมcreate/refresh/readเฉพาะสมาชิกภาพตน Backend111tests (65+37+9), Browser13/13 (Auth5+Team8), lint/TypeScript/build/direct app ASGIผ่าน ทุกfixtureROLLBACKและคืนbaseline52functions/0แถว ไม่มีSQL/grants/.envหรือGitCommit/Pushใหม่ P15→InProgress; Doneยัง4/20=20% ดูรายงานFrontendสำหรับหลักฐาน/ข้อจำกัด

อัปเดตล่าสุด — Team Members 2026-11-07: ผู้ใช้ยืนยันกรอกอีเมลตรงตัวแล้วเพิ่มทันทีและGET/POST /teams/me/members พัฒนาBackend/Frontendแล้ว Backend129=65+37+18+9, Browser21=5+8+8, direct app smoke/lint/TypeScript/buildผ่าน เก็บข้อมูลเดิมที่มีบัญชี/ทีมอย่างละ1ไว้ ทุกfixtureใหม่ROLLBACKและmetadata/ACL/rowcountsคืนbaseline แก้Auth test countให้เทียบbaselineแทนสมมติDBว่าง ไม่แก้SQL/grants/.env/Business Rulesและไม่GitCommit/Push P09/P15/P16/P17ยังInProgress ไม่มีDoneเพิ่มจึงยัง4/20=20%

อัปเดตล่าสุด — Project 2026-11-07: ผู้ใช้ยืนยันProject Contractแล้ว พัฒนาPOST /projects และGET /projects/meพร้อมหน้า/projects/ลิงก์จากteams ไม่มีDELETE/UPDATE Backend150=65+37+18+21+9, Browser30=5+8+8+9/direct app smoke/lint/TypeScript/buildผ่าน มีC-01/UNIQUE/actor/role/R-01/rollback/error coverage เก็บข้อมูลเดิมusers2/credentials2/sessions1/teams1/team_members2/projects0ไว้ ทุกfixtureROLLBACK metadata/ACL/rowcountsคืนbaseline ไม่แก้SQL/grants/.env/Requirementsและไม่Commit/Push P09/P15/P16/P17ยังInProgress Done4/20=20%

อัปเดตล่าสุด — Advisor invitations 2026-11-07: ผู้ใช้ยืนยันselectจากรายชื่อ/ทำครบworkflowแล้ว พัฒนา6operations/5pathsและสองหน้าทีม-advisor Backend174/Browser42/direct app boundary/lint/TypeScript/buildผ่าน Browserใช้project_ownerเตรียมadvisor2/coordinator1ในoutertransactionก่อนswitchเป็นeffectiveproject_appทุกHTTPrequest ไม่มีadminfallbackruntime ทุกfixtureROLLBACKคืนbaselineที่มีprojects1/users2เดิม ไม่สร้างadvisorถาวร/แก้SQL/grants/.env/Commit/Push P10Doneตามเกณฑ์API/UI/immutableที่ยืนยัน Done5/20=25% P08/P18ยังไม่ปิด

อัปเดตล่าสุด — Advisor provisioning 2026-11-07: เพิ่มownerCLIสร้างadvisorใหม่เท่านั้น DefaultDRY_RUN/ROLLBACK --applyต้องconfirmtestDB รหัสผ่านhiddenTTYไม่รับargument/env/file ไม่upsert/activateบัญชีเก่า 17testsและRegression191ผ่าน --checkอ่านสด/TTYdryrunข้อมูลที่ผู้ใช้ระบุผ่านจริง ยังไม่--apply/COMMITข้อมูลบัญชีถาวร ไม่แก้API/Frontend/SQL/RBAC/.env/Requirements ไม่Commit/Push P08ยังInProgress Done5/20=25%

อัปเดตล่าสุด — บันทึกadvisorตามอนุมัติ 2026-11-07: ผู้ใช้ตอบอนุมัติบันทึกหนึ่งบัญชี รัน--apply/confirmtestDB/hiddenTTYด้วยeffectiveproject_ownerแล้ว APPLIED/persisted=true เพิ่มusers1/credentials1เท่านั้น บัญชีroleadvisor/user_id1667 ตรวจconnectionใหม่พบhashArgon2idและdirectLOGINproject_app TestClientLogin200/Me200/inbox200/Logout204ในouterROLLBACK Provisioning17testsหลังapplyผ่าน metadata/ACLไม่เปลี่ยน sessionsยัง1 fixture0 บัญชีเดิมอยู่ครบ ไม่แก้Source/Schema/RBAC/.envและไม่Commit/Push P08ยังInProgress Done5/20=25%

อัปเดตล่าสุด — เตรียมส่งต่อทีม 2026-11-07: เจ้าของยืนยันWindows/PostgreSQLแยกเครื่อง เพิ่มdocs/teamสำหรับsetup/DB/Submission/Milestone/Gitchecklist/verification และblankbackend/.env.example ไม่implementfeaturesใหม่ รันRegression191/Browser42/build/lint/TypeScript/DBworkflow57และROLLBACKcleanupผ่าน ตรวจsecrets/ignore/imports/links/sourceSQLchecksumแล้ว FreshmachineinstallยังNotVerified ไม่มีstaging/Commit/Push Done5/20=25%เท่าเดิม

อัปเดตล่าสุด — Topic votes 2026-11-15: ผู้ใช้ยืนยันครบVote/รายชื่อ/ผลตามสิทธิ์และกรรมการเห็นVoteตนเอง+decisionเมื่อครบ เพิ่มAPI7operations/6paths/UI6routes/acceptedAdvisorlist/roleprojectionตาม [Contract](../api/TOPIC_VOTES_CONTRACT.md) Backend349/Topic17/Browser90รวมTopic9/build/lint/TypeScriptผ่าน ROLLBACK/fixtureconn0/baseline52functions-ACLตรงsource ไม่เปลี่ยนSQL/RBAC/peerSubmission-Milestone/Supabase/.envหรือGitCommit/Push P12คงInProgressสำหรับTX02/UAT ไม่เพิ่มDone จึงยัง5/20=25% เป็นอัตราปิดchecklistไม่ใช่เปอร์เซ็นต์effortหรือfeaturecoverage

อัปเดตล่าสุด — ติดตั้งTopicConcurrencyfixture2026-11-15: ผู้ใช้อนุมัติ29แถวและVC8 รันAPPLIED/COMMITเฉพาะseed29แถวในtestDB มีmanifestนอกGit/durableก่อนCOMMIT/postflightข้อมูลเดิม-ACLตรงbaseline Repeatapplyไม่เพิ่มแถว RCseedเดิม10แถวยังvalid VC8/8directapp/3PID/waitจริง/A-BROLLBACKผ่าน Backend386/Browser90หลังติดตั้งผ่านพร้อมคืนbaseline ไม่มีruntime/SQL/RBAC/peer/.env/Gitเปลี่ยน ยังไม่winner-COMMIT/HTTP/40001/retry/UAT P12/P18คงInProgress Done5/20=25%
