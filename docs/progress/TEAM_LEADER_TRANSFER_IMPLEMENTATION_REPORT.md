# Team leader transfer — ผลพัฒนาและทดสอบ

วันที่ 2026-11-14 (Asia/Bangkok) · P09/P15/P16/P17/P19 · Branch `feature/project-continuation` จาก `679913a` + Working tree ยังไม่ Commit/Push

ผู้ใช้ยืนยัน “เริ่มโอนหัวหน้าก่อนตามร่าง” สำหรับ [Contract](../api/TEAM_LEADER_TRANSFER_CONTRACT.md) งานนี้เพิ่มโอนหัวหน้าอย่างเดียว ไม่เพิ่มออก/ถอดสมาชิก ไม่แก้ Submission/Milestone/Supabase ของเพื่อน

## พฤติกรรมที่พัฒนาแล้ว

- `POST /api/v1/teams/me/leader` รับเฉพาะ `team_member_id` เป็น positiveBIGINTstring; ใช้active session/student/Origin/session-boundCSRFเดิม ไม่มีclientactor/team/roleoverride ทุกresponse no-store
- Backendเลือกทีมจากสมาชิกภาพ ตั้งtransaction-localactor ล็อกTeam แล้วตรวจหัวหน้าปัจจุบันและเป้าหมายในทีมใหม่ภายใต้lock ไม่เปิดเผยmembershipทีมอื่น
- แปลงmembershipIDเป็นuserIDฝั่งserverก่อนเรียก `v1_transfer_team_leader` เดิม ไม่มีdirectUPDATErole/ownerfallback/grantsเพิ่ม
- Defer cardinalityเฉพาะระหว่างสลับสองบทบาท แล้วบังคับconstraints IMMEDIATEก่อนคืนsuccess200 ในtransactionเดียว rollbackเมื่อwrite/transactioncompletionล้มเหลว
- คืนCurrentTeamDTOของผู้เรียก โดยหัวหน้าเดิมกลายเป็นmemberและmembership.idยังเดิม ไม่เปลี่ยน users.role หรือProject created_by สมาชิกคนใหม่เป็นleaderพอดีหนึ่งคน
- สิทธิ์หัวหน้าสำหรับmetadata/เพิ่มสมาชิก/สร้างProject/ส่งและยกเลิกInvitationย้ายตามสมาชิกภาพปัจจุบัน แต่ประวัติผู้สร้างProject/ผู้ส่งInvitationเดิมคงเดิม
- ไม่เพิ่มmetadata phase gateในtransfer ตามSQLV1เดิม ขณะที่metadata PATCHยังใช้phaseguardของตนตามปกติ
- หน้า `/teams` ใช้รายชื่อสมาชิกเดิม เลือกสมาชิกอื่น แสดงชื่อและmembershipIDเพื่อแยกชื่อซ้ำ มีขั้นตรวจสอบ/ยืนยัน/ยกเลิก ก่อนส่งrequestจริง
- หลังสำเร็จGETทีม/รายชื่อใหม่ ซ่อนเครื่องมือหัวหน้าจากผู้โอน ไม่ตีความroleจากlocalStorageหรือเปลี่ยนAuthusers.role
- Pendingป้องกันกดซ้ำ/ปิดcancel; ผลเครือข่ายไม่แน่นอนปิดการส่งซ้ำและให้GETตรวจข้อมูล ไม่automaticPOSTretry แม้กดยกเลิกconfirmationหลังresponseหายก็ยังคงปุ่มGETตรวจสอบไว้

## ไฟล์ที่เปลี่ยนในรอบนี้

