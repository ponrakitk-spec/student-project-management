# Team leader transfer — Approved and implemented

วันที่ 2026-11-14 · P09/P15/P16/P17 · **ผู้ใช้ตอบ “เริ่มโอนหัวหน้าก่อนตามร่าง” แล้ว; implemented/tested** ดู [รายงานผล](../progress/TEAM_LEADER_TRANSFER_IMPLEMENTATION_REPORT.md)

หลัง Team/Project metadata update เสร็จ ผู้ใช้ยืนยันให้ทำเฉพาะโอนหัวหน้าก่อน งานออก/ถอดสมาชิกมีผลต่อ Task/assignee ตาม C-02 จึงยังไม่อยู่ใน scopeนี้ และยังต้องตรวจร่วมกับ Milestone ของเพื่อนก่อนพัฒนาส่วนนั้น

## กฎ V1 ที่มีอยู่แล้ว

อ้าง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) G-03/G-12/transaction rules, [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) `v1_transfer_team_leader(bigint,bigint)`/`v1_team_members_guard`/`v1_team_final_cardinality` และ [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql)

- ผู้กระทำต้องเป็นหัวหน้าทีมปัจจุบัน เป้าหมายต้องเป็นสมาชิกอีกคนในทีมเดียวกัน ไม่ใช่ตนเอง
- โอนแล้วหัวหน้าเดิมเป็น member สมาชิกที่เลือกเป็น leader; ไม่ลบสมาชิก ไม่เปลี่ยน users.role, team_members.id/team_id/user_id หรือ Project created_by
- SQL helper รับ team ID กับ **user ID ของผู้รับ** ไม่ใช่ membership ID; Backendต้อง lookup membershipเป้าหมายภายใต้team lockก่อนแปลงเป็นuser ID
- ล็อก Team และ recheck actor/target ภายใต้ lock; ไม่ให้ direct UPDATE role เพิ่ม ใช้ controlled function/EXECUTE เดิม ตั้ง actor จาก active session เท่านั้น
- ต้องมีสมาชิกอย่างน้อยหนึ่งคนและหัวหน้าพอดีหนึ่งคนเมื่อ transactionจบ; defer cardinality ระหว่างเปลี่ยนบทบาทสองแถว แล้วบังคับ IMMEDIATE ก่อนตอบสำเร็จ
- V1 transfer helper/UPDATE role guard ไม่มี metadata phase gate ไม่เพิ่มกฎห้ามโอนระหว่างรอตรวจ/หลังอนุมัติเอง
- สิทธิ์หัวหน้าสำหรับคำขอหลังโอนต้องอิงสมาชิกภาพปัจจุบัน เช่นเพิ่มสมาชิก แก้ Team/Project และส่ง/ยกเลิก invitation ตามกฎเดิม ประวัติผู้สร้าง/ผู้ส่งเดิมไม่ถูกเขียนทับ
- ไม่แก้ Task/assignee ในการโอนหัวหน้าอย่างเดียว ไม่ออก/ถอดสมาชิกหรือรวมงานเพื่อน

## HTTP ที่ยืนยันและ implement แล้ว

`POST /api/v1/teams/me/leader` ใช้ active session/Origin/session-bound CSRF เดิม ทุกresponse no-store

```json
{"team_member_id":"202"}
```

- IDเป็นstringรูปแบบpositiveBIGINTเช่นpatternAPIคำเชิญเดิม ไม่รับ JSON number/fieldsอื่น ไม่รับteam/user/actor/roleที่clientเลือกมาเพื่อข้ามการตรวจสิทธิ์
- team_member_idมาจาก `id` ของ [GET /teams/me/members](TEAM_MEMBERS_CONTRACT.md); จำกัดเป็นสมาชิกทีมของactorที่เป็นหัวหน้าในขณะทำรายการ
- สำเร็จ200หลัง transactionจบ คืนCurrentTeamDTOเดิม id/name/description/membership ของ **ผู้เรียก** โดย membership.role เป็น `member` หลังโอน membership.idยังเดิม
- ใช้GET /teams/me/membersเดิมโหลดรายชื่อ/บทบาทใหม่ ไม่เพิ่ม user directory/email หรือข้อมูลทีมอื่น และไม่เปลี่ยน responseของGETเดิม

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionไม่มี/ผิด/หมดอายุ/ถูกยกเลิก |
| 403 TEAM_ACCESS_FORBIDDEN | advisor/coordinator เรียกstudent endpointนี้ |
| 404 TEAM_NOT_FOUND | actorไม่มีทีมปัจจุบัน |
| 403 TEAM_LEADER_TRANSFER_FORBIDDEN | actorไม่ใช่หัวหน้าปัจจุบัน รวมกรณีเสียสิทธิ์ระหว่างรอlock |
| 404 TEAM_MEMBER_NOT_FOUND | ไม่พบmembershipเป้าหมายในทีมตน/ถูกถอนหรือเปลี่ยนmembershipไปแล้ว ไม่เปิดเผยข้อมูลทีมอื่น |
| 409 LEADER_TARGET_INVALID | เลือกตนเองหรือเป้าหมายไม่ใช่memberที่รับการโอนได้ |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | คำขอเขียนไม่ผ่านนโยบายเดิม |
| 422 VALIDATION_ERROR | ID/JSON/fieldsผิด |
| 500 INTERNAL_ERROR | configuration/SQL/privilege/transactionfailureที่จำแนกไม่ได้; sanitized |

