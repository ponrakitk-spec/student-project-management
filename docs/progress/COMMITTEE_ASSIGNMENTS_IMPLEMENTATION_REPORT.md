# Coordinator / Committee assignments — รายงานพัฒนาและตรวจรับ

บันทึกนี้เป็นsnapshotรอบappointment วันที่2026-11-14 ต่อมาผู้ใช้อนุมัติVote/roster/resultsและพัฒนาเพิ่มแล้ววันที่2026-11-15 ดู [รายงานTopic votes](TOPIC_VOTES_IMPLEMENTATION_REPORT.md) สำหรับสถานะและจำนวนtestsล่าสุด ข้อความ“ยังไม่Vote”ด้านล่างเป็นประวัติของรอบเดิม

วันที่ 2026-11-14 (Asia/Bangkok) · Branch `feature/project-continuation` จาก `679913a` + working tree · Contract ยืนยันครบดูรายการ/เพิ่ม/เปลี่ยน/ถอด

ผู้ใช้ยืนยัน [Contract](../api/COMMITTEE_ASSIGNMENTS_CONTRACT.md) “ใช้ร่างครบ: ดูรายการ/เพิ่ม/เปลี่ยน/ถอด (แนะนำ)” และเลือกกรอกบัญชีจริงผ่านCLIเอง รอบนี้ไม่สร้างcoordinatorถาวร ไม่ทำVote/EvaluationAPI ไม่รวม/แก้Submission-Milestone-Supabaseของเพื่อน

## ผลลัพธ์และไฟล์ที่เปลี่ยน

