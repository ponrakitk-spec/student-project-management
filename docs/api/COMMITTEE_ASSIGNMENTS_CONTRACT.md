# Coordinator / Committee assignments — Approved contract

วันที่ 2026-11-14 · ผู้ใช้ยืนยัน “ใช้ร่างครบ: ดูรายการ/เพิ่ม/เปลี่ยน/ถอด (แนะนำ)” ครอบคลุม API/DTO/errors/UI ด้านล่างสำหรับ Coordinator รอบแรก ไม่ใช่การอนุมัติ Vote/Evaluation API หรือแก้ Submission/Milestone ของเพื่อน

## กฎ V1 ที่ยืนยันแล้ว

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) 4.2/4.4/4.5/4.6 และ [SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) `v1_committee_assignment_guard`, `v1_appoint_committee`, `v1_replace_committee`, `v1_remove_committee`

- Coordinator เห็น Project หลังมี Submission ที่อาจารย์อนุมัติ และแต่งตั้งกรรมการได้หลังมี approved submission เช่นเดียวกับ SQL เดิม ใช้ EXISTS approved ไม่เพิ่มเงื่อนไขว่าต้องเป็นรอบล่าสุด
- กรรมการต้องเป็น users.role=advisor และไม่ใช่ accepted advisor ของ Project นั้น; ห้ามซ้ำ advisor ใน Project เดียวกัน
- ต้องมีอย่างน้อย3คนก่อน Vote แรก ไม่บังคับว่าการเพิ่มกรรมการแต่ละ HTTP request ต้องเพิ่มครบ3พร้อมกัน และไม่มี max3ในV1
- หลังมี Vote แรกของ Project ห้ามเพิ่ม/เปลี่ยน/ถอดรายชื่อถาวร ไม่ปลดล็อกเมื่อมี Submission รอบใหม่
- ลำดับรายชื่อ assigned_at ASC, id ASC; assigned_by/assigned_at/project_id immutable; ใช้ assignment ID สำหรับเปลี่ยน/ถอด และ advisor user ID สำหรับแต่งตั้ง
- G-12 ใช้401เมื่อไม่มีsession,404เมื่อไม่เห็น/ไม่มีresource,403เมื่อเห็นแต่ทำไม่ได้ ไม่เปิดรายชื่อผู้ใช้ทุกบทบาท อีเมล รหัสผ่าน หรือ Vote/Evaluation รายบุคคลใน DTO รอบนี้
- หลังแต่งตั้ง Team/accepted Advisor มีสิทธิ์อ่านรายชื่อกรรมการตาม G-12 แต่ไม่เห็นการเชื่อมโยงกับ Vote รายบุคคล จุดอ่านสำหรับสองบทบาทนี้ยังต้องกำหนดในรอบที่เกี่ยวข้อง ไม่ถือว่าเสร็จจากหน้าจอCoordinator

## ขอบเขต API ที่ยืนยันสำหรับ Coordinator รอบแรก

ใช้ session8ชั่วโมง/Origin/CSRF เดิมที่ localhost:3000→localhost:8000 ไม่รับ actor/role/assigned_by/time จาก client IDs ทุกชนิดเป็น positive BIGINT strings

| Method / path | Request | Success ที่เสนอ |
|---|---|---|
| GET `/api/v1/coordinator/projects` | ไม่มี body | 200 `{data:[project...]}` เฉพาะ Project ที่มี approved submission; ว่างเป็น[] |
| GET `/api/v1/coordinator/projects/{project_id}/committee` | ไม่มี body | 200 `{data:{project,roster_locked,assignments:[...]}}` เมื่อเห็น Project; รายชื่อว่างเป็น[] |
| GET `/api/v1/coordinator/projects/{project_id}/committee-candidates` | ไม่มี body | 200 `{data:[{id,full_name}]}` advisor ที่ไม่ใช่acceptedadvisor/ไม่อยู่ในroster ปัจจุบัน |
| POST `/api/v1/coordinator/projects/{project_id}/committee` | `{advisor_id:"..."}` เท่านั้น | 201 `{data:assignment}` เพิ่มหนึ่งคน |
| PATCH `/api/v1/coordinator/projects/{project_id}/committee/{assignment_id}` | `{advisor_id:"..."}` เท่านั้น | 200 `{data:assignment}` เปลี่ยนคนในassignmentเดิม; ID/assigned_by/assigned_atเดิม |
| POST `/api/v1/coordinator/projects/{project_id}/committee/{assignment_id}/remove` | `{}` เท่านั้น | 204 empty body ไม่ลบ user/Project |

