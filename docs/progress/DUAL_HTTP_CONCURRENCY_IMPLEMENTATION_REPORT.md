# สอง HTTP clients พร้อมกัน — Team และ Vote/Committee

วันที่ 2026-11-15 (Asia/Bangkok) · `feature/project-continuation` / `679913a` + working tree · ไม่GitCommit/Push

**PASS9/9: สองคำขอผ่านTCPจริงซ้อนกัน โดยLogin/CSRFจริงทั้งสองฝั่ง และobserverพบการรอlockจริง** ใช้คนละactorและfixtureเดิม10+29แถว ทุกbusinessaction/credential/sessionชั่วคราวROLLBACK ไม่มีข้อมูลถาวรเพิ่ม

## ไฟล์ที่เพิ่ม/ปรับ

| ไฟล์ | เหตุผล |
|---|---|
| [dual_http_concurrency.py](../../backend/tests/dual_http_concurrency.py) | RunnerDH01–DH09 ค่าเริ่มต้นOffline; สองHTTPworkers/สองconnection/observer และจุดพักAก่อนresponse |
| [test_dual_http_concurrency.py](../../backend/tests/test_dual_http_concurrency.py) | Offline21tests ตรวจscope/คนละactor/credentialguard/gate/HTTPoverlap/DBwait/cleanup/SQLSTATE/baseline |
| [http_concurrency.py](../../backend/tests/http_concurrency.py) | เพิ่มoptionalactorในcredentialfixtureที่ตรวจว่าอยู่ในmanifest และoptionalcallbackก่อนUOWจบ; defaultของrunnerเดิมยังทำงานแบบเดิม |
| เอกสารนี้/Backlog/Localsetup/Schema2handoff/ลิงก์จากHTTPreportเดิม | บันทึกผลใหม่ ข้อจำกัด และคำสั่งรันซ้ำ ไม่เปลี่ยนContract/Requirements |

ไม่แก้productionBackend/Frontend/SQL/RBAC/.env/dependencies ไม่เพิ่มAPIสำหรับtest/seed ไม่แก้Submission/Milestone/Supabaseของเพื่อน

## หลักฐานว่าคำขอซ้อนกันจริง

1. WorkerAเปิดserverของตนบน127.0.0.1พอร์ตอัตโนมัติ Loginจริงและใช้session/CSRFของตน จากนั้นส่งbusinessrequest
2. Test-onlycallbackในUOWของAพัก **หลังoperationทำSQLแล้ว แต่ก่อนUOWจบและก่อนส่งresponse** และแจ้งcontrollerว่าAถือlockอยู่ การพักมีtimeout12s ไม่แก้status/body/actor/SQLของendpoint
3. ControllerเปิดworkerBอีกconnection/server/clientหนึ่ง Loginเป็นอีกactorจริง แล้วส่งbusinessrequestขณะresponseของAยังไม่กลับ
4. Observerที่เชื่อมdirectproject_app/READ ONLY ต้องพบAในpg_blocking_pids(B), ทั้งสามPIDต้องต่างกัน และresponseeventของA/Bต้องยังไม่ถูกตั้ง ณ จุดนี้ ถ้าresponseแรกจบไปแล้วหรือไม่พบDBwaitให้FAIL
5. จึงปล่อยgateให้Aตรวจresponse/ค่าข้อมูลภายในtransaction และปิดserver/ROLLBACKAก่อนรอB เมื่อlockถูกคืน Bจึงดำเนินต่อ ตรวจstatus/DTO/SQLจริงและROLLBACKB
6. หลังแต่ละcaseตรวจfullpublicrowvalues/metadata/owners/ACL/definitions/constraints/triggers/roleattributes และAuth/publicrowcountsเทียบbaselineก่อนรายงานPASS ต้องพยายามcleanupทั้งAและBแม้ฝั่งหนึ่งล้มเหลว

นี่เป็นcontrolledscheduleที่ให้Aเริ่มก่อนและใช้outerrollbackfixtures ไม่ใช่randomload/การทดสอบทุกลำดับเริ่มก่อนหลัง หรือหลักฐานการCOMMITข้อมูลจริง response2xxยืนยันoperationภายในworkertransactionก่อนการย้อนคืนของtest

ไม่มีAuth/session/role/HTTPresponsemockในLivecases แต่UOWทั้ง6ตัวใช้connectionfixtureของworkerนั้นตามแนวทางเดิม กรณีมีrouter/UOWใหม่ที่ไม่ถูกoverrideจะหยุดก่อนserve ไม่เปิดproductionconnectionนอกoutertransaction

## ขอบเขตAuth/สิทธิ์

