# จุดเริ่มต้นสำหรับทีม — Student Project Management System

**รอบ Task 2026-11-16:** เจ้าของยืนยัน Task/Assignee/History สำหรับทีมแล้ว มี [Contract](../api/TASKS_CONTRACT.md), [รายงานล่าสุด](../progress/TASK_IMPLEMENTATION_REPORT.md) และ [คู่มือขั้นตอน](../user/USER_GUIDE.md) ต่อจาก Milestone MVP ข้อความ “ยังไม่มี Task API” ในรายงานก่อนหน้าเป็นสถานะก่อนรอบนี้ ยังคง test DB/project_app/ROLLBACK และไม่เปิด Supabase หรือ Task หน้าบทบาทอื่น

**สถานะต่อจาก integration 2026-11-16:** เจ้าของอนุมัติรับช่วงงานที่เพื่อนยังไม่ได้ทำแล้ว มี Submission UI และ Milestone API/UI สำหรับทีมตาม [รายงานใหม่](../progress/PEER_WORK_CONTINUATION_REPORT.md) / [Milestone Contract](../api/MILESTONES_CONTRACT.md) ข้อความ integration ด้านล่างบันทึกสถานะก่อนรอบนี้ Task API/Assignees และหน้าของ advisor/coordinator สำหรับ Milestone ยังนอก scope

**รวมงาน 2026-11-16:** local `feature/team-integration` รับ Backend Submission ของเพื่อนแล้ว ใช้ [Contract](../api/SUBMISSIONS_CONTRACT.md) และ [รายงาน integration](../progress/SUBMISSION_INTEGRATION_REPORT.md) เป็นสถานะล่าสุด; รักษาระบบของเราจาก `6040702` และที่มาของเพื่อน `31c4fcb` ยังไม่ Commit/Push ชุดรวม ไม่รวม Supabase runtime, Submission UI หรือ Milestone API/UI

**ชุดส่งต่อ 2026-11-15:** ดู [สรุปส่วนเพิ่ม/ผลทดสอบ/ข้อจำกัดและสถานะก่อนเผยแพร่](RELEASE_PREPARATION_2026-11-15.md) สำหรับ `feature/project-continuation`; ตรวจ commit/remote ที่ได้รับก่อนเริ่มงาน รายงาน handoff เดิมเป็นหลักฐานของฐาน `679913a`

**คู่มือ/UAT 2026-11-15:** มี [คู่มือผู้ใช้](../user/USER_GUIDE.md), [Demo](../user/DEMO_SCRIPT.md) และ [แผนManual UAT20กรณี/เปิด8001แบบROLLBACK](../uat/MANUAL_UAT.md) แล้ว Startup/API/teardown probe9คำขอผ่านและคืนbaseline แต่ **Manual UATโดยทีมยังNot Run** เอกสารอิงlocalworkingtreeที่ยังไม่Commit/Push ต้องได้sourceชุดเดียวกันก่อนทำตาม ไม่ถือว่าclonecommitเก่าจะมีWorkspace/Evaluationครบ

**ล่าสุด Evaluation 2026-11-15:** พัฒนา [API/UI ตาม Contract ที่ยืนยัน](../api/EVALUATIONS_CONTRACT.md) แล้ว กรรมการบันทึกคะแนนครั้งเดียวและเห็นของตน; รวม/เฉลี่ยเปิดเมื่อครบ และ Coordinator เห็นรายบุคคลหลังครบเท่านั้น ดู [ผลตรวจและข้อจำกัด](../progress/EVALUATIONS_IMPLEMENTATION_REPORT.md) เงื่อนไขหัวข้อผ่าน/มี completed Milestone มาจาก SQL เดิม รอบนี้ไม่แก้ Submission/Milestone/Supabase ของเพื่อนหรือ Schema/RBAC

**รอบ Topic votes 2026-11-15:** [Vote/รายชื่อ/ผลตามสิทธิ์ครบContract](../api/TOPIC_VOTES_CONTRACT.md) ต่อจากCoordinatorappointmentแล้ว [Backend349/Browser90/lint/TypeScript/buildผ่าน](../progress/TOPIC_VOTES_IMPLEMENTATION_REPORT.md) ทุกfixtureROLLBACK กรรมการเห็นVoteตนเองและdecisionเมื่อครบ Team/acceptedAdvisorเห็นrosterและผล/commentsตามช่วง Coordinatorเห็นVoteรายบุคคล ผู้ใช้ [เตรียมcoordinatorผ่านCLIเอง](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) Projectต้องมีapprovedSubmissionจริงตามG-12 ยังไม่รวมไฟล์Submissionของเพื่อนหรือCommit/Push