| ไฟล์ / กลุ่ม | หน้าที่ |
|---|---|
| [committee_api.py](../../backend/committee_api.py), [committee_store.py](../../backend/committee_store.py) | 6operations/5pathsตามContract, role/G-12/Origin/CSRF, Projectlock/recheck/controlledwrites/error mapping |
| [main.py](../../backend/main.py) | router/validation/storage/no-store สำหรับCoordinator; CORSmethodsเดิมGET/POST/PATCH |
| [test_committee_api.py](../../backend/tests/test_committee_api.py), test_auth_security.py | HTTP/PostgreSQL15tests และOpenAPI23pathsโดยไม่เปิดDBตอนimport |
| [Auth_Provision_Coordinator.py](../../database/tools/Auth_Provision_Coordinator.py), [tests](../../database/tests/test_coordinator_provision.py) | fixed-role CLI/defaultDRY RUN/hiddenTTY/owner guard/hash/atomic account; 11tests |
| frontend/src/features/committee-assignments/* | APIclient/DTO/statusvalidation/role-gatedUI/confirm/pending/GETreconcile/CSS |
| frontend/src/app/coordinator/projects/page.tsx, frontend/src/app/coordinator/projects/[id]/committee/page.tsx | รายการและหน้าจัดกรรมการรายProject; dynamicrouteawaitparamsตามNext.jsguideที่ติดตั้ง |
| frontend/src/features/auth/account-screen.tsx | ลิงก์พื้นที่Coordinatorเฉพาะroleนี้ |
| [auth_browser_server.py](../../backend/tests/auth_browser_server.py) | CommitteeUOWoverrideและDB-onlyphasegraphภายในouterROLLBACK; staffเฉพาะfixturemodeก่อนserveทุกrequestเป็นeffectiveapp |
| [committee.spec.ts](../../frontend/tests/committee.spec.ts) | Browser8cases ทั้งrealAPIและerrorinjectionที่ระบุด้านล่าง |
| Contract/accountguide/backlog/reference/handoff/setup/report | scope/หลักฐาน/วิธีทดสอบ/จุดต่อกับเพื่อน |

ไม่เปลี่ยนSQLV1/Auth/RBAC, PostgreSQLroles/grants, .env, requirements/dependencies หรือbusinessrules ไม่มีProjectDELETEหรือGitCommit/Push

## พฤติกรรมที่ตรวจแล้ว

- coordinatorเท่านั้นอ่านรายการProjectที่มีapprovedSubmission; ใช้EXISTSapprovedตามSQL/G-12 ไม่เพิ่มlatest-onlygate ขณะที่Projectไม่มีapprovedตอบ404 ไม่เปิดfiles/submissions/สมาชิก/ผลVoteหรือEvaluationในDTOรอบนี้
- candidateคืนadvisorid/full_nameเท่านั้น ตัดacceptedadvisorและadvisorที่อยู่rosterออก; assignmentเรียงassigned_at/id ASC ไม่เปิดemail/assigned_by
- เพิ่มหนึ่งคนได้ตั้งแต่roster0/1/2 ไม่บังคับ3พร้อมกันและไม่จำกัดmax3 การเปลี่ยนคงassignmentID/assigned_at/assigned_by/project_id และการถอดไม่ลบuser/Project
- ตั้งtransaction-localactorจากsession ขอProjectlockและตรวจvisibility/target/vote lock/advisorซ้ำ ใช้v1_appoint/replace/remove_committeeเดิมและSETCONSTRAINTSALLIMMEDIATEก่อนUOWจบ ไม่มีdirectUPDATE/DELETEหรือowner fallback
- Voteแรกล็อกทั้งสามwriteถาวร รวมno-opและSubmissionรอบใหม่ ทดสอบด้วยcontrolledVote/DB-onlyphasefixtures ไม่เพิ่มVoteAPIให้ระบบ
- 401/403/404/409/422ตามContract; duplicateSQLSTATE23505จำแนกเฉพาะ`uq_committee_project_advisor` ส่วนunknownSQL/permission/storagefailureเป็นsanitized500 ไม่แปลงทุกP0001/42501เป็นbusinesserror
- remove204empty/no-store/noSetCookie; JSONsuccessตามContractหลังUOWจบ ไม่ต่อsessionหรือเพิ่มTTL
- UIไม่แสดงcontrolsให้student/advisor, ไม่แสดงformsเมื่อrosterlocked มีconfirm/cancelป้องกันกดซ้ำ และlost/invalidresponseต้องGETตรวจข้อมูลก่อนretry ไม่POST/PATCHซ้ำอัตโนมัติ
- หลังจริง409rosterlocked UIโหลดreadonlyใหม่ ไม่ใช้หน้าจอเก่าเพื่อข้ามguard

## ผลตรวจรับ

| ชุด | ผล | ขอบเขต |
|---|---|---|
| CommitteeHTTP + Authsecurity | PASS31 / 6.412s | Committee15 + Authsecurity16 บนouterROLLBACK |
| Coordinatorprovision | PASS11 / 0.543s | boundary5 + PostgreSQL6 ไม่มีapplyจริง |
| FullBackendregressionรวมtools | PASS332 / 50.321s | suiteเดิม306 + Committee15 + Coordinator11 คืนsnapshot baselineทุกDBsuite |
| Frontendlint/TypeScript | PASS | รันเรียงก่อนBrowser ไม่ชนgeneratedfiles |
| Productionbuild | PASS | Next16.4.4, 11staticpages และdynamicCoordinatorroute |
| BrowserเฉพาะCommittee | PASS8 / 10.5s | cleanupmetadata/ACL/rowcounts PASS; fixture_connections0 |
| FullBrowserregression | PASS81 / 1.2min | Auth5+Committee8+Invitations12+Transfer7+Exit10+Project16+Members8+Team8+TeamUpdate7; cleanupmetadata/ACL/rowsคืนbaseline, fixture_connections0 |
| Desktop/Mobilevisual | PASS | ดูภาพreplaceconfirmationdesktopและremoveconfirmation390px ปุ่มครบ/ยกเลิกไม่ถูกบีบ/ไม่overflow |
| Read-only CLI/V1 postflight | PASS | CoordinatorCLIcheckไม่persist, V1functions52ตรงsource/effectiveACLตรงbaseline ไม่เปลี่ยนprivileges |
| Final cleanup check | PASS | clientconnectionsอื่น0 และConcurrencyfixtureเดิม1namespace ไม่มีseedใหม่จากfeatureนี้ |
| File/doc audit | PASS | scope25ไฟล์ PythonAST/whitespace/relative links173จุด ไม่มีลิงก์เสียหรือค่าลับจาก.envในscope SQL/Auth/Invitation/AdvisorCLI/dependenciesที่ตรวจตรงHEAD และไม่มีstagedfiles |

ข้อผิดพลาดระหว่างพัฒนาที่แก้แล้ว: การเรียกOrigin/error-response helpersของAPIใหม่ต้องใช้signatureเดิมให้ครบ, uniqueconstraintต้องใช้ชื่อจริงจากSQL และexpiryfixtureต้องเลื่อนcreated_atคู่กับexpires_atเพื่อรักษาAuth lifetime CHECK ไม่แก้Schema/RBACเพื่อให้testsผ่าน ทุกfailureรอบนั้นROLLBACK/baselinePASS

ผล332เป็นการรันAuth/Team/member/Project/metadata/transfer/leave-removal/Invitations/Committee/coordinatorCLI/advisorCLI/DBboundary/concurrencytoolssafeguards ไม่ใช่จำนวนRequirementที่ปิดครบ และยังไม่รวมSubmission/MilestoneAPIของเพื่อนที่ไม่ได้merge

## แยกหลักฐาน Browser / DB / Login

- happy paths/role guards/CSRFและrosterlockใช้HTTP→PostgreSQLจริงผ่านsharedfixtureUOW
- Browserphasegraphเตรียมstaffด้วยnon-superuserownerก่อนserve: advisorsA–E/coordinator และstudentleadersเฉพาะfixture จากนั้นTeam/Project/invitation/submission/file/review/committee/voteทำด้วยeffectiveproject_appในoutertransaction ไม่มีtest-onlyHTTPseed endpoint
- dummyphasefileผ่านSQLCHECKเท่านั้น ไม่ใช่การตรวจเนื้อหาPDF/uploadAPIหรือหลักฐานงานSubmissionของเพื่อน
- lost-add-responseเรียกbackendจริงได้201แล้วabortresponse; GETพบrosterที่เพิ่มโดยไม่มีPOSTretry เป็นข้อมูลในouterROLLBACK ไม่ใช่runtimeCOMMIT
- unexpectedremove200{} และmalformed/500projectreadsใช้mockเพื่อตรวจfeedback; staleeditableUIแก้เฉพาะGETprojection แต่POSTเจอ409จากDBrosterlockedจริง
- pending/mobileใช้responsegateเพื่อดูdisabledbuttonsและหนึ่งrequest ไม่มีperformanceclaim
- PositiveCoordinatorHTTP/Browserเป็นeffectiveproject_appบนowner-preparedfixtureconnection ไม่อ้างว่าเป็นpositivephysicalLOGINcoordinatorบัญชีถาวร DirectLOGINproject_appถูกทดสอบแยกว่าไม่สามารถassumeownerเพื่อprovisionได้
- ทุกtestตรวจtestDB/roles/constraintsและROLLBACK; snapshotรวมpublic/authmetadata/rowcounts ไม่รวมsequencevalues ไม่มีcoordinator/Project/Submissionsถาวรเพิ่มจากรอบนี้ และseedConcurrency10แถวเดิมยังคงอยู่ตามอนุมัติก่อนหน้า

## ทดลองใช้งานจริง

ผู้ใช้เลือก [กรอกบัญชีผ่านCLIเอง](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) ไม่ส่งpasswordในแชท หลังบันทึกบัญชีที่ต้องการแล้วเปิดBackend8000/Frontend3000ตามLocalsetup Loginและกดจัดการกรรมการจากหน้าบัญชี

Projectจะปรากฏต่อเมื่อมีapprovedSubmissionจริงตามG-12 ปัจจุบันbranchนี้ยังไม่รวมSubmissionAPIของเพื่อน จึงอาจเห็นรายการว่างตามข้อมูลจริง ห้ามCOMMITphasefixturesหรือแก้filterเพื่อสาธิตโดยไม่มีอนุมัติ

## คงค้าง / จุดต่อรอบถัดไป

- Vote/EvaluationAPI/UIยังไม่เริ่มในรอบนี้; P12ยังInProgressเพราะรวมappointment+vote ไม่ปิดจากappointmentscopeที่ผ่าน
- Team/acceptedAdvisorอ่านrosterเป็นกฎG-12 แต่endpoint/UIของสองบทบาทนี้ยังไม่ทำในรอบแรกCoordinatorตามContract ต้องทำต่อพร้อมscopeที่เกี่ยวข้อง
- บัญชีcoordinatorถาวร/ข้อมูลProjectapprovedจริงเป็นสิ่งที่ผู้ใช้เตรียมผ่านขั้นตอนที่เลือก ยังไม่รับรองruntimebusinessCOMMITจากผลouterROLLBACK
- Schema/RBACไม่เปลี่ยน, HTTPmulti-session/winner-COMMIT/Vote-rosterconcurrencyTX02/serialization/retry/UATทั้งระบบยังไม่ครบ
- ตอนรวมSubmissionเพื่อน ต้องรักษาCommitteeRouter/handler/no-store/OpenAPI23paths/ทุกUOWoverride และให้Coordinatordownloadได้เฉพาะapprovedsubmissionตามG-12 ไม่รับconfigSupabase/DBtargetที่เปลี่ยนเอง ดู [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

Done5/InProgress14/NotStarted1/Blocked0 จาก20งาน คง25%ตามสูตรเดิม ไม่เพิ่มคะแนนจากจำนวนtestsหรือหน้าจอใหม่