- แต่ละworkerเตรียมcredentialชั่วคราวหนึ่งแถวด้วยeffectiveproject_ownerที่ไม่ใช่superuser แล้วswitchเป็นproject_appก่อนserveทุกrequest LoginAPIตรวจArgon2idจริง/คืนcookieจริง ใช้Originlocalhost:3000และCSRFจริง ไม่รับactor/roleจากclient
- A/Bต้องเป็นคนละactorและอยู่ในmanifestที่ตรวจรับแล้ว ห้ามoverwritecredentialเดิม ไม่เปลี่ยนusers.role/privileges/Schema ไม่มีownerfallbackเมื่อbusinessrequestล้มเหลว
- PhysicalconnectionของHTTPworkersเป็นfixture/deploymentconnectionที่เปลี่ยนroleระหว่างเตรียมfixture ทุกAPIใช้effectiveproject_app **ยังไม่ใช่physicalLOGINproject_appหรือproductionconnectionfactoryคนละrequest** observerเป็นdirectLOGINproject_appตามเดิม
- ใช้httpxclientคนละcookiejar/serverพอร์ตแยก ไม่มีcookieปะปน ปิดproxyenvและไม่ตามredirect บันทึกเฉพาะfixedreason/SQLSTATE ไม่แสดงpassword/token/hash/DSN/SQLparameters
- หลังcase ROLLBACKcredential/sessionทั้งสองฝั่ง ไม่สร้างบัญชีLoginถาวรหรือnamespace/Projectใหม่ ข้อมูลตั้งต้นเดิม10+29แถวยังคงอยู่ identitysequencevaluesไม่รวมในbaselineเพราะROLLBACKไม่ย้อนคืน

## 9 กรณีที่ผ่านจริง

| ID | คำขอA | คำขอB | HTTP A/B | ผลหลังA ROLLBACK |
|---|---|---|---|---|
| DH01 | หัวหน้าPOSTโอนหัวหน้าให้memberB | memberBPOSTออกจากทีม | 200 / 204 | Aเห็นตนเป็นmember/ผู้รับเป็นleaderภายในA; เมื่อAย้อนคืน Bยังเป็นmemberตามbaselineและออกได้ |
| DH02 | หัวหน้าPOSTถอดmemberB | memberBPOSTออกเอง | 204 / 204 | การถอดAถูกย้อนคืน Bจึงออกเองได้เฉพาะในtransactionB |
| DH03 | leaderAPOSTเพิ่มfreeStudentเข้าทีมmain | leaderCPOSTเพิ่มคนเดียวกันเข้าทีมempty | 201 / 201 | Bรอuniqueconflict; เมื่อAย้อนคืน นักศึกษาอยู่เฉพาะทีมemptyในBก่อนBย้อนคืน |
| DH04 | กรรมการbPOSTVoteแรก | CoordinatorPOSTเพิ่มกรรมการสำรอง | 201 / 201 | VoteAถูกย้อนคืน rosterเพิ่มได้เป็น4คนในB |
| DH05 | กรรมการbPOSTVoteแรก | CoordinatorPATCHเปลี่ยนกรรมการcเป็นสำรอง | 201 / 200 | เปลี่ยนได้หลังAย้อนคืน assignmentIDเดิม roster3คน |
| DH06 | กรรมการbPOSTVoteแรก | CoordinatorPOSTถอดกรรมการc | 201 / 204 | ถอดได้ roster2คน เพราะไม่มีVoteAค้างหลังย้อนคืน |
| DH07 | CoordinatorPOSTถอดกรรมการb | กรรมการbPOSTVote | 204 / 201 | AssignmentbกลับมาหลังAย้อนคืน; BลงVoteตนเองหนึ่งแถวได้ |
| DH08 | กรรมการbPOSTVote | กรรมการcPOSTVote | 201 / 201 | ในBมีเฉพาะVotec/decisionnull ไม่เห็นVotebที่ย้อนคืน |
| DH09 | สมาชิกทีมGETรายชื่อ/ผลหัวข้อ | กรรมการbPOSTVote | 200 / 201 | readerAเห็นdecisionnull/comments=[]/rosterชื่อเท่านั้น; Bลงได้เมื่อreaderคืนProjectlock |

ทุกcaseได้transport=TWO_LOOPBACK_TCP_CLIENTS, real_login_both=true, http_requests_overlap_observed=true, database_wait_observed=true, both_workers_rolled_back=true และpublic_rows_auth_counts_metadata_restored=true

## ผลตรวจรอบนี้