ใช้POSTสำหรับremoveตามรูปแบบสมาชิกทีมเดิม ไม่เพิ่มCORSmethodเองในรอบนี้

DTO ที่ยืนยัน:

- `project`: `{id,name,description,team:{id,name}}`; รายการProjectเรียงid DESCเพื่อคงผลหลังrefresh ไม่คืนfiles/submissions/votes/evaluations/memberlist
- `assignment`: `{id,advisor:{id,full_name},assigned_at}` ใช้เวลาแบบtimezone-awareตามpatternเดิม; ไม่คืนassigned_byที่ไม่จำเป็นต่อUI
- candidateคืนเฉพาะid/full_name การแทนด้วยadvisorเดิมหากส่งAPIตรงยังต้องตรวจrole/phase/lock ไม่ใช้no-opข้ามroster lock
- ทุกresponseมีno-store ไม่เก็บsessionหรือข้อมูลโครงงานในlocalStorage และไม่มีpagination/search/dashboardmetricsในรอบแรก

## Errors ตาม Contract

| HTTP / code | สถานการณ์ |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionไม่มี/หมดอายุ/ถูกยกเลิก |
| 403 COMMITTEE_ACCESS_FORBIDDEN | student/advisorเรียกพื้นที่Coordinator |
| 404 PROJECT_NOT_FOUND | Projectไม่มีหรือยังไม่มีapprovedsubmissionตามG-12 |
| 404 COMMITTEE_ASSIGNMENT_NOT_FOUND | assignmentไม่มี/อยู่Projectอื่น; ไม่เปิดว่าอยู่ที่ใด |
| 404 COMMITTEE_ADVISOR_NOT_FOUND | userIDไม่มีหรือไม่ใช่advisor |
| 409 COMMITTEE_ROSTER_LOCKED | มีVoteแรกแล้ว แม้แก้เป็นค่าเดิม |
| 409 PROJECT_ADVISOR_INELIGIBLE | เลือกacceptedadvisorของProject |
| 409 COMMITTEE_ADVISOR_ALREADY_ASSIGNED | advisorอยู่ในrosterคนละassignmentแล้ว |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | writeผิดนโยบายAuthเดิม |
| 422 VALIDATION_ERROR | IDs/body/ชนิด/fieldsเกินผิด ห้ามเลือกactor/role/เวลา |
| 500 INTERNAL_ERROR | storage/permission/transaction failureที่จำแนกไม่ได้; sanitized |

## SQL และ transaction

1. ยืนยันactive userจากsessionในUOWเดียวกับoperationและrole=coordinator; ไม่เชื่อcustomGUCจากBrowser
2. อ่านProjectตามG-12ก่อนใช้ID และตั้งtransaction-localactorจากsession
3. ขอProjectlockผ่านhelperเดิม แล้วตรวจvisibility/roster lock/target/advisorใหม่หลังรอlock โดยไม่มีdirectUPDATE/DELETEเพิ่ม
4. ใช้ `v1_appoint_committee(project_id,advisor_id)`, `v1_replace_committee(assignment_id,advisor_id)`, `v1_remove_committee(assignment_id)` เท่านั้น
5. ตรวจconstraintsก่อนตอบสำเร็จและให้UOWจบก่อนส่งresponse ไม่แปลงทุกP0001/42501เป็นbusiness409/403 ต้องจำแนกprecheck/constraintที่รู้จักโดยไม่รั่วSQL
6. SQLguardเดิมเป็นชั้นตรวจซ้ำ ไม่แก้phase/privileges/functions/Schemaเมื่อพบpermissiondenied ให้รายงานSQLSTATE/เส้นทางที่พบก่อน

## UI ตาม Contract

