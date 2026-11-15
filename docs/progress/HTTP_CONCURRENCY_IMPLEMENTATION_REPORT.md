# HTTP / PostgreSQL Concurrency — ผลทดสอบ Team/Project และ Vote/Committee

**ผลต่อเนื่องหลังรายงานนี้:** [สองHTTPclients9กรณีผ่านแล้ว](DUAL_HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) คนละactor/Loginจริง/responsependingทั้งสอง+DBwait ก่อนA/BROLLBACK พร้อมOffline60และrunnerเดิม14regressionผ่าน ข้อความ“ยังไม่สองHTTPclients”ด้านล่างเป็นขอบเขตของrunner14เดิม ไม่ขยายเป็นsameactor/winner-COMMIT/physicalappworkers

วันที่ 2026-11-15 (Asia/Bangkok) · `feature/project-continuation` / `679913a` + working tree · ไม่GitCommit/Push

**PASS14/14: คำขอAPIผ่านTCPจริงรอtransactionคู่แข่ง แล้วตรวจstatus/DTO/ROLLBACK** ใช้fixtureTeam10แถวและTopic29แถวเดิม ไม่มีข้อมูลตั้งต้นถาวรเพิ่ม ไม่เปลี่ยนBackend/Frontend/SQL/RBACหรือSubmission/Milestone/Supabaseของเพื่อน

## สิ่งที่เพิ่ม

| ไฟล์ | เหตุผล |
|---|---|
| [http_concurrency.py](../../backend/tests/http_concurrency.py) | Runner14กรณี ค่าเริ่มต้นOffline ต้องระบุสองmanifest; Aใช้repository, Bใช้HTTP/TCPจริงพร้อมLogin/CSRF, observerตรวจpg_blocking_pids; ทุกtransactionบังคับROLLBACK |
| [test_http_concurrency.py](../../backend/tests/test_http_concurrency.py) | Offline23tests: guard/manifest/6UOWoverrides/identity/temporarycredential/ephemeralserver/response/cleanup/SQLSTATE/baseline |
| เอกสารนี้, Backlog, Localsetup และSchema2handoff | แยกหลักฐานHTTPกับDB-only, ทดสอบเดิมกับผลใหม่ และข้อจำกัดการรับช่วงงานเพื่อน |

ไม่เปลี่ยนproductionrouter/contracts/handlers/dependencies/.env ไม่เพิ่มAPIสำหรับseedหรือทดสอบ และไม่เพิ่มgrantเพื่อให้ผ่าน

## ขอบเขตที่พิสูจน์

1. Aเชื่อมdirectLOGINproject_app ทำcontrolledoperationผ่านrepository/SQLเดิม แล้วถือtransactionค้างไว้
2. Bมีconnectionแยก ใช้ownerfixturemodeเตรียมcredentialชั่วคราว **หนึ่งรายการเฉพาะactorในmanifest** แล้วสลับเป็นeffectiveproject_appก่อนserveทุกคำขอ ห้ามoverwritecredentialเดิมและไม่fallbackownerเมื่อrequestล้มเหลว
3. Uvicornเปิดsocketที่runnerเป็นเจ้าของบน127.0.0.1พอร์ตอัตโนมัติ ไม่ใช้3000/8000/8001 HTTPXใช้TCPจริง, trust_env=falseไม่ส่งผ่านproxy, ไม่ตามredirect และมีtimeout
4. BเรียกLoginAPIจริง/verifyArgon2idจริง รับsession/CSRFcookiesและGETauth/meตรวจuser/role ก่อนส่งbusinessrequestพร้อมOriginlocalhost:3000/CSRFเดิม ไม่มีmockactor/role/sessionresolver
5. Auth/Team/Project/Invitation/Committee/TopicUOWทั้ง6ตัวถูกoverrideให้ใช้Bconnectionเดียวกันและnestedtransactions ตรวจdependencygraphรวมincludedroutersของFastAPIในเครื่อง หากพบUOWเพิ่มที่ไม่รู้จักให้หยุดก่อนserve ไม่ปล่อยrequestไปproductionconnection
6. Observerเป็นdirectLOGINproject_app/READ ONLY ต้องเห็นPIDของAในpg_blocking_pids(B)จริง ใช้3PIDต่างกัน จึงถือว่าเกิดการรอ ไม่ใช้sleepหรือthreadเริ่มทำงานเป็นหลักฐาน
7. ปกติปล่อยAด้วยROLLBACKแล้วBจึงดำเนินต่อ ตรวจHTTPstatus/DTO/ค่าข้อมูลที่เปลี่ยนในB จากนั้นROLLBACKB รวมcredential/sessionชั่วคราว ส่วนHRC06จงใจค้างAจนBtimeoutและตอบ500ก่อนปล่อยA
8. หลังแต่ละcaseตรวจfullpublicrowvalues/definitions/constraints/triggers/ownership/ACL/roleattributes และAuth/publicrowcountsกลับbaseline ก่อนรายงานPASS ปิดเฉพาะsocket/server/connectionที่runnerเปิดเอง

