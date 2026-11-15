# Leave / removal — ผลตรวจรับ API/UI

วันที่ 2026-11-14 (Asia/Bangkok) · P09/P13/P15/P16/P17/P19 · Branch `feature/project-continuation` จาก `679913a` + Working tree ยังไม่ Commit/Push

ผู้ใช้ยืนยัน “ทำทั้งออกและถอดตามร่าง” ตาม [Contract](../api/TEAM_MEMBERSHIP_EXIT_CONTRACT.md) API/UIและBackend/SQL/directLOGINappตรวจผ่านแล้ว หลังตรวจพบพอร์ตmanual3000/8001ว่างจึงรันproductionbuild/Browserต่อและผ่านครบscopeนี้ agentไม่ได้หยุดmanualprocessหรือทิ้งข้อมูลทดลองแทนเจ้าของ Backend242เป็นผลก่อนรอพอร์ต; รอบตรวจต่อแก้เฉพาะBrowserselectors/CSS/เอกสาร ไม่แก้Backendซ้ำ

## พฤติกรรมที่ implement

- `POST /api/v1/teams/me/leave` รับbody{} เลือกmembershipของactive actorเอง; `POST /api/v1/teams/me/members/{team_member_id}/remove` รับbody{} ให้เฉพาะหัวหน้าปัจจุบันถอดmemberทีมตน PathIDเป็นpositiveBIGINTstring
- ใช้session/student/Origin/session-boundCSRF/no-storeเดิม หัวหน้าต้องโอนตำแหน่งก่อนออกหรือถูกถอด ไม่เพิ่มTeam/Projectdelete
- ตั้งtransaction-localactor ล็อกTeam/recheckactorและtarget แล้วล็อกProjectถ้ามี ตรวจC-02ภายใต้Projectlockก่อนเรียก `v1_exit_team_member` เดิมให้ตรวจซ้ำและจัดassignees/history/membershipแบบatomic
- ถ้าจะทิ้งin_progressTaskไร้assigneeให้409MEMBER_EXIT_BLOCKED_BY_TASK ไม่ถอนบางงานก่อนยกเลิก ไม่เปลี่ยนTaskstatusหรือเลือกผู้รับผิดชอบใหม่เอง
- not_started/completedอาจเหลือ0assigneesจากการออกตามกฎเดิม ประวัติบันทึกด้วยSQLtriggerครั้งเดียว เก็บuser_id/assigned_at/unassigned_at แม้membershipถูกลบ
- หลังคะแนนแรกยังใช้exit-cleanup exceptionที่SQLอนุญาต แต่C-02ยังบังคับ ไม่ปลดล็อกTask/Milestoneทั่วไป
- บังคับTeamcardinalityและTaskactive-assignee deferredconstraintsก่อน204และจบtransactionก่อนตอบ สำเร็จไม่มีbody ไม่มีSet-Cookieหรือsessionrenewal
- หลังออกยังLoginได้แต่GETทีม/Project/memberlist/invitationhistoryทีมเดิมถูกปฏิเสธตามmembership ไม่ลบบัญชี/credential/Team/Project/Submissionเดิม
- UIเพิ่มconfirmationออกเองสำหรับmemberและถอดเฉพาะmemberสำหรับleader มีชื่อ+membershipIDของtarget; leaderเห็นคำอธิบาย/anchorไปโอนหัวหน้าก่อนออก
- UIยืนยัน204แบบstrict ไม่รับ200{}เป็นsuccess ไม่retryPOSTอัตโนมัติเมื่อผลไม่แน่นอน และให้GETreconcileแทน ล้างTeamcontextหลังออก; removeโหลดรายชื่อใหม่ ไม่มีpush/pollingไปเครื่องสมาชิกที่ถูกถอด

## ไฟล์ที่เปลี่ยนใน scopeนี้

| ไฟล์ | เหตุผล |
|---|---|
| `backend/team_api.py` | Emptybodymodel/pathvalidation/leave-remove204/errors |
| `backend/team_store.py` | Lock/recheck/C-02query/controlledexit/forcedconstraints ไม่เพิ่มrawDELETE |
| `backend/tests/test_team_membership_exit_api.py` | HTTP+PostgreSQL15tests รวมTaskhistory/firstEvaluationexception/rollback/authorization |
| `backend/tests/test_auth_security.py` | OpenAPI2pathsใหม่ success204และmethodexpectations |
| `backend/tests/team_api_direct_smoke.py` | Directappremove/leave204, Authretained/Team-Projectaccessrevoked/Projectpreserved |
| `frontend/src/features/teams/api.ts` | Strict204handlingแยกจากDTOcalls/exitclients/errorข้อความ |
| `frontend/src/features/teams/membership-exit-action.tsx` | Confirmation/cancel/pending/error/GETreconciliation |
| `frontend/src/features/teams/team-members.tsx` | Scopeปุ่มremove/leaveตามrosterและrefresh/leadertransferanchor |
| `frontend/src/features/teams/team-screen.tsx` | หลังleaveโหลดTeamcontextใหม่และnoticeในno-teamstate |
| `frontend/src/features/teams/teams.module.css` | Memberrow/confirmationlayout |
| `frontend/tests/membership-exit.spec.ts` | Browser10casesผ่านแล้ว รวมconfirmation/reconciliation/permission/session/errorfeedback |
| Contract/report/backlog/setup/handoff | Scope/หลักฐาน/ข้อจำกัด/จุดต่อกับMilestoneของเพื่อน |