- `/coordinator/projects` แสดงเฉพาะรายการProjectที่Coordinatorเห็น เลือกแล้วเปิด `/coordinator/projects/{id}/committee`
- หน้าcommitteeแสดงชื่อทีม/Projectและrosterพร้อมสถานะ “แก้รายชื่อได้” หรือ “ล็อกหลังเริ่มลงมติ” ไม่แสดงVoteรายบุคคลในรอบนี้
- เลือกอาจารย์จากรายชื่อ ไม่พิมพ์emailหรือสร้างบัญชีอาจารย์จากหน้านี้
- เพิ่มหนึ่งคน, เปลี่ยนคน, ถอดคน มีconfirmสำหรับเปลี่ยน/ถอด และป้องกันsubmitซ้ำ; แสดงจำนวนและแจ้งว่าต้องมีอย่างน้อย3ก่อนเริ่มVote ไม่สร้างปุ่มVoteเอง
- เมื่อผลwriteไม่แน่นอนให้GETreconcileก่อน ไม่retryPOST/PATCHอัตโนมัติ; 409lockedโหลดสถานะใหม่; refreshยังเห็นข้อมูลจากserver
- ใช้featuresแยก `src/features/committee-assignments` และ routeในsrc/app ตามโครงเดิม ไม่แก้Submission/MilestoneUIของเพื่อน

## บัญชี Coordinator

เสนอใช้CLIบนเครื่องโดยowner เช่นเดียวกับadvisorเดิม: defaultDRY RUN/ROLLBACK, passwordผ่านgetpassไม่รับในcommand/env/ไฟล์/แชท, hashด้วยpolicyเดิม, สร้างเฉพาะบัญชีใหม่ role=coordinator และcredentialในtransactionเดียว ไม่แก้role/รหัสบัญชีเดิม

การเตรียมเครื่องมือ/ทดสอบfixtureทำได้ก่อน ยังไม่สร้างบัญชีถาวรจนผู้ใช้ระบุชื่อ/emailผ่านช่องทางที่เลือกและอนุมัติบันทึกเฉพาะบัญชี ไม่มีเพิ่มหน้าสมัครที่ให้เลือกcoordinatorเอง

## แผนตรวจรับหลังยืนยัน Contract

- HTTP+PostgreSQL: coordinatorอ่านeligibleProject/roster/candidates เพิ่ม/แทน/ถอดได้; assignmentmetadataimmutable/ordering/unique/role/acceptedadvisorถูกต้อง; ก่อนapproved404และany-roundapprovedตามSQLเดิม
- >=3จำเป็นก่อนVoteแรกเท่านั้น; สร้างroster1/2คนชั่วคราวได้; voteแรกล็อกทั้งสามwriteถาวร รวมnoopและnewsubmissionround
- Security: noAuth/roleผิด/CSRF/Origin/expiry/revocation, spoofedactor/invalidIDs/foreignassignment/privacy/sanitizederrors
- Atomicity: injectfailureหลังSQL/UOWcompletionและforceconstraints; rollbackคืนroster/metadata; ไม่COMMITtestdata
- Fixtures: ownerเตรียมstaffและcredentialsเฉพาะtransaction; businessoperationsเป็นapp ใช้DB-onlysubmission/file/reviewfixturesตามV1 ไม่แก้หรือเรียกAPIเพื่อนเพื่อseed
- ทุกAuth/Project/Invitation/Committee UOWในการทดสอบต้องใช้connectionfixtureที่ตั้งใจเดียวกัน ห้ามหลุดไปproductionconnectionแบบB01; Browserrunnerต้องรองรับUOWใหม่ก่อนPOST
- Directappsmoke/Backendregression/BrowserDesktopMobile/lint/TypeScript/build รายงานแยกrealDB/fixture/mockresponses

สถานะตรวจรับ: API/UIครบscopeCoordinatorตามContract Backend332/Browser81รวมCommittee8/lint/TypeScript/buildผ่าน พร้อมROLLBACK/fixture_connections0 ตาม [รายงาน](../progress/COMMITTEE_ASSIGNMENTS_IMPLEMENTATION_REPORT.md) ผู้ใช้เลือก [กรอกบัญชีcoordinatorผ่านCLIเอง](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) ไม่สร้างบัญชีถาวรแทน ไม่เพิ่มdependencies และไม่ถือว่าVote/EvaluationหรือTeam/AdvisorrosterUIเสร็จ
