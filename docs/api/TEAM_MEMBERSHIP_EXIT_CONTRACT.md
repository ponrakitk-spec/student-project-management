# Membership leave / removal — Approved and verified

วันที่ 2026-11-14 · P09/P13/P15/P16/P17 · **ผู้ใช้ตอบ “ทำทั้งออกและถอดตามร่าง” แล้ว; API/UI implemented และตรวจรับครบscopeนี้** ดู [รายงาน](../progress/TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md)

ขอบเขตที่ยืนยันคือทั้งออกเองและหัวหน้าถอดmember ต่อจาก [Leader transfer](TEAM_LEADER_TRANSFER_CONTRACT.md) การถอนassigneesใช้SQLV1เดิม ไม่สร้างหรือแก้Milestone/TaskAPIของเพื่อน

## กฎที่มีอยู่แล้ว

อ้าง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) C-02/G-03/G-12/ข้อยกเว้นหลังคะแนนแรก, [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) `v1_exit_team_member(bigint)`, `v1_record_unassignment`, `v1_task_assignee_guard` และ [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql)

- member ออกจากทีมตนได้ หัวหน้าปัจจุบันถอด member ในทีมตนได้; membership ที่เป็น leader ต้องโอนตำแหน่งก่อนออก/ถูกถอด ไม่ลบทีมเพื่อข้ามข้อจำกัดนี้
- Actorมาจากactive session ผู้ถูกถอดต้องเป็นmembershipปัจจุบันในทีมเดียวกัน ไม่รับactor/team/user/roleจากclientเพื่อกำหนดสิทธิ์
- เรียก `public.v1_exit_team_member(membership_id)` เดิม ถอนtask_assigneesก่อนลบteam_membersในtransactionเดียว; ไม่เพิ่มrawDELETE/UPDATEหรือownerfallback
- C-02: หากTaskใดเป็นin_progressและเป้าหมายเป็นผู้รับผิดชอบคนสุดท้าย ให้ปฏิเสธทั้งoperation ไม่ถอนบางงานแล้วออกทีมบางส่วน
- not_started/completed อาจเหลือผู้รับผิดชอบ0จากการออก/ถอดที่อนุญาตได้ ไม่เปลี่ยนTaskstatus/due dateหรือเลื่อนงานอัตโนมัติ
- SQLบันทึกtask_assignment_historyเมื่อถอนassigneeจริงและTaskยังมีอยู่ เก็บuser_id/assigned_at/unassigned_atเดิมตามSchema ไม่สร้างmembership-historyตารางใหม่หรือแทรกhistoryซ้ำในBackend
- หลังEvaluationแรกยังมีข้อยกเว้นถอนassigneeจากการออก/ถอดตามcontrolledworkflowนี้ แต่C-02ยังบังคับ ไม่ปลดล็อกTask/Milestoneทั่วไปเอง
- SQL exitไม่มีmetadata phase gate ไม่เพิ่มกฎห้ามออกตอนpending/approvedเอง; การเพิ่มสมาชิกใหม่กลับเข้าทีมยังใช้C-07เดิม
- ลบเฉพาะmembership/assignmentsที่SQLอนุญาต ไม่ลบบัญชีผู้ใช้/Authcredential/Project/Submission/ประวัติเดิม; Sessionยังใช้ได้แต่สิทธิ์จากสมาชิกภาพสิ้นสุด

## HTTP ที่ยืนยันและ implement แล้ว

ใช้session/Origin/session-boundCSRFเดิม ทุกresponse no-store IDsเป็นpositiveBIGINTstringsตามpatternTeam/Invitationเดิม ไม่เพิ่มmethodCORSใหม่

| Operation | Method/path | Request / response |
|---|---|---|
| ออกเอง | `POST /api/v1/teams/me/leave` | body `{}` เท่านั้น เลือกmembershipของactorฝั่งserver; สำเร็จ204ไม่มีbody |
| หัวหน้าถอดmember | `POST /api/v1/teams/me/members/{team_member_id}/remove` | body `{}` เท่านั้น pathIDคือmembership.idจากรายชื่อทีมตน; สำเร็จ204ไม่มีbody |

หลังออกหรือถูกถอด GET /teams/me ของคนนั้นตอบ404TEAM_NOT_FOUND; GET /projects/me ตอบ404TEAM_NOT_FOUND; สมาชิกภาพไม่ให้สิทธิ์อ่านรายชื่อ/ประวัติคำเชิญทีมเดิมอีก แต่ GET /auth/me ยังตอบ200หากsessionใช้ได้ ไม่logoutหรือยกเลิกบัญชีอัตโนมัติ