**ตรวจความคืบหน้า 2026-11-14:** อ่าน [รายงานล่าสุด](../progress/2026-11-14_CONTINUATION_REVIEW.md) และ [รายการรับช่วงจาก database-schema2](SCHEMA2_INTEGRATION_HANDOFF.md) ก่อนรวมงานเพื่อน ส่วนตารางด้านล่างอธิบายฐาน `679913a` ที่ส่งทีมเมื่อ 2026-11-07; Submission Backend ใหม่ยังอยู่เฉพาะ branch เพื่อน และยังไม่รวมเข้าฐานนี้

เจ้าของยืนยันว่าเพื่อนรับผิดชอบ **Submission + Milestone** และเตรียม **Supabase สำหรับอนาคต** จึงไม่ทำสอง feature ซ้ำหรือย้าย runtime DB ตอนนี้ เจ้าของอนุมัติ [แก้ชื่อ/คำอธิบาย Project](../api/PROJECT_UPDATE_CONTRACT.md) แล้ว พัฒนาและทดสอบครบขอบเขตตาม [รายงาน2026-11-14](../progress/PROJECT_UPDATE_IMPLEMENTATION_REPORT.md) ใน local feature/project-continuation ยังไม่ Commit/Push

**รอบต่อมา Team update:** หัวหน้าแก้ชื่อ/คำอธิบายทีมได้ตาม [Contract](../api/TEAM_UPDATE_CONTRACT.md) และกฎphaseเดิม ผ่านBackend214/Browser56/directapp/lint/TypeScript/buildพร้อมROLLBACK ดู [รายงานล่าสุด](../progress/TEAM_UPDATE_IMPLEMENTATION_REPORT.md) ยังไม่เพิ่มออก/ถอดสมาชิก/โอนหัวหน้า API/UI และยังไม่รวมงานเพื่อน

**รอบโอนหัวหน้าถัดมา:** ยืนยันและimplemented [Leader transfer](../api/TEAM_LEADER_TRANSFER_CONTRACT.md) แล้ว ผ่านBackend227/Browser63/directapp/lint/TypeScript/buildพร้อมROLLBACK ดู [ผลล่าสุด](../progress/TEAM_LEADER_TRANSFER_IMPLEMENTATION_REPORT.md) ออก/ถอดสมาชิกยังไม่พัฒนา คงbranchlocalเดิมและไม่mergeงานเพื่อน/Commit/Push

**รอบออก/ถอดสมาชิกถัดมา:** [Exit Contract](../api/TEAM_MEMBERSHIP_EXIT_CONTRACT.md) implemented/verifiedแล้ว Backend242/Exit15/directapp และหลังพอร์ตmanualว่าง build/Browser73รวมExit10/lint/TypeScriptผ่านพร้อมROLLBACK ดู [ผลตรวจรับล่าสุด](../progress/TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md) ยังไม่รวมงานเพื่อนหรือCommit/Push

อัปเดต2026-11-07 · ทีมใช้ **Windows/PowerShell และ PostgreSQLแยกเครื่อง** ตามที่เจ้าของยืนยัน ฐานพัฒนาปัจจุบันfeature/database-schema; ต้องเริ่มจากcommitที่มีเอกสารนี้ ไม่ใช่remotecommit9d07c52เดิมที่ยังไม่มีงานรอบTeam/Project/Invitations

## อ่านตามลำดับ

1. [ตั้งค่าเครื่อง](LOCAL_SETUP.md) และ [ฐานข้อมูลเครื่องใหม่](DATABASE_SETUP.md)
2. [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md), [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md), [Backlog](../progress/BACKLOG.md)
3. [งานส่งโครงงาน](SUBMISSION_WORK_PACKAGE.md) หรือ [งานMilestone](MILESTONE_WORK_PACKAGE.md) ตามส่วนที่รับผิดชอบ
4. ก่อนส่งโค้ดกลับ อ่าน [Git/checklistส่งต่อ](GIT_RELEASE_CHECKLIST.md) และ [ผลตรวจชุดส่งต่อ](HANDOFF_VERIFICATION.md)

## มีอะไรแล้ว / ยังเหลืออะไร