ไม่แปลง P0001/42501 ทุกกรณีจากข้อความtriggerเป็นbusiness error ไม่ใช้ownerหรือเพิ่มgrantเพื่อข้ามปัญหาสิทธิ์

## UI ที่ยืนยันและ implement แล้ว

- เพิ่มส่วนโอนหัวหน้าใน `/teams` เฉพาะหัวหน้า ใช้รายชื่อสมาชิกเดิม แสดงชื่อและให้เลือกเฉพาะสมาชิกอื่นที่เป็นmember
- เมื่อไม่มีผู้รับที่เลือกได้ ให้แจ้งว่าต้องมีสมาชิกอีกคน ไม่สร้างบัญชี/เพิ่มสมาชิกอัตโนมัติ
- แสดงชื่อผู้รับและคำอธิบายว่าตนจะเป็นmemberก่อนกดยืนยัน มีปุ่มยืนยัน/ยกเลิก ไม่ใช้การเลือกชื่อแล้วเปลี่ยนสิทธิ์ทันที
- ปิดsubmit/cancelระหว่างpending ป้องกันกดซ้ำ หลังสำเร็จอ่านทีม/รายชื่อใหม่และซ่อนเครื่องมือหัวหน้าตามสิทธิ์ปัจจุบัน
- ไม่automatic POST retry เมื่อผลเครือข่ายไม่แน่นอน ให้GETตรวจบทบาท/รายชื่อก่อน การมีconfirmationไม่ใช่idempotency guarantee
- ไม่เพิ่มปุ่มออก/ถอดสมาชิก/ลบทีมใน scopeโอนหัวหน้าอย่างเดียว

## ขอบเขตไฟล์ implementation

- `backend/team_api.py`, `backend/team_store.py`: input/route/authorization/controlled transfer/DTO/errors
- testsเฉพาะtransferใหม่, `backend/tests/test_auth_security.py` และ direct app smoke: method/path/role/transactionproof
- `frontend/src/features/teams/` กับ Browsertestsเฉพาะtransfer: selection/confirmation/refresh/stale roles/network
- เอกสารContract/implementationreport/backlog/handoff; Browserharnessใช้TeamUOWoverrideเดิม หากไม่มีUOWใหม่ไม่เพิ่มconnection

ไม่เปลี่ยนSQL/RBAC/Requirements/.env/connectionpolicy และSubmission/Milestone/Supabaseของเพื่อน ไม่มีCommit/Pushโดยไม่ได้รับอนุญาต

## เกณฑ์ทดสอบ

1. leaderโอนให้memberได้ มีleaderพอดี1คน, membership IDsและProject created_byคงเดิม, oldleaderกลายเป็นmember
2. oldleaderเสียสิทธิ์เพิ่มสมาชิก/แก้metadata/ส่งหรือยกเลิกinvitationตามactorปัจจุบัน newleaderใช้สิทธิ์เดิมได้; staff/member/outsider/spoofทำไม่ได้
3. ไม่พบทีม/เป้าหมาย, self target, stale membership, ชื่อซ้ำเลือกจากIDได้, BIGINTstringprecision/invalidpayload/unknownfieldsไม่เผยข้อมูลลับ
4. recheckหลังlock/deferredvalidationก่อนตอบสำเร็จ/rollbackเมื่อแก้บทบาทแล้วfailureหรือtransactioncompletionล้มเหลว; SQLunknownerrorsยังsanitized500
5. โอนตามSQLเดิมทั้งก่อนส่งและphaseที่metadataถูกล็อก โดยไม่สร้างphasegateใหม่ ไม่แก้SubmissionAPIของเพื่อนเพื่อเตรียมfixtures
6. Browserconfirmation/cancel/pending/roleUIrefresh/noautomaticretry/CSRF/session/DesktopMobile; ผูกทุกwriteกับouterROLLBACK

ทุกชุดDBตรวจชื่อ student_project_management_v1_test ก่อน Businessrequestsใช้project_appและTransaction/ROLLBACK ตรวจคืนmetadata/ACL/rowsไม่รวมsequencevalues ไม่มีCOMMITfixtureเพื่อทดสอบmulti-sessionเอง

## ผลตรวจรับ

Readonlybaseline52functions/effectiveACL/direct appผ่าน ผลBackend227testsรวมtransfer13 และBrowser63รวมtransfer7/directappsmoke/lint/TypeScript/buildผ่าน พร้อมROLLBACKคืนbaseline ไม่รวมsequencevalues ไม่ใช่multi-sessionconcurrencyหรือการตรวจรับSupabase/featureของเพื่อน อ่านขอบเขตrealDB/mockedresponses/ข้อจำกัดในรายงาน
