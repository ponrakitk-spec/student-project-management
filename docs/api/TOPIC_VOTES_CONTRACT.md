# Topic votes / roster reads / results — Approved contract

วันที่ 2026-11-15 (Asia/Bangkok) · ผู้ใช้ยืนยัน **ทำครบVote/รายชื่อ/ผลตามสิทธิ์** และ **กรรมการเห็นVoteตนเองและผลรวมเมื่อครบ** รวมacceptedAdvisorprojectlist/entryตามข้อเสนอ ไม่เพิ่ม Vote/Evaluation columns ไม่เปลี่ยน SQL/RBAC และไม่ทำ Submission/Milestone ของเพื่อนซ้ำ

## กฎ V1 ที่ยืนยันแล้ว

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) 4.2/4.4/4.5/4.6 และ [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) `v1_committee_vote_guard`, `v1_cast_vote`, `v1_topic_decision`

- กรรมการเป็น user.role=advisor ที่มี committee_assignment ของ Project ไม่ใช่ role ใหม่ และไม่ใช่ accepted advisor ของ Project เดียวกัน
- Vote เฉพาะ Submission ล่าสุด (id สูงสุด) ที่ status=approved และ rosterมีอย่างน้อย3คน กรรมการหนึ่งคนลงได้หนึ่งครั้งต่อรอบ ห้ามแก้/ลบ Vote
- voteเป็น approved/revision_requested; commentเป็นoptionalTEXTเมื่อapproved แต่revision_requestedต้องมีข้อความจริง trimASCIIwhitespaceแล้วไม่ว่าง; ไม่เพิ่มเพดานความยาวใหม่
- ผลสรุปยังไม่เกิดจนกรรมการทุกคนลงครบ; approvedมากกว่า50%จึงผ่าน เท่ากับ50%เป็นrevision_requested ใช้v1_topic_decisionเดิม ไม่คำนวณสถานะจากBrowser
- VoteแรกของProjectล็อกrosterถาวร รวมหลังส่งรอบใหม่
- ก่อนครบ กรรมการเห็นVoteตนเอง; Team/acceptedAdvisorไม่เห็นผล/ข้อความของคนอื่นก่อนครบ; Coordinatorเห็นVoteรายบุคคล
- หลังครบ Team/acceptedAdvisorเห็นผลสรุปและcommentที่มีจริงเท่านั้น ห้ามส่งVoteID, author/assignment/advisorID, voteรายคน, voted_at หรือลำดับที่เชื่อมผู้เขียนกับcomment
- Team/acceptedAdvisorอ่านรายชื่อกรรมการได้หลังแต่งตั้งตามG-12, เรียงassigned_at/idเดิม แต่DTOสำหรับสองกลุ่มนี้คืนเฉพาะชื่อ ไม่เชื่อมกับVote
- Backendยืนยันตัวตน/สิทธิ์ทุกครั้งและกรองresponse; DBใช้project_app/actorcontextจากsession ไม่ใช้RLSหรือBrowser actorID

## ขอบเขตรอบนี้ที่ยืนยันแล้ว

1. กรรมการดูProjectที่ได้รับแต่งตั้ง อ่านหัวข้อsnapshot/ประวัติVoteของตน ลงมติพร้อมconfirmation และดูสถานะตามสิทธิ์
2. สมาชิกทีมปัจจุบันและacceptedAdvisorอ่านroster/ผลสรุปแต่ละรอบ พร้อมcommentsที่ไม่แนบตัวผู้ลงมติหลังครบ
3. Coordinatorอ่านVoteรายบุคคล/ผลสรุปในProjectที่เห็นตามG-12
4. ไม่ทำEvaluationAPI, upload/download/reviewSubmissionAPI, Milestone/Task, notification หรือdashboardmetrics และไม่สร้างpermanentphasefixtures/บัญชีเพิ่ม