| ไฟล์ | เหตุผล |
|---|---|
| `backend/team_api.py` | Input/route/errors/validation สำหรับtransfer |
| `backend/team_store.py` | Team lock/recheck/target lookup/controlledtransfer/deferredchecks/DTO |
| `backend/tests/test_team_leader_transfer_api.py` | HTTP+PostgreSQL13tests ในouterrollback รวมสิทธิ์ที่เปลี่ยนและInvitationintegration |
| `backend/tests/test_auth_security.py` | เพิ่มpathและmethodที่อนุมัติในOpenAPIexpectations โดยไม่ต่อDB |
| `backend/tests/team_api_direct_smoke.py` | Direct apptransfer, oldleader403/newleader200 และProjectcreatorคงเดิม |
| `frontend/src/features/teams/api.ts` | POSTclient/DTOparser/errorข้อความ ใช้sessionCSRFเดิม |
| `frontend/src/features/teams/leader-transfer-form.tsx` | เลือกเป้าหมาย/confirmation/cancel/pending/reconciliation |
| `frontend/src/features/teams/team-members.tsx` | ใช้รายชื่อเดิม/leader-onlytransfer โดยไม่สร้างuserdirectory |
| `frontend/src/features/teams/team-screen.tsx` | ตรวจresponseว่าเป็นทีมและmembershipเดิมแต่rolemember แล้วโหลดข้อมูลใหม่/แจ้งผล |
| `frontend/src/features/teams/teams.module.css` | Select/confirmation/responsive styles |
| `frontend/tests/leader-transfer.spec.ts` | Browser7tests รวมduplicate-key/network/stale-target/session/pending |
| `docs/api/TEAM_LEADER_TRANSFER_CONTRACT.md` | บันทึกอนุมัติ/implementedscope |
| `docs/team/LOCAL_SETUP.md` | เพิ่มTeamUpdate/Transfertestmodulesในคำสั่งregressionสำหรับผู้รับงาน |
| Report/backlog/START_HERE/handoff | ผลใหม่/ขอบเขตและจุดที่ต้องรักษาตอนรวมงานเพื่อน |

Main/CORS/Browserharnessใช้ของเดิม ไม่เปลี่ยนเพิ่มในรอบนี้ SQLV1/RBAC/Auth/connectionpolicy/dependencies/.env และInvitationAPI/storeไม่เปลี่ยน Branchเพื่อนยังไม่ได้mergeหรือแก้

## ผลรันใหม่

| ชุด | ผล / ขอบเขต |
|---|---|
| V1 baseline readonly | PASS52functions/no differences/effectiveACL; testDBเท่านั้น committed=false |
| Auth direct runtime readonly | PASSproject_app/student_project_management_v1_test |
| TransferHTTP+PostgreSQL | PASS13tests / 4.420s ในรอบเฉพาะfeature |
| FullBackendregression | PASS227tests / 31.271s = Auth65+Team37+Members18+Project32+TeamUpdate12+Transfer13+Invitations24+DBboundary9+provisioning17 |
| Direct appASGIsmoke | PASS session_user=current_user=project_app; transfer200/oldleaderwrite403/newleaderwrite200; ROLLBACKbaselinePASS |
| Frontendlint/TypeScript/productionbuild | PASS; routeเดิม ไม่มีSubmission/Milestonefrontendเพิ่มเติม |
| Browserfullsuite | PASS63tests / 56.0s = Auth5+Invitations12+Transfer7+Project16+Members8+Team8+TeamUpdate7; cleanupPASS/fixture_connections0 |
| Desktop/Mobilevisualcheck | ตรวจscreenshotsconfirmationทั้งDesktopและ390pxMobile อ่านชื่อผู้รับ/ผลที่จะเกิดได้ ไม่มีhorizontaloverflowหรือReactduplicate-keywarningในtransfertests |

คำสั่งregressionจากrootด้วยPythonในbackend/.venv:

```powershell
python -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_team_update_api backend.tests.test_team_leader_transfer_api backend.tests.test_invitation_api database.tests.test_test_database database.tests.test_advisor_provision -q
python -B -m backend.tests.team_api_direct_smoke
```

Frontendจากfrontend: `npm run lint`, `npx tsc --noEmit`, `npm run build`, `npm run test:e2e` [คู่มือตั้งเครื่อง](../team/LOCAL_SETUP.md) อัปเดตคำสั่งแล้ว

## หลักฐานและขอบเขตการพิสูจน์

