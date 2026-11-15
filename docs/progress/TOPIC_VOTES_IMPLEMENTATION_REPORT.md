# Topic votes / roster / results — รายงานพัฒนาและตรวจรับ

**ผลต่อเนื่องหลังรายงานนี้:** ผู้ใช้อนุมัติfixture29แถวและรัน[VC01–VC08ผ่าน8/8ด้วยdirectapp/3PID/winner-ROLLBACK](TOPIC_VOTE_CONCURRENCY_REPORT.md) แล้ว Backendregressionหลังติดตั้ง386ผ่าน รายงานนี้คงผลรอบimplementation349/90และข้อจำกัดของsnapshotเดิม ไม่ใช้ข้อความTX02NotVerifiedเดิมแทนผลVCล่าสุด และยังไม่winner-COMMIT/HTTPconcurrencyครบ

ตรวจวันที่ 2026-11-15 (Asia/Bangkok) · local `feature/project-continuation` จาก `679913a` + working tree · ไม่ Commit/Push

ผู้ใช้อนุมัติ **ทำครบ Vote/รายชื่อ/ผลตามสิทธิ์** และ **กรรมการเห็น Vote ตนเองและผลรวมเมื่อครบ** ตาม [Contract](../api/TOPIC_VOTES_CONTRACT.md) รวมรายการ Project ของ acceptedAdvisor ไม่เปลี่ยน Schema V1, RBAC, Auth หรือขอบเขต Submission/Milestone/Supabase ของเพื่อน

## ผลที่ใช้งานได้

| ผู้ใช้ | ทางเข้า | ข้อมูลและการทำงาน |
|---|---|---|
| Advisor ที่ได้รับแต่งตั้งเป็นกรรมการ | หน้าบัญชี → งานกรรมการ → `/committee/projects/{id}/topic-votes` | อ่าน snapshot แต่ละรอบ/ประวัติ Vote ของตน ลงมติรอบล่าสุดที่ approved เมื่อมีกรรมการ ≥3 คน; ยืนยันก่อนส่ง ลงครั้งเดียว แก้/ลบไม่ได้; เห็นผลรวมเมื่อครบ ไม่เห็น Vote/comment คนอื่น |
| Student สมาชิกทีมปัจจุบัน | `/projects` → รายชื่อกรรมการและผลหัวข้อ → `/projects/committee` | อ่านชื่อกรรมการ; ก่อนครบ decision=null/comments=[]; หลังครบอ่านผลรวมและข้อความจริงที่ไม่แนบตัวผู้ลงมติ |
| Advisor ที่ตอบรับเป็นที่ปรึกษา | หน้าบัญชี → โครงงานที่ปรึกษา → `/advisor/projects/{id}/committee` | อ่านแบบเดียวกับ Team เฉพาะ Project ที่ตน accepted; สิทธิ์นี้แยกจากการเป็นกรรมการ |
| Coordinator | หน้าจัดกรรมการ → ดูการลงมติรายบุคคล → `/coordinator/projects/{id}/topic-votes` | อ่าน Vote, ชื่อผู้ลงมติ, comment และเวลา เฉพาะ Project ที่มี approvedSubmission และเฉพาะรอบ approved |

ผลสรุปใช้ `v1_topic_decision` เดิม: ต้องลงครบทุกคนและ approved >50% จึงผ่าน; 50% เป็นขอแก้ไข Vote แรกล็อก roster รวมหลังส่งรอบใหม่

## ไฟล์ที่เพิ่ม/ปรับในรอบนี้

| ส่วน | ไฟล์ | เหตุผล |
|---|---|---|
| Backend | [topic_vote_api.py](../../backend/topic_vote_api.py), [topic_vote_store.py](../../backend/topic_vote_store.py) | 7 operations / 6 paths ใหม่, session/CSRF/Origin, project scope, controlled Vote และ projection ตามบทบาท |
| Router/handlers | [main.py](../../backend/main.py) | ติดตั้ง router, sanitized validation/storage errors และ no-store โดยไม่ทับ handler ของ Coordinator/Project |
| Backend tests | [test_topic_vote_api.py](../../backend/tests/test_topic_vote_api.py), [test_auth_security.py](../../backend/tests/test_auth_security.py) | 17 tests ใหม่ และ exact OpenAPI รวม29paths; import/OpenAPI ไม่ต่อ DB |
| Frontend feature | [api.ts](../../frontend/src/features/topic-votes/api.ts), [topic-vote-screen.tsx](../../frontend/src/features/topic-votes/topic-vote-screen.tsx), [topic-votes.module.css](../../frontend/src/features/topic-votes/topic-votes.module.css) | DTO validation, หน้ารายการ/ลงมติ/อ่านผล, confirmation/pending/reconcile และ Desktop/Mobile |
| Routes | `frontend/src/app/committee/projects`, `advisor/projects`, `projects/committee`, `coordinator/projects/[id]/topic-votes` | 6 routes ใหม่ ใช้ App Router และ await dynamic params ตาม Next.js docs ในเครื่อง |
| Navigation | [account-screen.tsx](../../frontend/src/features/auth/account-screen.tsx), [project-screen.tsx](../../frontend/src/features/projects/project-screen.tsx), [committee-screen.tsx](../../frontend/src/features/committee-assignments/committee-screen.tsx) | ลิงก์จากหน้าของแต่ละบทบาท ไม่แสดงข้อมูล Vote ผ่านหน้าอื่นโดยไม่ได้ตรวจสิทธิ์ |
| Browser fixtures/tests | [auth_browser_server.py](../../backend/tests/auth_browser_server.py), [topic-votes.spec.ts](../../frontend/tests/topic-votes.spec.ts) | Topic UOW override ให้ครบ outer connection และ 9 Browser tests พร้อม phase fixtures แยกกรณี |
| เอกสาร | Contract, Backlog, Schema reference, root/Frontend README, Local setup, Start here, Schema2 handoff และรายงานนี้ | บันทึกสิ่งที่ยืนยันแล้ว ผลตรวจ และงานคงค้าง; เก็บรายงาน appointment เดิมเป็น snapshot |