| รายการ | ผล | ขอบเขต |
|---|---|---|
| Offlineใหม่+HTTPhelperเดิม+Authsecurity | **PASS60 / 0.611s** | Dual21 + HTTP23 + Authsecurity16; mocks ไม่เปิดsocket/ต่อPG/อ่าน.env ไม่ใช้แทนLivecase |
| V1preflight | PASS | testDB52functions differences=[]; effectiveappPublicACLตรงsource |
| สองHTTPclients DH01–DH09 | **PASS9/9** | ตรวจoverlapก่อนresponseทั้งสอง/3PID/DBwait/realLogin/ROLLBACK |
| Regressionrunnerเดิม repositoryA/HTTPB | **PASS14/14 รันใหม่** | ยืนยันoptionalhelperไม่เปลี่ยนdefault รวมHRC06HTTP500/55P03ตามคาด |
| ข้อมูลถาวรเพิ่ม | **0** | ใช้manifest/seedเดิม ไม่เพิ่มAuthaccount/fixtureถาวร |
| Finalreadonlypostflight | PASS | 52functions/differences=[]/effectiveappPublicACLตรงsource; manifestTeam/Topicvalid; fixturecredentials0/sessions0 และotherclientconnections0 |
| Source/docs/secret audit | PASS | productionFrontend-Backend-SQL68ไฟล์ตรงsnapshotที่ตรวจไว้ก่อนหน้า; 8ไฟล์ในขอบเขตผ่านAST/encoding/whitespace/ลิงก์ ไม่พบcommitcallหรือค่าลับจาก.env; staged0/gitdiffcheckผ่าน |

ไม่พบruntimepermissiondeniedหรือunexpectedSQLfailureในDH9 กรณี500/55P03อยู่ในHRC06ของregressionเดิมซึ่งจงใจค้างlockเพื่อทดสอบsanitizederror ไม่ใช่bugที่พบจากการใช้งานปกติ

ไม่รันfullBackend/Browser/lint/TypeScript/buildซ้ำรอบนี้เพราะเพิ่มเฉพาะtesthelpers/tests/docsและไม่เปลี่ยนproduction/ข้อมูลตั้งต้นถาวร ผลBackend386/Browser90เป็นsnapshotรอบ[ติดตั้งTopicfixture](TOPIC_VOTE_CONCURRENCY_REPORT.md) ไม่ใช่ผลรวมsuiteใหม่ทั้งรายการ ผลLive9และLive14เป็นคนละrunner/ขอบเขต ไม่ใช่จำนวนRequirementsที่ปิดเพิ่ม

## ทำไมยังไม่ทดสอบผู้ใช้เดียวกันสองฝั่ง

Fixtureusersไม่มีcredentialsถาวร auth.sessionsมีFKไปauth.credentials และcredentialsมีPKuser_id จึงเตรียมcredentialของuserเดียวกันที่ยังไม่COMMITให้สองconnectionมองเห็นพร้อมกันไม่ได้ การINSERTซ้ำจะรอกันตั้งแต่เตรียมAuthก่อนถึงbusinessoperation ทำให้ไม่ใช่หลักฐานที่ต้องการ

รอบนี้เลือกคนละactorตามContractที่ยืนยันแล้ว ไม่สร้างcredentialsถาวร/ไม่mockAuthหรือแอบCOMMITเพื่อข้ามข้อจำกัด ผลsame-actorของ[runnerเดิม](HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md)ยังเป็นrepositoryA/HTTPB ไม่ขยายเป็นสองHTTPclients

## คำสั่ง Windows / PowerShell

จากroot Offline:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.dual_http_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_dual_http_concurrency backend.tests.test_http_concurrency backend.tests.test_auth_security -q
```

LiveเฉพาะtestDBที่มีสองmanifestเดิม ต้องหยุดงานเขียนDBอื่นระหว่างรัน ไม่ใช้Projectจริงแทน/ไม่สร้างmanifestจากIDsที่ROLLBACKไปแล้ว ใช้พอร์ตloopbackที่runnerเปิดเอง ไม่ใช้พอร์ตnormalFrontend/Backend:

```powershell
$teamFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.dual_http_concurrency --run-rollback --team-fixture $teamFixtureManifest --vote-fixture $topicFixtureManifest
```

## งานคงค้าง

- Winner-COMMITทุกแบบยังไม่อนุมัติ/ไม่ทดสอบ การอนุมัติseed29แถวไม่ครอบคลุมCOMMITbusinessactions
- สองHTTPclientsที่ใช้actorเดียวกัน, physicalproject_appของHTTPworkers, productionconnectionfactoryแต่ละrequest และrandomload/ทุกorderingยังNot Verified
- GenuineAPIdeadlock/40001/retry, UATบัญชีจริง, Evaluation และTaskconcurrencyยังไม่ครบ
- Submission/Milestone/Supabaseยังเป็นของเพื่อน ไม่เพิ่มAPIupload/review/downloadหรือphasefixtureของเพื่อนในDH9 ดู [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

P12/P18/P19ยังInProgress Done5/20=25%คงเดิม เป็นอัตราปิดchecklist ไม่ใช่คะแนนจากจำนวนtests
