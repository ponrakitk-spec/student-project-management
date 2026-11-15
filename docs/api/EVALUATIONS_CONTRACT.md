# Evaluation — Approved contract

วันที่ 2026-11-15 (Asia/Bangkok) · ผู้ใช้ยืนยัน **ทำครบ API/UI ตามร่าง** และ **ใช้สิทธิ์ดูผลตามข้อเสนอ**: กรรมการเห็นของตนตลอด เมื่อครบTeam/acceptedAdvisor/กรรมการเห็นรวม-เฉลี่ย และCoordinatorเห็นรายบุคคลหลังครบ ไม่เปลี่ยนSchema/RBAC/งานเพื่อน

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตาราง10/หัวข้อ4.2/4.4/4.5 และ [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) `v1_record_evaluation`, `v1_committee_evaluation_guard`, `v1_has_first_evaluation`

## กฎ V1 ที่ยืนยันแล้ว

- กรรมการคือadvisorที่ได้รับแต่งตั้งในProject ไม่เพิ่มค่าใหม่ในusers.role และassignmentต้องมาจากsessionactor+Project ไม่รับclientassignmentID
- หนึ่งassignmentให้Evaluationได้ครั้งเดียวต่อProject ไม่แยกรอบSubmission ไม่มีUPDATE/DELETE; scoreเป็นINTEGER0–100 และcommentเป็นTEXTต้องมีข้อความหลังtrimASCIIwhitespace
- ให้คะแนนเมื่อ **Submissionล่าสุดมีผลกรรมการapproved** และมีMilestonecompletedอย่างน้อย1 ไม่ใช้ชื่อProject/checkbox/statusจากclientแทนเงื่อนไขDB
- Evaluationแรกล็อกMilestone/Task/AssigneeตามV1 มีข้อยกเว้นถอนassigneeจากการออกทีมตามC-02 ไม่ปลดล็อกงานหรือเปลี่ยนphasegateเอง
- ผลรวม/เฉลี่ยคำนวณเมื่อกรรมการให้คะแนนครบ โดยเฉลี่ยปัดเป็นจำนวนเต็ม ไม่เพิ่มcolumnเก็บค่ารวม ไม่คำนวณผลสิทธิ์จากBrowser
- G-12ต้องตรวจsession/role/projectscopeทุกครั้ง; สมาชิกทีมใช้สมาชิกภาพปัจจุบัน acceptedAdvisorใช้invitationaccepted กรรมการเห็นการประเมินของตนตามสิทธิ์
- **คำยืนยันการแจกแจงข้อมูลเพิ่มเติม:** DataDictionary4.4ไม่ได้แจกแจงfieldรายบทบาทครบ ผู้ใช้จึงยืนยันmatrixด้านล่างในรอบนี้ ไม่ยืมสิทธิ์ดูVoteรายบุคคลของCoordinatorมาใช้กับEvaluationอัตโนมัติ

## ขอบเขต API/UI ที่ยืนยันแล้ว

ใช้session8h/CSRF/Origin/no-storeเดิม localhost:3000→localhost:8000; IDsเป็นpositiveBIGINTstrings ไม่มีclientactor/role/assignment/created_at/summary ไม่เปลี่ยนSQL/RBAC และไม่ทำSubmission/Milestone/TaskAPIของเพื่อนซ้ำ

| Method / path | Request / สิทธิ์ | Success |
|---|---|---|
| GET `/api/v1/committee/projects/{project_id}/evaluations` | advisorที่มีassignmentในProjectนั้น | 200 `{data:committee_context}` |
| POST `/api/v1/committee/projects/{project_id}/evaluations` | `{score:integer,comment:string}`; actorมีassignment/ผ่านphase/ยังไม่ประเมิน | 201 `{data:own_evaluation}` หลังUOWจบ |
| GET `/api/v1/projects/me/evaluations` | studentสมาชิกทีมปัจจุบัน; deriveProjectจากsession | 200 `{data:reader_context}` |
| GET `/api/v1/advisor/projects/{project_id}/evaluations` | advisorที่acceptedProjectนั้น | 200 `{data:reader_context}` |
| GET `/api/v1/coordinator/projects/{project_id}/evaluations` | coordinator/ProjectมีapprovedSubmissionตามG-12 | 200 `{data:coordinator_context}` |

ใช้รายการProjectกรรมการ/acceptedAdvisor/Coordinatorที่มีอยู่แล้ว ไม่เพิ่มuserdirectory/worklistAPIใหม่เพียงเพื่อEvaluation

### DTOที่ยืนยันแล้ว