**สิทธิ์กรรมการหลังครบที่ยืนยัน:** ยังเห็นเฉพาะVoteรายบุคคลของตนเอง แต่เห็นdecisionรวมของรอบนั้นเมื่อทุกคนลงครบ ไม่เปิดVoteหรือcommentของกรรมการคนอื่นในหน้ากรรมการ

## API ที่ยืนยันแล้ว

session/CSRF/Origin/no-storeเหมือนเดิม localhost:3000→localhost:8000; IDsเป็นpositiveBIGINTstrings; ไม่รับactor/role/assignmentID/เวลา/ผลรวมจากclient

| Method / path | Request / สิทธิ์ | Success |
|---|---|---|
| GET `/api/v1/committee/projects` | advisorที่ได้รับแต่งตั้ง; filterตามactor | 200 `{data:[project...]}`; ไม่มีงานเป็น[] |
| GET `/api/v1/committee/projects/{project_id}/topic-votes` | เฉพาะกรรมการที่ได้รับแต่งตั้งในProjectนั้น | 200 `{data:committee_context}` latestsnapshot/ownvotehistory/can_vote/reason และdecisionรวมเมื่อครบ |
| POST `/api/v1/committee/projects/{project_id}/topic-votes` | `{submission_id:"...",vote:"approved"|"revision_requested",comment?:string|null}` | 201 `{data:own_vote}` หลังUOWจบ |
| GET `/api/v1/projects/me/committee` | studentสมาชิกทีมปัจจุบัน; deriveProjectจากsession | 200 `{data:reader_context}` rosterชื่อ/roundsummaries; ไม่มีทีม/Project404ตามG-12 |
| GET `/api/v1/advisor/projects` | advisorที่acceptedProject; filterตามactor | 200 `{data:[project...]}`; ไม่มีงานเป็น[] |
| GET `/api/v1/advisor/projects/{project_id}/committee` | advisorที่acceptedProjectนี้เท่านั้น | 200 `{data:reader_context}` แบบเดียวกับTeam; ไม่ใช่หน้ากรรมการ |
| GET `/api/v1/coordinator/projects/{project_id}/topic-votes` | coordinatorและProjectมีapprovedSubmission | 200 `{data:coordinator_context}` เฉพาะรอบapprovedและVoteรายบุคคล |

POSTส่งsubmission_idเป็นtokenยืนยันว่าผู้ใช้กำลังลงมติsnapshotใด ไม่ใช่authority ถ้าระหว่างโหลดหน้ากับกดยืนยันมีรอบล่าสุดใหม่ ให้409SUBMISSION_CHANGEDและGETใหม่ **ไม่เปลี่ยนไปVoteรอบใหม่ให้เอง**

DTO:

- project: `{id,name,description,team:{id,name}}` แบบCoordinatorเดิม; listเรียงprojectidDESC
- submission: `{id,snapshot_name,snapshot_description,status,submitted_at}` อ่านsnapshotจริง ไม่ใช้ชื่อProjectปัจจุบันแทนหัวข้อที่ลงมติ; roundsเรียงsubmissionidDESC
- own_vote: `{id,submission_id,vote,comment,voted_at}` ของactorเท่านั้น ไม่คืนVoteของคนอื่น
- committee_context: `{project,latest_submission_id,can_vote,blocking_reason,rounds:[{submission,own_vote,decision}]}` ไม่มีtally/Voteคนอื่น; decisionเป็นnullก่อนครบ และapproved/revision_requestedเมื่อครบ; blocking_reasonรองรับNO_SUBMISSION/SUBMISSION_NOT_APPROVED/COMMITTEE_INCOMPLETE/ALREADY_VOTEDหรือnull
- reader_context: `{project,committee:[{full_name}],rounds:[{submission,decision,comments:[string]}]}` decision=null/comments=[]ก่อนครบ; ไม่ส่งยอดapproved/revisionรายคนหรือprogresscountsก่อนครบ
- anonymouscomments: เก็บข้อความจริงรวมข้อความซ้ำ ไม่เติมplaceholder ไม่แนบmetadata เรียงตามเนื้อหาข้อความอย่างคงที่ให้ไม่อิงเวลา/ผู้เขียน/ลำดับVote
- coordinator_context: `{project,rounds:[{submission,decision,votes:[{id,advisor:{id,full_name},vote,comment,voted_at}]}]}` เฉพาะapprovedrounds Voteภายในเรียงvoted_at/idASCตามV1
- ถ้าไม่มีcommittee/ไม่มีsubmissionให้คืนcollectionว่างตามสิทธิ์ ไม่แกล้งซ่อนnetwork/500/invalidDTOเป็นข้อมูลว่าง