SQLV1/RBAC/Auth/connectionpolicy/.env/dependencies/main/CORSและsourceSubmission/Milestone/Supabaseของเพื่อนไม่เปลี่ยน TeamUOWoverrideในBrowserharnessมีอยู่แล้วและexitใช้UOWนั้น ไม่เพิ่มnormalconnectionfallback

## ผลตรวจรอบพัฒนาและรอบตรวจต่อ

| ชุด | ผล / ขอบเขต |
|---|---|
| Offlinevalidation/security/DBboundary | PASS42tests / 0.581s ไม่ต่อDB |
| ExitHTTP+PostgreSQL | PASS15tests / 10.811s outerROLLBACK |
| FullBackendregression | PASS242tests / 53.318s = Auth65+Team37+Members18+Project32+TeamUpdate12+Transfer13+Exit15+Invitations24+DBboundary9+provisioning17 |
| DirectappASGIsmoke | PASS current_database=testDB, session_user=current_user=project_app; remove204/leave204, Auth200หลังleave/Team-Project404 และROLLBACKbaselinePASS |
| FreshV1readonlybaseline | PASS52functions/no differences/effectiveACL committed=false |
| DirectAuthruntime readonly | PASSproject_app/testDB |
| OpenAPIno-connectioncheck | PASS18paths, leave/removeมี204responses |
| Frontendlint/TypeScript | PASS หลังrunnerหยุดแล้ว รันเรียงลำดับไม่ชนgeneratedfiles |
| Productionbuildหลังเพิ่มexit | PASS หลังปรับCSSปุ่มยกเลิกแล้ว Next16.4.4 buildทุกrouteเดิมสำเร็จ |
| BrowserเฉพาะExit | PASS10/10 / 10.5s หลังแก้alertselectors |
| Browserfullsuiteรอบสุดท้าย | PASS73tests / ประมาณ1นาที = Auth5+Invitations12+Transfer7+Exit10+Project16+Members8+Team8+TeamUpdate7; metadata/ACL/rowsคืนbaseline, fixture_connections0 |
| Desktop/Mobile | ตรวจscreenshotsleaveDesktop/removal390pxMobileแล้ว ปุ่มยกเลิกอ่านชัด ไม่มีhorizontaloverflow |

Backendtestsใช้uniquefixturesและouterROLLBACKแยกconnectionจากmanualfixtureที่เปิดอยู่ ไม่หยุดหรือrollbackconnectionของผู้ใช้ Testsตรวจคืนmetadata/owners/ACL/rowcountsของinstalledbaseline; ไม่ถือเป็นการพิสูจน์multi-sessionconcurrency และไม่นับidentitysequencevaluesที่อาจเพิ่มแม้ROLLBACK

## หลักฐาน Task/สิทธิ์/rollback

- Businessrequestsใช้project_app มีdirectLOGINappsmokeแยก Ownerใช้เฉพาะเตรียมstaff/sessionfixturesตามแบบที่อนุมัติ ไม่มีsuperuserข้ามสิทธิ์positivebusinessrequest
- Task/Milestone/Submission/Committee/Evaluationเป็นDB-onlyphasefixturesผ่านSQLV1เดิมในconnectionเดียวกับHTTPUOW ไม่แก้หรือเรียกAPIของเพื่อนเพื่อเตรียมข้อมูล
- ทดสอบexitกับไม่มีProject, มีProject, pending/approved/revision และTasknot_started/completed/in_progressหลายassignees/คนสุดท้าย ครอบคลุมleaveและremoveในชุดหลัก
- ยืนยันhistoryuser/assigned_at/unassigned_at>=assigned_at ไม่มีhistoryซ้ำเมื่อrequestซ้ำไม่สำเร็จ และTaskstatusไม่ถูกเปลี่ยนเพื่อให้exitผ่าน
- หลังEvaluationแรก: completedTaskcleanupผ่านcontrolledexitได้; หากมีin_progressTaskที่เป้าหมายเป็นคนสุดท้ายยัง409และข้อมูลทั้งหมดคงเดิม
- จำลองprecheckC-02ผิดด้วยtestdouble: SQLhelperยังปฏิเสธ orphanedTask, APIคืนsanitized500และrollback ไม่ตีความP0001ทุกตัวเป็น409
- FailureหลังSQLถอนงาน/สร้างhistory/ลบmembershipแล้ว หรือขณะtransactioncompletion ยืนยันmembership/assignments/historyคืนครบ ไม่มี204ปลอม
- User/credential/Team/Projectคงอยู่และsessioncookieเดิมไม่เปลี่ยนหลังexit; G-12อ่านทีม/Project/memberlist/invitationhistoryหลังexitไม่ได้ Authยังใช้ได้
- Recheckหลังlockใช้testdouble ไม่ใช่realmulti-sessionconcurrency