- project: `{id,name,description,team:{id,name}}` แบบTopic/Coordinatorเดิม
- own_evaluation: `{id,score,comment,created_at}`; IDและเวลามาจากDB ไม่มีassignment/advisorของผู้อื่น
- summary: `null`ก่อนครบ หรือ`{total_score:"240",average_score:80}`เมื่อครบ; total_scoreเป็นstringรักษาค่าSQLSUM(BIGINT) average_scoreเป็นinteger0–100คำนวณSQLround(avg(score))
- committee_context: `{project,can_evaluate,blocking_reason,own_evaluation,summary}`; reasonเป็นNO_SUBMISSION/TOPIC_NOT_APPROVED/COMPLETED_MILESTONE_REQUIRED/ALREADY_EVALUATEDหรือnull ข้อมูลเฉพาะeligibilityไม่คืนMilestone/Taskเต็มรายการ
- reader_context: `{project,summary}`; ไม่คืนคะแนน/commentรายคนหรือprogresscountsก่อนครบ
- coordinator_context: `{project,summary,evaluations:[]}`; ตามmatrixที่ยืนยัน เปิดindividualsหลังครบเท่านั้นเป็น`[{id,advisor:{id,full_name},score,comment,created_at}]` เรียงcreated_at/idASCตามV1 ก่อนครบไม่แกล้งแสดงว่าไม่มีคนประเมิน แต่UIบอกรอผลครบ
- คะแนนเป็นJSONintegerจริง ไม่รับbool/float/string; commenttrimASCIIเหมือนSQL รักษาwhitespaceภายใน/Unicode ไม่เพิ่มเพดานTEXTเอง ปฏิเสธNUL/invalidUnicodeที่PostgreSQLเก็บไม่ได้ ไม่echoinputในerror

### สิทธิ์เปิดเผยที่ยืนยันแล้ว

| ผู้ใช้ | ก่อนครบ | เมื่อกรรมการทุกคนให้คะแนนครบ |
|---|---|---|
| กรรมการที่ได้รับแต่งตั้ง | Evaluationของตนเท่านั้น | ของตนและคะแนนรวม/เฉลี่ย; ไม่เห็นscore/commentคนอื่น |
| Teamสมาชิกปัจจุบัน | summary=null | เฉพาะคะแนนรวม/เฉลี่ย ไม่มีรายบุคคล/comment |
| acceptedAdvisor | summary=null | เฉพาะคะแนนรวม/เฉลี่ย ไม่มีรายบุคคล/comment |
| Coordinator | summary=null/evaluations=[] | คะแนนรวม/เฉลี่ยและindividualscore/comment/ชื่อ/เวลา |

Matrixนี้เป็นคำยืนยันเพิ่มเติมของผู้ใช้ ไม่เปิดคะแนนผู้อื่นก่อนครบหรือเพิ่มรายบุคคลแก่Team/Advisorเอง

### HTTP errors

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionหาย/หมดอายุ/ถูกยกเลิก |
| 403 EVALUATION_ACCESS_FORBIDDEN | roleไม่ใช่advisorเข้าพื้นที่กรรมการ; readerใช้EVALUATION_READER_ACCESS_FORBIDDEN |
| 404 COMMITTEE_PROJECT_NOT_FOUND | ไม่ใช่Projectที่actorได้รับแต่งตั้ง/ไม่มีProject |
| 404 PROJECT_NOT_FOUND / TEAM_NOT_FOUND | resourceไม่มี/ไม่เห็นตามG-12 |
| 409 EVALUATION_ALREADY_RECORDED | actorให้คะแนนแล้ว รวมส่งข้อมูลเดิมซ้ำ |
| 409 TOPIC_NOT_APPROVED | ไม่มีlatestSubmissionที่กรรมการอนุมัติแล้ว |
| 409 COMPLETED_MILESTONE_REQUIRED | ไม่มีMilestonecompletedอย่างน้อย1หลังขอlock |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | Authpolicyเดิมไม่ผ่าน |
| 422 VALIDATION_ERROR | integer0–100/comment/ID/ชนิด/extraFieldsผิด ไม่echoinput |
| 500 INTERNAL_ERROR | unknownSQL/permission/transactionfailure; sanitized ไม่มีownerfallback |

## Transaction / สิทธิ์ SQL

- หาassignmentจากsession/Project ตั้งtransaction-localactorและขอProjectlock แล้วอ่านscope/latesttopic/hascompleted/ownEvaluationใหม่หลังรอ ไม่มีdirectINSERT/UPDATE/DELETEevaluationsให้appเพิ่ม
- เรียก `v1_record_evaluation(assignment,score,comment)` ตามRBACเดิม บังคับconstraintsและให้UOWจบก่อนคืน201 ไม่เพิ่มgrantเมื่อพบpermissiondenied
- จำแนกUNIQUEเฉพาะevaluationของassignmentเดิม ไม่แปลงทุก23505/P0001/42501เป็นbusinessconflict ต้องตรวจconstraintidentityจริงก่อนmap
- Readcontextใช้Projectlockเพื่อให้การตรวจครบและอ่านผลไม่อยู่คนละสถานะ Teamreaderใช้Team→Projectlockและตรวจสมาชิกภาพซ้ำ เป็นreadที่ขอล็อกไม่ใช่SQL READ ONLY
- ผลครบตรวจจากassignmentทั้งหมด/จำนวนevaluationที่ผูกassignmentเดียวกัน ไม่มีการแบ่งคะแนนตามSubmission ไม่มีcount/tallyของผู้อื่นก่อนครบในContractนี้

