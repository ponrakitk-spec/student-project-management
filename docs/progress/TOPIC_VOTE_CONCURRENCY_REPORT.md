# Topic / Committee Concurrency — ผลติดตั้งและทดสอบ

**ผลต่อเนื่องหลังรายงานนี้:** [LiveHTTP14กรณีผ่านแล้ว](HTTP_CONCURRENCY_IMPLEMENTATION_REPORT.md) โดยrepositoryAชนกับAPI/TCPจริงB พร้อมLoginและouterROLLBACK ใช้fixtureเดิม ไม่มีข้อมูลถาวรเพิ่ม ยังไม่สองHTTPclients/winner-COMMIT/physicalproject_appของHTTPB ข้อความ“ยังไม่HTTP”ด้านล่างเป็นขอบเขตรอบDB-onlyก่อนหน้า

วันที่ 2026-11-15 (Asia/Bangkok) · `feature/project-continuation` / `679913a` + working tree

**ล่าสุดหลังอนุมัติ: ติดตั้ง fixture29แถว และ VC01–VC08 PASS8/8 บน PostgreSQL จริง** ทุกกรณีเป็นwinner-ROLLBACK ไม่ใช่winner-COMMIT/HTTPconcurrency ไม่มีGitCommit/Push

## ผลหลังอนุมัติบันทึกข้อมูลตั้งต้น

ผู้ใช้ยืนยัน **“อนุมัติบันทึก fixture 29 แถวและรัน 8 กรณี”** ขอบเขตเฉพาะ `student_project_management_v1_test` แยกจากฐานข้อมูลหลักและfixtureTeam/Projectเดิม10แถว

- ติดตั้งAPPLIED/committed=true เฉพาะ29แถวตามตารางด้านล่าง ไม่มีAuthcredentials/sessions ไม่มีบัญชีLogin/รหัสผ่านใหม่ ไม่มีDDL/grant/ข้อมูลเดิมเปลี่ยน
- เตรียมusersด้วยeffectiveproject_ownerที่ไม่ใช่superuser จากนั้นbusinessoperationsด้วยeffectiveproject_app ใช้SQL/helperเดิม ตรวจforcedconstraints/rowdelta/metadataและhashข้อมูลเดิมก่อนCOMMIT
- บันทึกmanifestด้วยexclusivefilecreate/flush/fsyncก่อนCOMMITที่ `%LOCALAPPDATA%\StudentProjectManagement\concurrency\topic-vote-v1.json` ซึ่งอยู่นอกGit เก็บเฉพาะIDs/namespace ไม่มีsecrets ไม่เขียนทับmanifestหรือสร้างชุดใหม่เมื่อผลCOMMITไม่ชัดเจน
- ตรวจconnectionใหม่หลังCOMMIT: metadata/owners/ACL/rowcounts/fullpublicvaluesตรงที่คาด ข้อมูลpublicเดิมเมื่อหักfixtureออกมีhashเดิม และdirectLOGINproject_appตรวจfixtureผ่าน
- เรียกapplyซ้ำด้วยmanifestเดิมได้ALREADY_INSTALLED/additional_rows0/written=false; ตรวจmanifestTeam/Projectเดิมผ่าน ไม่มีการเปลี่ยนfixture10แถวนั้น
- VC01–VC08ผ่านทั้ง8กรณี ใช้directLOGINproject_app/worker2+observer1/3PIDต่างกัน และพบAในpg_blocking_pids(B)จริง ทุกA/BROLLBACKและfingerprintข้อมูล/metadataคืนbaselineที่มีfixture29แถวครบ

**ข้อมูลคงอยู่หลังทดสอบ:** fixtureตั้งต้น29แถวและfixtureเดิม10แถวยังคงอยู่ตามอนุมัติ ActionsของVCไม่ค้าง ค่าidentitysequencesไม่ย้อนคืนด้วยROLLBACK ไม่ลบProjectเพราะR-01

Coordinatorอาจเห็น2Projectจำลองชื่อ `spms-vc-<hex32>.main.project` / `.revision.project` และadvisorfixtureในรายการตามG-12 เป็นข้อมูลสำหรับautomatedtests ไม่มีบัญชีLoginของfixture หลีกเลี่ยงการแก้ข้อมูลเหล่านี้ผ่านหน้าUIเพราะrunnerตรวจbaselineแบบexact; ไม่ใช้แทนUATบัญชีจริง

### ไฟล์ที่เพิ่มในขั้นติดตั้ง