การตรวจbaselineไม่รวมค่าidentitysequencesซึ่งROLLBACKไม่ย้อนคืน และไม่อ่านค่าcredential/sessionเดิมมาแสดง ผลAuthตรวจmetadata/จำนวนแถวและยืนยันfixturecredentials/sessionsเหลือ0หลังจบ ไม่อ้างว่าทุกค่าในฐานข้อมูลรวมsequenceไม่เปลี่ยน

**Roleboundary:** A/observerเป็นphysicalproject_app ส่วนBต้องใช้fixture/deploymentconnectionเพื่อเตรียมcredentialด้วยnon-superuserproject_ownerก่อนสลับcurrent_user=project_appในoutertransactionเดียว ทุกAPIrequestถูกguardเป็นeffectiveproject_app ไม่ใช่หลักฐานว่าBเป็นphysicalLOGINproject_app normalruntimeยังใช้directproject_appตามเดิมและไม่ถูกแก้

**Concurrencyboundary:** Aเป็นrepositoryoperation และBเป็นHTTPrequestจริง ไม่ใช่สองHTTPclientsพร้อมกัน ไม่ใช่loadtest/browserCORSหรือwinner-COMMIT ทั้งสองฝั่งROLLBACK; ไม่อ้างduplicate409/สิทธิ์ถูกถอนหลังCOMMITจากcaseที่Aย้อนคืน

## กรณีที่ผ่านจริง

| ID | Aค้างtransaction | Bผ่านHTTP | ผลที่ตรวจ |
|---|---|---|---|
| HRC01 | โอนหัวหน้า | PATCHteams/meโดยหัวหน้าเดิม | รอแล้ว200หลังAย้อนคืน; actorยังleaderและชื่อเปลี่ยนเฉพาะในB |
| HRC02 | ถอดmember | POSTteams/me/leaveโดยmemberนั้น | รอแล้ว204/emptybody; สมาชิกถูกถอนเฉพาะในB |
| HRC03 | PATCHProjectdescription | PATCHprojects/meเฉพาะname | รอแล้ว200; descriptionที่ไม่ส่งกลับเป็นbaselineเดิมหลังAย้อนคืน |
| HRC04 | สร้างProjectให้ทีมempty | POSTprojectsทีมเดียวกัน | รอแล้ว201หลังAย้อนคืน; team/created_byถูกต้อง |
| HRC05 | เพิ่มนักศึกษาคนเดียวเข้าทีมmain | POSTmembersเข้าทีมempty | รอuniqueconflictแล้ว201หลังAย้อนคืน; อยู่ทีมของBเท่านั้น |
| HRC06 | แก้Teamและถือlock | PATCHteams/meทีมเดียวกัน | พบwaitจริง, lock_timeout1s, HTTP500/INTERNAL_ERROR; harnessพบ55P03; responseมีเฉพาะcode/messageไม่มีSQL; ข้อมูลกลับbaseline |
| HVC01 | Voteแรก | CoordinatorPOSTเพิ่มกรรมการ | รอแล้ว201; roster4คนหลังVoteAย้อนคืน |
| HVC02 | Voteแรก | CoordinatorPATCHเปลี่ยนกรรมการ | รอแล้ว200; assignmentIDเดิม/กรรมการสำรอง/roster3 |
| HVC03 | Voteแรก | CoordinatorPOSTถอดกรรมการ | รอแล้ว204/emptybody; roster2เมื่อVoteAย้อนคืน |
| HVC04 | ถอดผู้ที่จะลงมติ | กรรมการPOSTVote | รอแล้ว201เพราะการถอดถูกย้อนคืน; ownVote/assignmentตรงกัน |
| HVC05 | กรรมการBลงมติ | กรรมการBPOSTVoteรอบเดียวกัน | รอแล้ว201หลังVoteAย้อนคืน; มีVoteตนเอง1แถวในB ไม่ใช่duplicateหลังwinner-COMMIT |
| HVC06 | กรรมการBลงมติ | กรรมการCPOSTVote | รอแล้ว201; มีVoteCเท่านั้น decisionnull ไม่เห็นVoteAที่ย้อนคืน |
| HVC07 | DB-onlyรอบใหม่พร้อมไฟล์ | TeamGETรายชื่อ/ผล | รอแล้ว200; เห็นรอบเดิมขอแก้ไข/comments3ข้อความ rosterชื่อเท่านั้น ไม่มีmetadataรายVote |
| HVC08 | TeamreaderถือProjectlock | กรรมการPOSTVote | รอแล้ว201เมื่อreaderคืนlock; ownVote1แถว/decisionnull |

HRC06ใช้SQLSTATEจากexceptioncontextภายในtest-onlyUOWwrapperเพื่อพิสูจน์การแปลงerrorของhandlerเดิม ไม่เพิ่มSQLSTATE/SQLให้productionresponse ต้นทางคือTeamrepositoryขอ `public.v1_lock_team` ขณะAถือlockอยู่ ไม่ใช่permissiondeniedและไม่ใช่bugที่พบจากการใช้งานปกติ