ไม่รับdescription/reason/TaskIDsหรือfieldเสริมใหม่ ไม่มีการย้ายสมาชิกไปทีมอื่นในoperationเดียว ไม่รับbodyที่แอบเลือกmembershipอื่นในleave

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionขาด/ผิด/หมดอายุ/ถูกยกเลิก |
| 403 TEAM_ACCESS_FORBIDDEN | advisor/coordinatorเรียกstudent endpoints |
| 404 TEAM_NOT_FOUND | actorไม่มีทีมปัจจุบัน |
| 403 TEAM_MEMBER_REMOVAL_FORBIDDEN | actorไม่ใช่หัวหน้าปัจจุบัน แต่พยายามใช้remove |
| 404 TEAM_MEMBER_NOT_FOUND | targetไม่มีในทีมตน/ถอนหรือเปลี่ยนmembershipแล้ว ไม่เปิดเผยข้อมูลทีมอื่น |
| 409 TEAM_LEADERSHIP_TRANSFER_REQUIRED | membershipเป้าหมายยังเป็นleader รวมleaderออกเอง ต้องโอนก่อน |
| 409 MEMBER_EXIT_BLOCKED_BY_TASK | จะทิ้งTaskin_progressไร้ผู้รับผิดชอบ; ไม่ส่งTaskID/ชื่อหรือrawSQLในerror |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | ไม่ผ่านนโยบายคำขอเขียน |
| 422 VALIDATION_ERROR | pathID/JSONผิด bodyไม่ใช่{}หรือfieldsเกิน |
| 500 INTERNAL_ERROR | storage/transaction/privilege/triggererrorที่จำแนกไม่ได้; sanitized |

ลำดับตรวจremove: Auth/CSRF/student → ทีมของactor → Team lock/recheckหัวหน้า → targetในทีม → leader restriction → Project lock/C-02 → controlledexit/forcedconstraints → transactioncompletion → 204

ลำดับleaveเหมือนกันแต่targetคือmembershipของactorที่อ่านใหม่หลังTeam lock และไม่ต้องเป็นหัวหน้า; หากยังเป็นleaderปฏิเสธ409

ถ้าเคยสำเร็จแล้วส่งซ้ำ leaveอาจ404TEAM_NOT_FOUND และremoveอาจ404TEAM_MEMBER_NOT_FOUND ไม่มีidempotencyguarantee จึงต้องGETตรวจผลเมื่อnetworkไม่แน่นอน ไม่automaticPOSTretry

## แนวทางtransaction / เชื่อมTaskของเพื่อน

1. ใช้TeamUOWเดิมและDBguard ตั้งtransaction-localactorจากactive session ล็อกTeamแล้วrecheckสมาชิกภาพ/role/target
2. หากมีProject ล็อกProjectก่อนตรวจC-02 การเปลี่ยนTaskstatus/assigneeตามV1ต้องใช้Project lockร่วมกัน ห้ามใช้precheckที่ไม่มีlockเป็นด่านสุดท้าย
3. ตรวจว่ามีin_progressTaskที่เป้าหมายเป็นassigneeคนเดียวหรือไม่ภายใต้Project lockเพื่อคืน409ที่จำแนกได้ ไม่เปิดเผยรายละเอียดTask
4. เรียกSQLexitเดิมให้ล็อกProject→MilestonesASC→TasksASC ตรวจC-02ซ้ำและถอนงาน/บันทึกhistory/ลบmembershipแบบatomic บังคับdeferredconstraintsที่เกี่ยวข้องก่อนตอบสำเร็จ
5. ไม่แปลงP0001/42501ทั้งหมดเป็นbusiness409ด้วยข้อความtrigger หากprecheckไม่ครอบคลุม/SQLfailไม่รู้จักให้rollbackและsanitized500 ไม่มีเพิ่มgrantเพื่อทำFORUPDATEเอง

Milestone/Task UI/APIยังเป็นของเพื่อน Scopeนี้แตะเพียงSQLexistingexitและqueryตรวจC-02 ไม่ย้ายTask/เพิ่มassignmentAPI/เลือกคนรับงานแทนให้อัตโนมัติ เมื่อถูกบล็อกให้ผู้ใช้จัดการผู้รับผิดชอบผ่านworkflowที่ทีมยืนยันแล้วก่อนลองใหม่

## UI ที่ implement และตรวจ Browserแล้ว