| ไฟล์ | เหตุผล |
|---|---|
| [Topic_Vote_Concurrency_Fixture_Install.py](../../database/tools/Topic_Vote_Concurrency_Fixture_Install.py) | ติดตั้งเฉพาะfixtureที่อนุมัติ ป้องกันseedซ้ำ/manifestในrepo/DBอื่น/otherclients ตรวจexistingpublicvalues/rowdeltaและpostflightด้วยconnectionใหม่ |
| [test_topic_vote_fixture_install.py](../../database/tests/test_topic_vote_fixture_install.py) | Offline13tests: guard/idempotency/manifestก่อนCOMMIT/ก่อนCOMMITล้มเหลว/COMMITไม่ชัดเจน/หลังCOMMITตรวจไม่ผ่าน/ข้อมูลเดิมเปลี่ยน/hash |

### ผลตรวจขั้นติดตั้งและรันจริง

| รายการ | ผล / หลักฐาน |
|---|---|
| Preflight | PASS52functionsตรงsource/differences=[]/effectiveappPublicACLตรงbaseline |
| Offlineinstaller+Topicrunner+rehearsal+sharedhelper+DBboundary | PASS71 / 0.181s (13+15+9+25+9); mocks ไม่ใช่ผลPGlocking |
| ติดตั้งครั้งแรก | PASS / APPLIED / 29แถว / committed=true / existing_public_rows_unchanged=true / schema_acl_unchanged=true |
| VC01–VC08 | **PASS8/8** / wait_observed=true / both_workers_rolled_back=true / public_rows_metadata_restored=trueทุกกรณี |
| Repeatapply | PASS / ALREADY_INSTALLED / additional_rows0 / written=false |
| FixtureTeam/Projectเดิม | PASS / CHECK / direct_app_login=true / written=false |
| FullBackendregressionหลังติดตั้ง | **PASS386 / 78.507s** (349เดิม + TopicConcurrencysafeguards24 + installer13); ทุกDBsuiteROLLBACKคืนbaselineที่มีข้อมูลเดิมและfixtures |
| FullBrowserregressionหลังติดตั้ง | **PASS90 / 2.0min** / browser_database_rollback=PASS / fixture_connections0; ใช้sourceFrontendเดิม |
| Finalreadonlypostflight | PASS52functions/differences=[]/effectiveappPublicACLตรงsource; manifestทั้งTopicและTeamvalid; topicfixtureusers8ในnamespaceเดียว/temporarybrowserusers0/otherclients0 |
| Source/docs/secret audit | PASS68productionFrontend-Backend-SQLfilesไม่เปลี่ยนจากก่อนติดตั้ง; 7ไฟล์ในขอบเขตผ่านAST/encoding/whitespace/ลิงก์และไม่พบค่าลับจาก.env; staged0/gitdiffcheckผ่าน |

ไม่มีruntimepermissiondenied/SQLfailureใน8กรณี จึงไม่เพิ่มสิทธิ์หรือเปลี่ยนproductioncodeเพื่อให้ผ่าน SQLSTATE42501/uncertainCOMMITในOfflinetestsเป็นการจำลองข้อผิดพลาดเพื่อพิสูจน์safety ไม่ใช่ปัญหาที่พบในbaselineจริง

**ขอบเขตที่ยังไม่พิสูจน์:** winner-COMMIT (เช่นVoteแรกบันทึกถาวรแล้วผู้แก้rosterต้องถูกปฏิเสธหลังรอ), HTTPmulti-session, 40001/retry, peerSubmissionAPIส่งรอบใหม่พร้อมVote, Evaluation/Taskconcurrency และUAT บันทึกseedถาวร29แถวไม่ได้อนุมัติให้COMMITbusinessactionsของVCหรือรอบถัดไป P12/P18ยังInProgressและDone5/20=25%

### ใช้ชุดที่ติดตั้งแล้ว

```powershell
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Topic_Vote_Concurrency_Fixture_Install --check --manifest $topicFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.topic_vote_concurrency --run-rollback --fixture $topicFixtureManifest
```

ใช้manifestเดิมของเครื่อง/DBนี้ รันบนtestDBที่ไม่มีงานเขียนอื่นพร้อมกัน ไม่ย้ายpathเพื่อสร้างfixtureถาวรชุดที่สอง ไม่ใช้manifestTeam/Projectแทน ส่วนDRY RUNยังไม่มีapplymodeและยังROLLBACKเสมอ

รอบนี้เพิ่มinstaller/testsและอัปเดตเอกสารเท่านั้น ไม่รันlint/TypeScript/productionbuildซ้ำเพราะsourceFrontend/Backend/SQL68ไฟล์ตรงก่อนรอบนี้ ตรวจBackend386และBrowser90ใหม่เพราะมีbaselineข้อมูลตั้งต้นเพิ่ม ไม่แก้.env/dependenciesหรือGitCommit/Push