- ทุกชุดDBตรวจ `student_project_management_v1_test` ก่อน businessoperations ไม่เชื่อมฐานหลัก ไม่มีpersistentfixtureCOMMIT/DDL/grantchanges
- Effectiveownerใช้เฉพาะเตรียมstaff/sessionfixturesตามรูปแบบที่อนุมัติ Businessrequestsเป็นproject_app; directLOGINappมีsmokeแยก ไม่มีsuperuserข้ามสิทธิ์
- Fixtures/Project/Invitation/phase setupทุกrequestใช้UOWoverridesกับconnection/outerROLLBACKเดียวกัน ไม่มีnormalproductionUOWfallback TeamUOWoverrideมีอยู่แล้วในBrowserharnessจึงไม่ต้องเพิ่มconnectionใหม่
- PostgreSQLจริงพิสูจน์สลับrole/membershipIDsคงเดิม/หนึ่งleader/ProjectcreatorและInvitation sent_byคงเดิม/สิทธิ์old-newleader/BIGINTprecision/targetprivacy/constraints/rollback
- ทดสอบก่อนส่ง, pending, advisor-approved, advisor-revisionโดยใช้DB-onlySubmissionfixtureจากรอบProject ไม่แก้หรือเรียกSubmissionAPIของเพื่อน Filefixtureเป็นDB-only ไม่ใช่PDFcontentvalidation ไม่ขยายผลว่าทดสอบทุกcommittee/evaluationphaseด้วยHTTPtransferแล้ว
- Recheckระหว่างรอlockใช้testdoubleเพื่อจำลองการเปลี่ยนสิทธิ์ ไม่ใช่realmulti-sessionconcurrency
- Browserconfirmation/cancel/transfer/roleGETrefresh/memberforged403/CSRF/session/pendingเชื่อมAPI→DBจริง Stale-target404เป็นmockHTTPfeedbackเพื่อพิสูจน์UI; targetscopeจริงพิสูจน์ในBackend
- Browserlost-responseส่งให้Backendเปลี่ยนroleในoutertesttransactionจริงก่อนตัดresponse แล้วGETตรวจrolememberโดยไม่POSTซ้ำ สุดท้ายROLLBACKทั้งหมด
- ตรวจmetadata/owners/ACL/rowcountsคืนbaselineและfixtureconnection0 ไม่รวมidentitysequencevaluesที่อาจเพิ่มแม้ROLLBACK
- ผลนี้ไม่ใช่successfulruntimeCOMMIT/freshinstall/Supabase/HTTPS/LAN/UATหรือmulti-sessionconcurrency

## รวมงานเพื่อนและงานคงค้าง

**ผลทดลองที่ผู้ใช้รายงานเพิ่มเติม:** เจ้าของแจ้งว่าโอนหัวหน้าได้ หัวหน้าใหม่ได้รับสิทธิ์ และหัวหน้าเดิมใช้สิทธิ์หัวหน้าไม่ได้ บันทึกเป็นuser-reportedmanualtestเฉพาะเส้นทางนี้ ไม่ใช่การสังเกตซ้ำโดยagent ไม่ทราบmode/บัญชี/รายการendpointที่กดครบ และไม่ถือเป็นหลักฐานmanualDBcleanup/ทุกphase/UATทั้งระบบเพิ่มเติมจากผลอัตโนมัติข้างต้น

1. รักษาtransferendpoint/Teamstore/Frontendcontrols และOpenAPIpathใหม่ `/api/v1/teams/me/leader` เมื่อรวมsnapshotเพื่อน; `/teams/me`และ`/projects/me`ยังคงGET/PATCHจากงานก่อน
2. รักษาCORSและทุกUOWoverrideเมื่อเพิ่มSubmission/MilestoneAPI; ปัญหาB01–B03ใน [บันทึกเพื่อน](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ยังไม่ได้แก้แทนเพื่อน
3. ไม่เพิ่มphasegateในtransferเมื่อเชื่อมSubmission งานmetadata/เพิ่มสมาชิกยังตรวจphaseตามกฎของตน
4. ออก/ถอดสมาชิกยังไม่พัฒนา ต้องยืนยันContract/ผลต่อTaskin_progress/assigneehistory/C-02ก่อน ไม่อนุมานว่าtransferอนุมัติงานเหล่านั้นด้วย
5. Supabaseยังเป็นอนาคต ไม่เปลี่ยนruntime DB/role/config และไม่Commit/Pushรอบนี้

Transferเสร็จเฉพาะContractนี้ P09ยังInProgressเพราะออก/ถอดสมาชิกและConcurrencyยังไม่ครบ คงDone5/20=25%ตามchecklistเดิม ไม่ใช้จำนวนtestsเป็นเปอร์เซ็นต์effortหรือความครบทั้งระบบ