| ส่วน | หลักฐาน / สถานะ |
|---|---|
| Auth | Registerstudent/Login/Logout/Me, Argon2id, session8ชั่วโมง, CSRF/Origin/CORS; Frontendเชื่อมแล้ว |
| Team | สร้างTeamพร้อมตนเป็นleader อ่านทีม/รายชื่อ เพิ่มmemberด้วยemail; ยังไม่มีออก/ถอด/โอนหัวหน้าAPI/UI |
| Project | หัวหน้าสร้าง1Projectต่อทีม สมาชิกอ่านProjectตน; ห้ามลบตามR-01; ยังไม่มีmetadataupdateAPI/UI |
| Advisor invitation | เลือกadvisor/ส่ง/ประวัติ/ยกเลิก และadvisorinbox/รับ/ปฏิเสธ ครบContractที่ยืนยัน |
| Database | publicV1 14tables/86columns/28FK/52functions/24triggers + auth2tables/6columns/2FK |
| Submission/file/review | มีSQL/DB-onlyregressionบางส่วน ยังไม่มีAPI/UIหรือHTTPContractที่ยืนยันสำหรับส่วนนี้ |
| Milestone/Task | มีSQL/controlledfunctions/DB-onlyregressionบางส่วน ยังไม่มีAPI/UIหรือHTTPContractที่ยืนยันสำหรับส่วนนี้ |
| Concurrency/UAT/freshinstall | อ่านขอบเขตในBacklog/ผลตรวจ ไม่ถือว่าเสร็จจากจำนวนtests |

คำว่าDB-onlyไม่เท่ากับAPIใช้งานได้แล้ว หน้าบัญชีไม่ใช่Dashboard ตารางMilestoneไม่ใช่หลักฐานว่ามีTaskboard UI

## ข้อตกลงร่วมของสองทีม

- ห้ามเปลี่ยนSchemaV1/BusinessRules, SQLreviewที่pinchecksum หรือgrantsเพื่อแก้permissionerrorเอง ให้รายงานและยืนยันก่อน
- ใช้student_project_management_v1_testเท่านั้น ไม่ใช้DBหลัก เครื่องใหม่มีบัญชี/ข้อมูลแยกจากเครื่องเจ้าของ Gitไม่ได้ย้ายPostgreSQLหรือบัญชีadvisorไปด้วย
- Runtimeใช้project_app ส่วนownerใช้เฉพาะติดตั้ง/fixtureที่อนุมัติ ไม่ใส่adminfallbackในAPI
- ทุกAPIใช้sessionเดิม และPOST/การเขียนใช้session-boundCSRF/OriginตามContract; IDsเป็นdecimalstrings ห้ามใช้clientuser_id/roleเป็นสิทธิ์
- ทดสอบการเขียนด้วยTransaction/ROLLBACK ตรวจcurrent_databaseก่อนชุดและmetadata/ACL/rowcountsหลังชุด เก็บข้อมูลเดิม ไม่COMMITfixtureเพื่อทำmulti-sessionเอง
- การติดตั้งSchema/Authหรือสร้างบัญชีถาวรเป็นงานผู้ดูแลตามขั้นอนุมัติ ไม่ใช่testfixtureปกติ
- ไม่เผยpassword/hash/token/.env/DBdumpในGitหรือรายงาน ใช้templatesที่เว้นpasswordว่าง

## จุดต่อโค้ดที่ใช้ร่วมกัน

- [main.py](../../backend/main.py): appfactory/router/validation/storage/no-store/CORS ต้องรักษาของเดิม
- [auth_api.py](../../backend/auth_api.py), [auth_store.py](../../backend/auth_store.py): active session, error envelope, pinnedDB/appconnection; ไม่ใช้legacybackend/database.pyเป็นrequestconnection
- [project_store.py](../../backend/project_store.py), [invitation_store.py](../../backend/invitation_store.py): ตัวอย่างauthorizedquery/UOW/actorGUC/parentlocks/narrowPGerror mapping
- Frontendroutesอยู่src/app; งานใหม่แยกsrc/features/submissionsและsrc/features/milestonesเมื่อContractยืนยัน โดยreuseAuthsession/APIorigin ไม่สร้างLogin/roleระบบใหม่
- [auth_browser_server.py](../../backend/tests/auth_browser_server.py): **เพิ่มUOWoverrideของfeatureใหม่** ให้ใช้outerROLLBACKเดียวกันก่อนBrowserPOST มิฉะนั้นอาจหลุดไปCOMMITบนnormalconnection
- [test_auth_security.py](../../backend/tests/test_auth_security.py): อัปเดตOpenAPIpathsetเมื่อมีendpointที่ยืนยันเพิ่ม

SubmissionและMilestoneพัฒนาแยกbranchได้ แต่ต้องตกลงไฟล์shared main.py/tests/harness/errorhandlersก่อนmerge ไม่มีการเลือกURL/DTO/phaseหรือlibraryที่ยังไม่ยืนยันแทนเจ้าของrequirementsในเอกสารนี้