## ประวัติขั้นเตรียมก่อนอนุมัติ

เนื้อหาส่วนนี้เป็นผลรอบเตรียมก่อนบันทึกfixture ข้อความNotRun/ยังไม่อนุมัติด้านล่างใช้กับsnapshotนั้น ผลล่าสุดอยู่ด้านบน

**สถานะในรอบเตรียม: runnerและDRY RUNผ่าน; VC01–VC08หลายconnectionยังNotRun** ยังไม่มีfixtureถาวรในขั้นนั้น การซ้อมsequentialไม่ใช่ผลConcurrency

รอบนี้ต่อจาก [Topic votes ที่พัฒนาแล้ว](TOPIC_VOTES_IMPLEMENTATION_REPORT.md) เพื่อเตรียม TX02 และการอ่านผลตาม [Contract](../api/TOPIC_VOTES_CONTRACT.md) ไม่เปลี่ยน runtime/API/UI/Schema/RBAC หรือ source Submission/Milestone/Supabase ของเพื่อน

## ไฟล์ที่เพิ่ม

| ไฟล์ | หน้าที่ |
|---|---|
| [topic_vote_concurrency.py](../../backend/tests/topic_vote_concurrency.py) | 8 กรณี ใช้ repository/controlled SQL เดิม แยก worker A/B และ observer; default Offline; ต้องระบุ manifest ของ fixture ที่ตรวจรับแล้ว |
| [Topic_Vote_Concurrency_Fixture.py](../../database/tools/Topic_Vote_Concurrency_Fixture.py) | สร้างข้อมูลจำลองเฉพาะ namespace ใหม่ ซ้อม A/B แยก savepoint แล้ว ROLLBACKทั้งหมด ไม่มี apply/COMMIT/export mode |
| [test_topic_vote_concurrency.py](../../backend/tests/test_topic_vote_concurrency.py) | Offline guards 15 tests สำหรับ manifest/scope, SELECT-only validation, worker cleanup, wait evidence และ sanitized SQLSTATE |
| [test_topic_vote_fixture.py](../../database/tests/test_topic_vote_fixture.py) | Offline guards 9 tests สำหรับ DRY RUN/row delta/baseline/permission/connection failure |
| [ตัวอย่าง manifest](../../backend/tests/fixtures/topic_vote_concurrency.example.json) | ไม่มี secrets ใช้ placeholder ที่จงใจผ่าน validation ไม่ได้ ห้ามแทนด้วย ID ของผู้ใช้จริง |

อัปเดต Backlog, Local setup และบันทึกรับช่วงงานเพื่อนเพื่อแยกผลซ้อม/ผลหลาย connection ไม่แก้ runner/fixture ของ Team/Project รอบเดิม

## สถานการณ์ที่เตรียมไว้

ใช้ A ทำก่อนโดยค้าง transaction, B ทำพร้อมกัน, observerต้องพบ PID ของ A ใน `pg_blocking_pids(B)` จริง เมื่อพบจึงให้ **A ROLLBACK** แล้วให้ B ตรวจผลและ **ROLLBACK** ด้วย ไม่มี winner-COMMIT/HTTP concurrency ในชุดนี้

| ID | A ก่อน ROLLBACK | B ที่ต้องรอ | ผลที่คาดหลัง A ROLLBACK |
|---|---|---|---|
| VC01 | Vote แรก | Coordinator เพิ่มกรรมการสำรอง | เพิ่มได้ เพราะ Vote ของ A ถูกย้อนคืน; roster4คนในBก่อนBROLLBACK |
| VC02 | Vote แรก | Coordinator เปลี่ยนกรรมการหนึ่งคน | เปลี่ยนได้ roster3คน และไม่มี Vote ของ A ค้าง |
| VC03 | Vote แรก | Coordinator ถอดกรรมการหนึ่งคน | ถอดได้ rosterเหลือ2คนเพราะยังไม่มี Vote ที่บันทึกถาวร |
| VC04 | ถอดกรรมการที่จะลงมติ | กรรมการคนนั้นลงมติ | อ่าน assignment หลังรอแล้วลงได้เพราะการถอดถูกย้อนคืน |
| VC05 | กรรมการ B ลงมติ | กรรมการ B ลงซ้ำ | B ลงได้หนึ่งครั้งหลัง Vote ของ A ถูกย้อนคืน ไม่ใช่หลักฐาน duplicateหลังwinner-COMMIT |
| VC06 | กรรมการ B ลงมติ | กรรมการ C ลงมติ | Btransactionมีเฉพาะ Vote ของ C; decisionยังnull ไม่เห็น Vote ของ A |
| VC07 | สร้างรอบใหม่พร้อมไฟล์จากProjectที่ผลเดิมขอแก้ไข | สมาชิกทีมอ่านผล | เห็นเฉพาะรอบเดิม/ผลขอแก้ไข/comments3ข้อความ ไม่เห็นรอบที่ A ย้อนคืน |
| VC08 | สมาชิกทีมอ่านผลและถือProjectlock | กรรมการลงมติ | Vote รอ reader แล้วลงได้หนึ่งครั้งหลัง readerคืนlock |