ยังไม่เพิ่มfilelinkหรืออ่านfile_dataในfeatureนี้ การดูไฟล์ใช้จุดต่อSubmissionของเพื่อนในภายหลัง โดยรักษาG-12 ไม่สร้างdownloadAPIหรือpublicURLทับงานเพื่อน

## Errors

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | ไม่Login/sessionหมดอายุ/ถูกยกเลิก |
| 403 VOTE_ACCESS_FORBIDDEN | roleไม่ใช่advisorเข้าพื้นที่กรรมการ; roleไม่ตรงreaderendpointใช้codeตามพื้นที่ |
| 404 COMMITTEE_PROJECT_NOT_FOUND | Projectไม่มี/ไม่ใช่งานกรรมการที่actorได้รับแต่งตั้ง; ไม่เปิดงานของคนอื่น |
| 404 PROJECT_NOT_FOUND / TEAM_NOT_FOUND | readresourceไม่มีหรือไม่เห็นตามG-12 |
| 409 SUBMISSION_CHANGED | submission_idไม่ตรงรอบล่าสุดหลังProjectlock |
| 409 SUBMISSION_NOT_APPROVED | ยังไม่มีรอบapprovedที่ลงมติได้ |
| 409 COMMITTEE_INCOMPLETE | จำนวนกรรมการไม่ถึง3 |
| 409 VOTE_ALREADY_CAST | มีVoteของactorในรอบนี้แล้ว รวมซ้ำข้อมูลเดิม |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | คำขอเขียนไม่ผ่านAuthpolicyเดิม |
| 422 VALIDATION_ERROR | IDs/enum/comment/ชนิด/fieldsเกินผิด ไม่echoinput |
| 500 INTERNAL_ERROR | unknownSQL/permission/storage/transactionfailure; sanitized ไม่มีownerfallback |

## SQL / transaction / privacy

- หาassignmentจากsessionactor+project ไม่ใช้clientassignmentID ตั้งtransaction-localactorและขอProjectlockด้วยhelperเดิม แล้วอ่านassignment/lateststatus/ownvote/countใหม่หลังรอ
- ใช้ `v1_cast_vote(submission,assignment,vote,comment)` เท่านั้น ไม่มีdirectINSERT/UPDATE/DELETEVoteให้appเพิ่ม และใช้SQLfunctionguardเป็นชั้นตรวจซ้ำ
- บังคับconstraintsก่อนตอบสำเร็จและให้UOWจบก่อนคืน201; uniqueจำแนกเฉพาะ`uq_committee_vote_submission_member` ไม่แปลงทุกP0001/42501เป็นbusinesserror
- role-scopedอ่านVote: กรรมการqueryเฉพาะของตน; readerไม่select/serializeindividualVoteข้อมูลมาใช้เป็นDTO; ตรวจครบ/decisionด้วยSQLเดิมก่อนอ่านcommentsที่ไม่แนบmetadata
- readTeamต้องใช้สมาชิกภาพปัจจุบันในquery, acceptedAdvisorต้องตรวจinvitationacceptedของตน, coordinatorต้องมีapprovedProject; header/query/bodyที่อ้างrole/actorไม่มีผล
- Context GET ใช้Projectlockเดิมเพื่อให้การตรวจdecisionและอ่านข้อมูลอยู่ในสถานะเดียวกัน Teamreaderใช้Teamlockและตรวจสมาชิกภาพซ้ำก่อนProjectlock; เป็นการอ่านที่ขอล็อก ไม่ใช่SQL READ ONLY transaction
- UIhideไม่ทดแทนserverauthorization และห้ามreturndataที่ต้องซ่อนแล้วให้Frontendกรองเอง