## UI

- กรรมการ: ลิงก์จากหน้ารายการ/รายละเอียดงานกรรมการไป `/committee/projects/{id}/evaluations`; อ่านownEvaluation/eligibility ให้integer0–100+comment มีconfirmationก่อนบันทึกเพราะแก้/ลบไม่ได้
- Team: `/projects/evaluations` จากหน้าProject; acceptedAdvisor: `/advisor/projects/{id}/evaluations` จากProjectที่ตอบรับ; Coordinator: `/coordinator/projects/{id}/evaluations` จากหน้าจัดกรรมการ
- ก่อนครบแสดงรอผล ไม่เปิดข้อมูลที่ต้องซ่อนแล้วให้Browserกรอง หลังครบแสดงตามmatrixที่ยืนยัน
- pendingส่งครั้งเดียว network/500/invalidsuccessต้องGETreconcileก่อน ไม่มีautoPOSTretry;409โหลดcontextใหม่; Auth401กลับLogin
- แยก `src/features/evaluations` ใช้AuthShell/sessionเดิม/DesktopMobile ไม่เก็บคะแนน/sessionในlocalStorage ไม่เพิ่มหน้าMilestoneหรือdownloadfileซ้ำ

## ขอบเขตการทดสอบตาม Contract

- Validator0/100/ชนิดbool-float-string/ข้อความว่าง/NUL-Unicode/ASCIItrim/ไม่มีTEXTmaxlengthใหม่ แบบOfflineก่อน
- HTTP/PostgreSQL: scope/role/session/CSRF/Origin/latesttopic/hascompleted/immutable/duplicate/first-scorelock/forcedconstraints/UOWfailure/sanitizederrors
- Privacyก่อนครบ/หลังครบ/ออกทีม/acceptedAdvisor/กรรมการ/Coordinator รวมexactDTOkeysและround(sum/avg)บนSQL
- Phasefixtureใช้DB-onlycontrolledSQLสำหรับVote+Milestone/Taskเพื่อให้completedจริง ไม่อัปเดตmilestones.statusตรงหรือใช้APIเพื่อนที่ยังไม่ได้รวม
- ทั้งAPI/Browserต้องoverrideAuth/Team/Project/Invitation/Committee/Topic/**Evaluation**UOWครบในouterROLLBACK ไม่สร้างบัญชี/phasefixtureถาวร ไม่แก้fixtureConcurrencyเดิม10+29แถว
- หลังBackendผ่านจึงBrowser/DesktopMobile/lint/TypeScript/buildและregressionตามผลกระทบ เฉพาะstudent_project_management_v1_test ตรวจDBก่อนทุกชุด

## ประวัติการเตรียมก่อนยืนยัน API/UI

- เพิ่ม [evaluation_validation.py](../../backend/evaluation_validation.py) เป็นpurehelpersตามกฎINTEGER0–100/ASCIItrimTEXTเดิม ไม่มีrouter/config/DB/authหรือการเปิดเผยผล
- เพิ่ม [test_evaluation_validation.py](../../backend/tests/test_evaluation_validation.py) 12tests ครอบคลุม0/100/outofrange/bool/float/string/null/commentsว่าง/NUL-surrogate/Thaiemoji/innerwhitespace/ไม่มีTEXTmaxlengthใหม่
- คำสั่งด้านล่าง **PASS45 / 0.572s** = Evaluation12 + Authvalidation17 + Authsecurity16 เป็นOffline ไม่ใช่HTTP/PGEvaluationหรือAPIที่พร้อมใช้งาน ไม่รันBrowser/build/DBworkflowซ้ำเพราะยังไม่มีendpoint/UIใหม่

```powershell
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_evaluation_validation backend.tests.test_auth_validation backend.tests.test_auth_security -q
```

Implementationให้Evaluationhandlersถูกเลือกก่อนTopicpathpredicateในmainที่ครอบคลุมcommittee/projects-prefix และoverrideEvaluationUOWครบในทุกAPI/Browserfixture ไม่ปล่อยfactoryใหม่หลุดจากouterROLLBACK

ScopeAPI/UIและprivacymatrixยืนยันแล้ว และพัฒนาครบ 5 operations / 4 API paths กับ 4 UI routes อ่านผลตรวจจริงและข้อจำกัดใน [Evaluation Implementation Report](../progress/EVALUATIONS_IMPLEMENTATION_REPORT.md) ไม่ถือว่าผลvalidatorอย่างเดียวเป็นหลักฐานAPI/UI และยังไม่ใช่การตรวจรับ Submission/Milestone API ของเพื่อน