ทุกกรณีใช้3PIDต่างกัน, test DB/effective role/physical session_user=project_app/Read Committedตามhelperเดิม, boundedstatement/locktimeouts ไม่มีauto-retry, ไม่มีowner fallback และไม่ปิดsessionของผู้ใช้ Cancelได้เฉพาะworkerconnectionที่runnerเปิดเอง

หลังแต่ละกรณีต้องตรวจ fingerprint ของค่าข้อมูล public14ตารางและ metadata/owners/ACL/definitions/constraints/triggers/roleattributes เทียบ baseline ไม่ตรวจเพียงจำนวนแถว ไม่อ่าน credential/session values และไม่รวม identitysequence values ซึ่งROLLBACKไม่คืน

## ทำไมยังรันหลาย connection ไม่ได้

Fixtureที่สร้างแล้ว ROLLBACKใน DRY RUN มองเห็นได้เฉพาะconnectionที่สร้าง Connectionที่สองไม่เห็นข้อมูลที่ยังไม่COMMIT จึงใช้IDsจากDRY RUNเป็นsharedfixtureไม่ได้ และไม่ใช้Projectจริงของทีมแทน

fixtureเดิมของ Team/Project10แถวต้องไม่มีworkflowchildrenเพื่อใช้RC01–RC08 จึงไม่เพิ่มSubmission/กรรมการ/Voteถาวรลงfixtureนั้น เพราะจะทำให้ชุดเดิมตรวจรับไม่ได้ รอบนี้ซ้อมnamespaceใหม่แยกไว้ ไม่เปลี่ยนmanifestเดิมนอกGit

หากจะรันVCจริง จำเป็นต้องอนุมัติ **บันทึกเฉพาะข้อมูลตั้งต้น29แถว** ในtestDBก่อน แยกจากการทดสอบแต่ละกรณีที่ยังROLLBACK ขอบเขตที่เตรียมให้ตรวจมีดังนี้:

| ตาราง | แถว | รายละเอียด |
|---|---:|---|
| users | 8 | student2, advisor5 (ที่ปรึกษา1/กรรมการ3/สำรอง1), coordinator1; เป็นfixtureuser ไม่มีauth.credentials/sessionหรือรหัสผ่านLogin |
| teams / team_members / projects | 2 + 2 + 2 | 2ทีม แต่ละทีมมีleader1/Project1 แยกจากProjectจริงและfixtureเดิม |
| advisor_invitations | 2 | acceptedAdvisorของแต่ละProject |
| project_submissions / project_submission_files | 2 + 2 | approvedรอบแรกอย่างละ1 พร้อมDB-onlydummyfile ไม่ใช่ผลตรวจPDF/PPTXparser |
| committee_assignments | 6 | Projectละ3คน |
| committee_topic_votes | 3 | Projectrevisionลงครบขอแก้ไข3คน เพื่อซ้อมรอบใหม่; Projectmainยัง0Vote |
| **รวม** | **29** | ไม่มีAuth/Milestone/Task/Evaluation/DDL/grantdelta |

การบันทึกข้อมูลตั้งต้นยังไม่ทำ ไม่มีapplymodeในเครื่องมือปัจจุบัน ถ้าอนุมัติจึงเตรียมขั้นติดตั้งที่ตรวจpreflight/rowdelta/baseline/repeatapplyก่อน COMMITเฉพาะ29แถว และเก็บmanifestไว้นอกGit ไม่บันทึกactionsของVCถาวร

**ผลกระทบหากอนุมัติ:** 2Projectจำลอง/ข้อมูลตั้งต้นจะคงอยู่ในtestDB; R-01ห้ามลบProject จึงไม่เสนอDELETEเพื่อcleanup คำสั่งVCทุกครั้งกลับสู่baselineที่มี29แถวนี้ หากยังไม่อนุมัติจะคง runnerพร้อมรันแต่ไม่อ้างผลConcurrencypass และไม่มีข้อมูลถาวรใหม่