## UI

- advisorมีลิงก์ “งานกรรมการ” จากหน้าบัญชีไป `/committee/projects` เลือกProjectไป `/committee/projects/{id}/topic-votes`; ถ้าไม่ถูกแต่งตั้งรายการว่าง
- อ่านsnapshotแต่ละรอบและVoteตนเอง แบบฟอร์มเฉพาะlatestที่can_vote ใช้ตัวเลือกผ่าน/ขอแก้และcomment ถ้าขอแก้บังคับข้อความ มีconfirmationก่อนส่งเพราะแก้Voteไม่ได้
- pendingป้องกันส่งซ้ำ; network/500/invalidsuccessต้องGETreconcileก่อน ไม่มีautoPOSTretry; stale submission/duplicate/rosterไม่ครบให้แสดงerrorและโหลดบริบทใหม่
- Teamใช้ `/projects/committee` เข้าจากProjectเดิม; acceptedAdvisorเข้ารายการ `/advisor/projects` จากหน้าบัญชี แล้วเลือกอ่านที่ `/advisor/projects/{id}/committee`
- Coordinatorมีลิงก์จากหน้าจัดกรรมการไป `/coordinator/projects/{id}/topic-votes`
- readerแสดงrosterและรอบส่งที่มีสิทธิ์ ก่อนครบแสดงรอผล ไม่แสดงใครลงแล้ว/ยอดvote/comment; หลังครบแสดงdecisionและcommentsข้อความล้วน
- Featureแยก `src/features/topic-votes` ใช้AppRouter/AuthShell/sessionเดิม ไม่เก็บvotes/sessionในlocalStorage ไม่เพิ่มRouteไปแสดงEvaluationเอง

**จุดเข้าของ acceptedAdvisor ที่ยืนยันแล้ว:** GET `/api/v1/advisor/projects` คืนเฉพาะProjectที่actoraccepted และหน้า `/advisor/projects` จากหน้าบัญชี ไม่แก้InvitationDTOเดิมหรือเพิ่มuserdirectory

## แผนทดสอบ

- DB/API: latestapproved/สามคน/immutable/unique/50%tie/ครบจึงสรุป/comments/role/scope/assignmentstale/foreignsubmission/newround/oldownhistory/rosterfirstvotelock
- Privacy: ก่อนครบ/หลังครบ/ออกทีม/acceptedadvisor/committee/coordinator, exactDTOkeys, anonymouscommentsไม่เรียงตามVote และไม่ส่งmetadata/คะแนนรายคนผิดบทบาท
- Atomicity: SQL/UOWfailureก่อนresponse, forcedconstraints, noautomaticretry/sanitized500 ไม่มีpartialwrite
- HTTP fixtureทุกAuth/Team/Project/Invitation/Committee/VoteUOWต้องใช้connectionที่ตั้งใจเดียวกัน/outerROLLBACK ห้ามหลุดไปproductionconnectionแบบB01; phasegraphเป็นDB-onlyไม่ใช้APIเพื่อน
- BrowserrealAPI+negativefeedback+lostresponse+DesktopMobile+baselinecleanup, lint/TypeScript/buildและregressionที่ได้รับผลกระทบ
- เฉพาะstudent_project_management_v1_test ตรวจชื่อก่อนทุกชุด ไม่COMMITdata/phasefixturesหรือเพิ่มสิทธิ์เพื่อให้ผ่าน

API/UIตามContractนี้พัฒนาแล้ว ดูหลักฐานและข้อจำกัดใน [รายงานตรวจรับ](../progress/TOPIC_VOTES_IMPLEMENTATION_REPORT.md) P12ยังInProgressเพราะTX02/multi-sessionและUATยังไม่ครบ ไม่เขียนSchema/RBACหรือCOMMITtestdata