HVC07เป็นDB-onlyphaseoperationจากrunnerเดิม ยังไม่ใช่APIupload/review/downloadของเพื่อน Dummyfilebytesไม่ใช่หลักฐานPDF/PPTXparservalidation

## ผลตรวจรอบนี้

| รายการ | ผล | ขอบเขต |
|---|---|---|
| Offlineใหม่ | 23testsในชุดรวมด้านล่างผ่าน | mocks ไม่เปิดsocket/อ่าน.env/ต่อPG; ไฟล์fixture/metadataเดิมไม่ถูกเขียน |
| Offlineใหม่+Authsecurity+sharedrunner+Voteharness+DBboundary | **PASS88 / 0.658s** | 23+16+25+15+9; รวมfail-closedUOWguardและcleanup ไม่ใช่ผลlockingจริง |
| Baselinepreflight | PASS | testDB52functions differences=[]; effectiveappPublicACLตรงsource |
| LiveTCPHTTP/PG | **PASS14/14** | แต่ละcase real_login/wait_observed/both_workers_rolled_back/public_rows_auth_counts_metadata_restored=true |
| Locktimeout | PASS | HRC06คาดหวังHTTP500และSQLSTATE55P03; ไม่มีSQL/parametersในresponse |
| ข้อมูลถาวรเพิ่ม | **0** | fixtureเดิม10+29แถวยังคงอยู่ ไม่สร้างnamespace/Project/บัญชีLoginถาวรเพิ่ม |
| Finalreadonlypostflight | PASS | 52functions/differences=[]/effectiveappPublicACLตรงsource; manifestTeam/Topicvalid; credential/sessionของfixtureทั้งสองชุดเหลือ0 และotherclientconnections0 |
| Source/docs/secret audit | PASS | productionFrontend-Backend-SQL68ไฟล์ตรงsnapshotที่ตรวจไว้ก่อนหน้า; 7ไฟล์ในขอบเขตผ่านAST/encoding/whitespace/ลิงก์ ไม่พบcommitcallหรือค่าลับจาก.env; staged0/gitdiffcheckผ่าน |

Backend386/Browser90เป็นผลรอบ[ติดตั้งTopicfixture](TOPIC_VOTE_CONCURRENCY_REPORT.md)ก่อนหน้า ไม่รันfullBackend/Browser/buildซ้ำรอบนี้ เพราะเพิ่มเฉพาะharness/tests/docsและbaselineไม่เพิ่มข้อมูลถาวร หลักฐานใหม่คือOffline88และLiveHTTP14ตามตาราง ไม่ใช้ผลเก่ารับรองcaseใหม่

## คำสั่ง Windows / PowerShell

จากroot ค่าเริ่มต้นOffline:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.http_concurrency
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_http_concurrency backend.tests.test_auth_security backend.tests.test_team_project_concurrency_harness backend.tests.test_topic_vote_concurrency database.tests.test_test_database -q
```

LiveHTTPเฉพาะDBในเครื่องที่มีmanifestเดิม ตรวจว่าไม่มีconnectionอื่นเขียนDBพร้อมกันก่อนเริ่ม ไม่ต้องปิดnormalserverเพียงเพราะใช้พอร์ตเดียวกัน เพราะrunnerใช้พอร์ตใหม่ แต่ต้องหยุดกิจกรรมเขียนtestDBระหว่างรัน:

```powershell
$teamFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\team-project-v1.json'
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.http_concurrency --run-rollback --team-fixture $teamFixtureManifest --vote-fixture $topicFixtureManifest
```

ไม่แสดง/ส่งรหัสผ่านในargumentหรือmanifest ใช้privateconfigเดิมในเครื่องและsyntheticcredentialที่เตรียม/ย้อนคืนภายในrunner `--run-rollback`ไม่ติดตั้งseedหรือDDL ไม่มีCOMMIT/applymode/automaticretry

## งานคงค้าง

- สองHTTPclientsพร้อมกันและproductionconnectionfactoryคนละrequestจริง รวมphysicalproject_appของHTTPworkerB
- Winner-COMMITยังไม่ได้รับอนุมัติและไม่ทดสอบ การอนุมัติseed29แถวไม่ครอบคลุมbusinessactionsถาวร
- 40001/retrypolicy, genuineAPIdeadlock, UATบัญชีจริง, Evaluation/Taskconcurrencyยังไม่ครบ
- ผสานSubmission/Milestoneของเพื่อนเมื่อยืนยันขอบเขตและแก้B01–B03ตาม [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md) ไม่ใช้HVC07แทนหลักฐานAPIเพื่อน

P12/P18/P19ยังInProgress คงDone5/20=25%เป็นอัตราปิดchecklist ไม่เพิ่มDoneจากจำนวนcases/tests