- memberเห็น “ออกจากทีม” พร้อมconfirmationว่าจะเสียสิทธิ์ข้อมูลทีม/Projectหลังสำเร็จ หัวหน้าต้องโอนก่อน จะแสดงคำอธิบาย/ทางไปส่วนโอนหัวหน้า ไม่ใช้ปุ่มลบทีมทดแทน
- หัวหน้าเห็น “ถอดสมาชิก” เฉพาะแถวmemberที่ไม่ใช่ตน แสดงชื่อ+membershipIDของเป้าหมายและคำเตือนผลต่อการเข้าถึงก่อนยืนยัน; memberไม่มีเครื่องมือนี้
- ยกเลิกก่อนส่งไม่เขียนข้อมูล; pendingปิดconfirm/cancelและป้องกันกดซ้ำ
- leaveสำเร็จโหลดทีม/Projectcontextใหม่ แสดงว่าไม่มีทีมและยังLoginอยู่ ไม่คงcacheรายชื่อ/Projectเดิมบนหน้าปัจจุบัน
- removeสำเร็จโหลดรายชื่อใหม่ เมื่อผู้ถูกถอดทำrequest/refreshต้องไม่ได้สิทธิ์ทีมเดิม ไม่เพิ่มpushnotification/real-timepollingที่ยังไม่ยืนยัน
- C-02บล็อกแสดงข้อความให้จัดผู้รับผิดชอบอื่นก่อน ไม่รายงานว่าออก/ถอดสำเร็จ และไม่เปลี่ยนTaskstatusเพื่อให้ผ่าน
- Responseหาย/500/204ผิดรูปแบบ: ไม่retryPOSTอัตโนมัติ ให้GETตรวจทีม/รายชื่อก่อน; การตรวจไม่สำเร็จต้องแสดงerror ไม่ตีความว่าออกแล้ว

## ขอบเขตไฟล์ implementation

- `backend/team_api.py`, `backend/team_store.py`: leave/remove/targetscope/C-02precheck/controlledexit/204/errors
- testsเฉพาะexitใหม่, OpenAPIexpectations/directappsmoke และfixturesที่SQLV1ควบคุม ไม่ใช้normalUOW fallback
- `frontend/src/features/teams/` และBrowsertests: confirmation/action/refresh/permissionloss/uncertainoutcome
- Contract/report/backlog/LOCAL_SETUP/handoffตามผลจริง ไม่เปลี่ยนSQL/RBAC/Requirements/.env/dependencies/main/CORSหรือsourceเพื่อนโดยพลการ

## เกณฑ์ทดสอบ

1. memberออกเอง/leaderถอดmemberในทีมตนสำเร็จ204 ไม่มีmembership/assigneesค้าง Team/Project/users/credentialคงเดิม ไม่มีleaderถูกลบ
2. คนที่ออกยังAuthได้แต่Team/Project/memberlist/invitationhistoryทีมเดิมถูกปฏิเสธตามContract; actor/targetspoof/cross-team/staff/memberremoveไม่ได้
3. ไม่มีTask, not_started, completed, in_progressมีassigneeหลายคน/คนสุดท้าย: ผลC-02และhistoryถูกต้อง ไม่มีpartialdeleteหรือstatusเปลี่ยนเอง
4. firstEvaluationexitexception, historytimestamps/user_idและassigned_atถูกต้อง ไม่มีhistoryซ้ำจากrequestที่ไม่สำเร็จ ไม่ข้ามDBguardหรือใช้ownerทำpositivebusinessrequest
5. staleactor/targetหลังlock, forceddeferredchecks, failureหลังถอนงาน/หลังลบmembership/transactioncompletionต้องrollbackข้อมูลและhistoryทั้งหมด SQLunknownerrorsไม่รั่ว
6. Browserconfirmation/cancel/pending/member/leader/no-team/Auth/CSRF/409/204/lostresponse/GETfailure/DesktopMobile โดยครอบทุกwriteด้วยouterROLLBACK

ทดสอบเฉพาะ student_project_management_v1_test ตรวจชื่อก่อนทุกชุด ใช้Transaction/ROLLBACKและตรวจmetadata/ACL/rowsคืนbaseline ไม่รวมsequencevalues ไม่COMMITfixtureเพื่อทดสอบmulti-sessionเอง

## สถานะตรวจรับล่าสุด

- V1readonlybaseline52functions/effectiveACL/directappผ่าน; Backend242testsรวมExit15 และdirectappsmokeออก/ถอด204ผ่าน พร้อมROLLBACK/baselineproof
- หลังตรวจพบพอร์ตmanual3000/8001ว่าง รันproductionbuild/lint/TypeScriptแบบเรียงลำดับและBrowserเต็มชุด73กรณีผ่าน รวมExit10กรณี ตรวจDesktop/Mobileแล้ว พร้อมROLLBACKcleanup/fixture_connections0 ไม่หยุดmanualprocessแทนเจ้าของ
- BrowserC-02และบางfailureใช้mockHTTP ส่วนC-02/Taskhistoryจริงพิสูจน์ในBackendSQLtests ไม่ใช่multi-sessionconcurrencyหรือUATทั้งระบบ อ่านข้อจำกัดในรายงาน