## ผลตรวจจริงรอบนี้

| รายการ | ผล | ข้อจำกัด |
|---|---|---|
| Offline safeguards ใหม่ | PASS24 / 0.086s | mocks ไม่อ่าน.env/ต่อDB ไม่พิสูจน์lockจริง |
| Offlineใหม่+sharedhelper+DBboundary | PASS58 / 0.177s | 24ใหม่ + sharedhelper25 + boundary9; helperrollback/identity/wait/cleanupถูกทดสอบโดยไม่เปิดPG |
| Preflight baseline | PASS | testDB52functions differences=[]; effective app privileges/PublicACLตรงsource |
| DBสงบก่อนเริ่ม | PASS | readonlyตรวจotherclientconnections0 ก่อนDRY RUN |
| Fixture DRY RUN | **PASS29แถว / 16sequentialactions** | ทุกactionใช้effectiveproject_appและforcedconstraints; ownerที่ไม่ใช่superuserเตรียมเฉพาะ8users |
| หลังDRY RUN | PASS | metadata/ACL/rowcounts/fullpublicvaluesคืนbaseline; committed=false, manifest_exported=false, multisession_tested=false |
| Topic+Committee HTTP regression | **PASS32 / 23.578s** | Topic17 + Committee15 พร้อมouterROLLBACKและbaseline; ไม่ใช่multi-session |
| Readonly postflight | PASS | physical/effectiveproject_appในtestDB; newTopicfixtureusers0/otherclientconnections0หลังปิดชุดทดสอบ |
| Source/docs/secret audit | PASS | ตรวจ9ไฟล์: PythonAST/encoding/whitespace/ลิงก์เอกสารผ่าน ไม่พบcommitcallใน4Pythonใหม่หรือค่าลับจาก.envในไฟล์ที่ตรวจ; staged0/gitdiffcheckผ่าน |
| Offline CLI / placeholder | PASSตามเกณฑ์ | defaultไม่ต่อDB; exampleถูกปฏิเสธVOTE_MANIFEST_NAMESPACEก่อนเปิดconnection |
| VC01–VC08 หลายconnection | **Not Run / Not Verified** | ยังไม่มีsharedfixtureที่อนุมัติบันทึก |
| Winner-COMMIT / HTTPconcurrency / 40001/retry / UAT | **Not Run / Not Verified** | ไม่อยู่ในrunnerหรือการอนุมัติรอบนี้ |
| Frontend build/Browser/fullBackend349 | ไม่รันซ้ำในรอบนี้ | ไม่เปลี่ยนproduction source; 349/Browser90เป็นผลรอบTopicimplementationตามรายงานเดิม |

ไม่มี runtime permission deniedในการซ้อม หากเกิดจริงrunnerจะแสดงfixedreason/stage/SQLSTATEเท่านั้นและหยุดพร้อมROLLBACK ไม่เพิ่มgrantเอง ไม่แสดงSQL/DSN/parameters/secret

## คำสั่งที่รันได้ตอนนี้ (Windows/PowerShell จาก root)

Offlineไม่ต่อDB:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.topic_vote_concurrency
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Topic_Vote_Concurrency_Fixture
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_topic_vote_concurrency database.tests.test_topic_vote_fixture backend.tests.test_team_project_concurrency_harness database.tests.test_test_database -q
```

DRY RUNเขียนเฉพาะtransactionที่ROLLBACK ตรวจDBก่อนและหยุดการเขียนtestDBจากชุดอื่น:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Topic_Vote_Concurrency_Fixture --dry-run
```

โหมดต่อไปนี้ใช้ภายหลังsharedfixtureได้รับอนุมัติและติดตั้งจริงแล้วเท่านั้น อย่าสร้างmanifestจากIDsที่DRY RUNย้อนคืน:

```powershell
$topicFixtureManifest = Join-Path $env:LOCALAPPDATA 'StudentProjectManagement\concurrency\topic-vote-v1.json'
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.topic_vote_concurrency --preflight --fixture $topicFixtureManifest
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.topic_vote_concurrency --run-rollback --fixture $topicFixtureManifest
```

P12/P18คงInProgress Done5/20=25%เป็นอัตราปิดchecklist ไม่เพิ่มผลจากoffline/sequentialเป็นConcurrencypass งานไฟล์SubmissionและMilestoneของเพื่อนยังรักษาขอบเขตเดิมตาม [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)