ไฟล์อื่นที่ dirty/untracked ใน Git รวมงานรอบก่อน ไม่ใช่ทั้งหมดถูกแก้ในรอบ Topic votes นี้

## การตรวจสิทธิ์ / Transaction

- ใช้เฉพาะ `student_project_management_v1_test` และตรวจ identity ก่อนชุดทดสอบ Runtime connection ใช้ physical `project_app` ตาม opener เดิม ไม่เพิ่มสิทธิ์และไม่มี owner fallback
- API tests/Browser ใช้ connection ที่มี outer transaction และ override Auth/Team/Project/Invitation/Committee/**Topic** UOW ครบทุกตัว แต่ละ request เป็น savepoint; staff fixtures เตรียมด้วย effective `project_owner` ที่ไม่ใช่ superuserก่อนสลับเป็น effective `project_app` เพื่อทำ business operations
- Vote หา assignment จาก actor ใน session ตั้ง transaction-local actor ขอ Project lock แล้วอ่านสิทธิ์/latest/status/จำนวนกรรมการ/ownVote ซ้ำ ใช้ `v1_cast_vote` และ `SET CONSTRAINTS ALL IMMEDIATE` ให้ UOW จบก่อนตอบ201
- Context GET ขอ Project lock เพื่อไม่ให้ decision และ comments อยู่คนละสถานะ Team readerขอ Team lock/ตรวจสมาชิกซ้ำก่อน Project lock การอ่านนี้ไม่ใช่SQL READ ONLY transaction
- กรรมการ query เฉพาะ Vote ตนเอง; Team/Advisor comments query เลือกเฉพาะข้อความหลังผลครบ ไม่เลือก VoteID/author/assignment/เวลา เรียงเนื้อหาด้วย COLLATE C แยกจาก roster ไม่ตัดข้อความซ้ำ
- ไม่มี automatic POST retry ถ้า network/invalid response/500 ให้ GET ตรวจผลก่อน; stale submission tokenตอบ409และโหลดบริบทใหม่ ไม่โหวตรอบใหม่ให้เอง
- จำแนก23505เฉพาะ `public.committee_topic_votes.uq_committee_vote_submission_member`; unknown SQL/42501/P0001 sanitized500 ไม่เปิด SQL/input/secret และไม่ fallback เป็น owner

## ผลทดสอบจริง

| รายการ | ผล | ขอบเขตหลักฐาน |
|---|---|---|
| Topic API + Auth security รอบแรก | PASS31 / 9.376s | Topic15 + Auth16 ก่อนเพิ่ม2กรณีสุดท้าย |
| Full Backend regression | **PASS349 / 53.451s** | เดิม332 + Topic17; DB integration พร้อม ROLLBACK/baseline check ไม่รวม API ของเพื่อน |
| Frontend lint | PASS | `npm run lint -- --no-cache` |
| TypeScript | PASS | `tsc --noEmit --incremental false` |
| Production build | PASS | Next16.4.4; รวม6routesใหม่ |
| Browser เฉพาะ Topic | **PASS9 / 16.3s** | Edge/real API+DB, negative/transport casesตามรายการด้านล่าง; rollback PASS, fixture_connections0 |
| Full Browser regression | **PASS90 / 1.3min** | เดิม81 + Topic9; rollback PASS, fixture_connections0 |
| ภาพ Desktop/Mobile | PASS | ตรวจภาพ confirmation390px และ Team summary1440px; ไม่มี horizontal overflow ใน mobile assertion |
| Readonly V1 baseline หลัง tests | PASS | 52functionsตรงsource, differences=[]; effective app privileges/Public ACL PASS; metadata/owners/ACL/rowcountsคงเดิม |
| Direct app readonly postflight | PASS | session_user=current_user=project_app ในtestDB; temporaryVote/Browseraccounts0 และ browserfixtureconnections0; พอร์ต3000/8001ไม่เหลือlistenerจากrunner |
| Source/docs/secret audit | PASS | ตรวจ29ไฟล์ในขอบเขต, Python AST/encoding/ลิงก์เอกสารผ่าน, protectedSQL/Auth/dependencies13ไฟล์ตรงHEADหลังnormalizeEOL, ไม่พบค่าลับจาก.envในไฟล์ที่ตรวจ, staged0 และgit diff --checkผ่าน |

Backend349ใช้คำสั่งเต็มใน [Local Setup](../team/LOCAL_SETUP.md) ส่วน Browserรันจากfrontend:

```powershell
npm run test:e2e -- topic-votes.spec.ts
npm run test:e2e
```

17 Topic testsครอบคลุม scoped worklists, projectionก่อน/หลังครบ, 50%tie, commentsซ้ำ/ไม่ว่าง, <3, latestpending, duplicateรวมจริง23505, ส่งรอบใหม่และประวัติ, rosterlock, scope404, หลังออกทีม, roles/session/expiry/revocation/CSRF/Origin, invalidpayload/actor spoof, ตรวจสิทธิ์ซ้ำหลังlock, SQL/UOWfailure rollback, sanitizedunknownerror และnoTeam/noProject

9 Browser casesแยกหลักฐานดังนี้:

1. Vote3คนจริงและตรวจข้อมูลข้าม4บทบาท ก่อนครบซ่อนcomment หลังครบเปิดผลและข้อความตามสิทธิ์
2. Mobile validation/cancel/pending singlePOST และ refreshเห็นVoteตนเอง
3. POSTได้201จริงแล้วจำลอง Browserไม่ได้รับresponse; GETอ่านVoteที่บันทึกแล้วกลับมา ไม่มีPOSTซ้ำ
4. ส่งtokenของรอบเก่าโดยแก้transportrequest ให้Backendตอบ409จริง; **ไม่ใช่การทดสอบ uploadพร้อมVoteหลายsession**
5. กรรมการไม่ครบตอบ409จริง และรอบใหม่pendingไม่มีform/ไม่มีรอบpendingในCoordinatorDTO
6. Privacyก่อนครบ/acceptedAdvisorที่ไม่ใช่กรรมการ/Coordinatorเห็นรายคน
7. malformed GETเป็นtransportmock; anonymous redirectและwrongrole ใช้Authจริง
8. unexpected200/failedGETเป็นtransportmock ไม่ใช่ผลSQLผิดพลาดจริง; UIไม่แกล้งสำเร็จและต้องอ่านใหม่
9. 4คน50%tieจริงได้ขอแก้ไขและcommentsซ้ำคงอยู่

SQL/UOWfailure testsใช้การฉีดข้อผิดพลาดเพื่อทดสอบrollback/sanitization ไม่ใช่รายงานว่าbaselineมี permission denied ส่วน positive Vote/reads/role projections ใช้SQLจริงด้วย effective project_app

## Fixture และข้อจำกัด

- ใช้ DB-only submission/file/review เพื่อจัด phase graph ไม่ใช้ API/parser/ดาวน์โหลดไฟล์ของเพื่อน; dummy file bytesไม่ใช่หลักฐานผ่านPDF/PPTX content validator
- Browserเตรียมกรณีflow/lost/mobile/incomplete/stale/private/error/revision/tie ในoutertransactionเดียว ไม่มีHTTPseed endpoint ไม่มีpermanentphasefixtureหรือบัญชีใหม่ค้าง
- หลังBackendและBrowser ROLLBACKคืนbaselineเดิม รวมบัญชีจริงของผู้ใช้และconcurrencyfixture10แถวตามอนุมัติครั้งก่อน **identitysequence valuesไม่ย้อนกลับด้วยROLLBACK**
- ไม่แก้SQL/RBAC/Auth source/dependencies/.env ไม่เข้าถึงฐานข้อมูลหลัก ไม่Commit/Push/mergeหรือแก้sourceเพื่อน
- Positive HTTP/Browserรอบนี้เป็น effective-role project_app บนtest connection ไม่ใช่หลักฐาน physical LOGINบัญชีกรรมการถาวรครบworkflow; phaseข้อมูลและบัญชีfixtureหายเมื่อrunnerจบ หน้าnormalUIอาจไม่มีProjectที่พร้อมลงมติ

## งานต่อ / ยัง Not Verified

1. TX02: หลายsessionแข่งแต่งตั้ง/ถอดกรรมการกับVoteแรก รวมSubmissionรอบใหม่พร้อมVoteและwinner-COMMIT ยังไม่ทดสอบรอบนี้ ไม่ขยายผลจาก Project lock tests เดิมเป็น Vote concurrencyครบ
2. UATด้วยบัญชีจริงของทีม และสิทธิ์หลายหน้ารวมระบบยังไม่ครบ จึงคงP12 InProgress โดยไม่นับจากจำนวนtests
3. เชื่อมรายละเอียด/ไฟล์Submissionของเพื่อนหลังแก้B01–B03และยืนยันContract/ขอบเขตรับช่วงตาม [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ไม่เพิ่มdownloadAPIซ้ำ
4. Evaluation API/UI/ผลคะแนนยังไม่พัฒนาในรอบนี้ ต้องยืนยันContractก่อน; ไม่เปิดMilestone/Taskของเพื่อนมาทำซ้ำ