### Browser integration ที่ตรวจต่อหลังพอร์ตว่าง

- Happy pathsใช้API→PostgreSQLจริง: memberออก204โดยยังAuth200/Team-Project404; leaderถอด204แล้วrosterใหม่ไม่มีtarget และsessionเดิมของtargetยังAuth200แต่เข้าทีม/Projectไม่ได้
- BrowserC-02ใช้mock409เพื่อพิสูจน์ข้อความ/คงconfirmation ไม่ได้สร้างTaskผ่านUIของเพื่อน; C-02และประวัติจริงเป็นBackend15testsข้างต้น
- Lost-responseทั้งleave/removeเรียกBackendจริงให้เปลี่ยนข้อมูลในouterfixturetransactionก่อนตัดresponse แล้วGETreconcileโดยไม่POSTซ้ำ แม้ยกเลิกconfirmationหลังresponseหายก็ยังมีทางตรวจข้อมูล
- ตรวจ200{}ที่ไม่ตรง204contractต้องเป็นerror ไม่รายงานsuccess; เมื่อGETreconcileล้มเหลวไม่ตีความว่าไม่มีทีม; CSRF/sessionและpendingใช้คำขอจริง
- ทุกBrowserwriteใช้TeamUOWoverrideกับouterROLLBACKเดิม ในfixturemodeอาจใช้ownerเตรียมstaffก่อนserveทุกrequestเป็นeffectiveproject_app; ไม่ใช่directLOGINapp ซึ่งพิสูจน์แยกด้วยsmokeแล้ว
- รอบแรก73casesมี67ผ่าน/6ไม่ผ่านเพราะglobalalertselectorจับNext.js route-announcerด้วย แก้testให้เลือกข้อความerrorที่ตรวจ หลังแก้Exit10/10ผ่าน แล้วfull73ผ่าน
- พบปุ่มยกเลิกถูกflexบีบจนคำไทยขึ้นหลายบรรทัด แก้CSSเฉพาะexitconfirmationให้cancelไม่หดและprimaryแบ่งพื้นที่ หลังแก้รันlint/TypeScript/buildและfull73ใหม่ผ่าน พร้อมดูภาพซ้ำ
- เคยรันlint/TypeScriptพร้อมBrowserrunnerแล้วชนgeneratedfilesที่กำลังสร้างใหม่ เป็นการตรวจที่ล้มเหลวชั่วคราวจากลำดับรัน ไม่แก้config/dependenciesเพื่อกลบปัญหา รันเรียงหลังrunnerหยุดแล้วผ่าน

## งานตรวจต่อ — เสร็จแล้ว

1. ตรวจพอร์ต3000/8001ว่างก่อนเริ่ม ไม่บังคับหยุดmanualservers
2. Productionbuild/Browserfixtureรุ่นใหม่และfull73ผ่าน ทั้งExit10และregressionเดิม ตรวจคืนmetadata/ACL/rowsและfixtureconnection0
3. ตรวจภาพและแก้ปุ่มcancelพร้อมทดสอบซ้ำบนsourceสุดท้ายแล้วผ่าน
4. อัปเดตContract/Backlog/handoff/setupด้วยผลใหม่ แยกBackend242รอบก่อนรอพอร์ตกับBrowser73รอบตรวจต่อ ไม่ใช้Browser63เก่ารับรองUIExit

## จุดต่อกับเพื่อน

- รักษาexitroutesและTeamstoreขณะรวมsource อย่าoverwriteด้วยTeamfilesในsnapshotpeerเก่า รักษาOpenAPI/UOWoverridesทุกfeature
- Milestone/TaskAPIของเพื่อนต้องตรวจmembershipทุกrequestตามG-12 และรองรับcompleted/not_startedTaskที่เหลือ0assigneesจากexitได้ตามV1 ประวัติมีuser_idจึงยังอยู่หลังmembershipถูกลบ
- ไม่ให้peerUIเปลี่ยนTaskstatusหรือassignคนอื่นอัตโนมัติเพื่อหลบ409; firstEvaluationcleanup exceptionใช้เฉพาะcontrolledexitนี้ ไม่ปลดล็อกTaskAPIทั่วไป
- ปัญหาB01–B03ใน [บันทึกเพื่อน](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ยังไม่ได้แก้แทนเพื่อน และSupabaseยังเป็นอนาคต

สถานะscopeนี้: implemented/verifiedครบAPI/UIตามContract แต่ไม่ใช่freshinstall/runtimeCOMMIT/HTTPS/LAN/UATหรือmulti-sessionconcurrency จึงไม่ปิดงานหลักเพิ่ม คงDone5/20=25% และP09/P13ยังInProgress ไม่มีCommit/Push
