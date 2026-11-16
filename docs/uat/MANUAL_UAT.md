# Manual UAT — แผนทดลองและแบบบันทึกผล

วันที่ 2026-11-15 · **สถานะ UATโดยผู้ใช้: Not Run** · อ้างอิง working treeที่มี Workspace/API/UIตาม [คู่มือผู้ใช้](../user/USER_GUIDE.md)

เอกสารนี้เป็นแผนตรวจรับจาก Contractที่ยืนยันแล้ว ไม่เพิ่ม Business Rules/NFR หรือรับรองว่าทั้งระบบเสร็จ เจ้าของงานต้องทดลองและบันทึกผลเอง ผลอัตโนมัติที่อ้างในตารางเป็นหลักฐานประกอบคนละประเภท

## 1. เตรียมสภาพแวดล้อมแบบ ROLLBACK

ใช้ Windows/PowerShell จาก rootของโค้ดชุดเดียวกับเอกสารนี้ ติดตั้ง V1/Authและตั้ง private configบนเครื่องตาม [LOCAL_SETUP](../team/LOCAL_SETUP.md) แล้ว ใช้เฉพาะ `student_project_management_v1_test` ไม่มีขั้นตอนสร้างDB/ติดตั้งSQL/เพิ่มgrantsในคู่มือนี้

หยุด Frontendหรือtest runnerเดิมที่ใช้3000/8001ด้วยCtrl+CจากTerminalของตน และหยุดงานเขียนtest DBอื่นก่อนเริ่ม เพื่อให้เปรียบเทียบbaselineได้ ไม่ปิด processที่ไม่ทราบเจ้าของหรือใช้DBหลักแทน

มี2Terminal: **Aเปิดrollback Backend8001** และ **BเปิดFrontend3000ที่ชี้8001** Browserเข้าด้วย `localhost` โหมดนี้ใช้ได้กับการลอง workflowแต่ไม่ใช่ load/concurrency test เพราะทุกrequestยืมconnectionเดียวและมีlockคุมUOW

### Terminal A — เก็บ baseline และเปิด Backend

อ่าน configจากเครื่องโดยไม่แสดงรหัสผ่าน ตรวจsnapshotก่อนเปิด หากคำสั่งFAILหรือมีfixture connectionอยู่แล้วให้หยุดตรวจ

```powershell
$uatBefore = (& .\backend\.venv\Scripts\python.exe -B -m backend.tests.auth_browser_server --snapshot) | ConvertFrom-Json -ErrorAction Stop
if ($LASTEXITCODE -ne 0 -or -not $uatBefore.metadata_sha256 -or $uatBefore.fixture_connections -ne 0) { throw 'UAT baseline is not ready' }
```

เปิดfixtureแบบdirect project_app ไม่สร้างstaff/phasefixturesอัตโนมัติ ค่าenvเป็นของTerminalนี้และคืนค่าเดิมเมื่อออก:

```powershell
$uatSavedRollbackMode = $env:SPMS_AUTH_BROWSER_ROLLBACK
$uatSavedStaffMode = $env:SPMS_INVITATION_BROWSER_FIXTURES
try {
    $env:SPMS_AUTH_BROWSER_ROLLBACK = '1'
    $env:SPMS_INVITATION_BROWSER_FIXTURES = '0'
    & .\backend\.venv\Scripts\python.exe -B -m backend.tests.auth_browser_server
} finally {
    $env:SPMS_AUTH_BROWSER_ROLLBACK = $uatSavedRollbackMode
    $env:SPMS_INVITATION_BROWSER_FIXTURES = $uatSavedStaffMode
}
```

**อย่าเปิด normal Backend8000เพื่อทดลองเขียนแทน:** โหมด8000COMMITตามปกติ ส่วน8001ยืมconnectionภายในouter transactionแบบforce_rollback ทั้ง10UOWและยกเลิกข้อมูลเมื่อปิด สำเร็จ201ในโหมด8001จึงไม่ได้หมายความว่าข้อมูลจะคงอยู่หลังหยุดserver

### Terminal B — ตรวจ Backendแล้วเปิด Frontend

เปิดTerminalใหม่จากroot ตรวจ8001ตอบ200ก่อน แล้วใช้environmentเฉพาะprocess ไม่แก้ `.env`/`.env.local`:

```powershell
(Invoke-WebRequest -Uri 'http://localhost:8001/' -UseBasicParsing).StatusCode
$uatSavedApiBase = $env:NEXT_PUBLIC_API_BASE_URL
Push-Location frontend
try {
    $env:NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8001'
    npm run dev -- --hostname localhost --port 3000
} finally {
    $env:NEXT_PUBLIC_API_BASE_URL = $uatSavedApiBase
    Pop-Location
}
```

เข้า `http://localhost:3000/login` ก่อนสมัคร/สร้างข้อมูล ให้ดูNetworkของBrowserว่าคำขอแอปใช้ **localhost:8001** ถ้าพบ8000/hostอื่นให้หยุดแก้การเปิดprocessก่อน ไม่กดเขียนต่อและไม่คัดลอกcookie/Authorization/รหัสผ่านจากNetworkลงรายงาน

## 2. ผู้ทดลองและบัญชี

| ผู้เล่น | วิธีเตรียมในรอบนี้ |
|---|---|
| นักศึกษา A/B/C | สมัครจากUIด้วยชื่อ/อีเมลจำลองคนละบัญชี กำหนดรหัสผ่านเองตามกฎ ไม่ใช้รหัสDB |
| advisor | ใช้บัญชีแอปที่ผู้ดูแลเตรียมไว้แล้วและผู้ทดลองทราบรหัสของตน |
| coordinator | ใช้บัญชีที่เตรียมผ่านCLIตาม [คู่มือ](../database/COORDINATOR_ACCOUNT_PROVISIONING.md) ไว้ก่อนแล้ว |
| กรรมการ | เป็นadvisorที่ได้รับแต่งตั้งในProjectที่มีpreconditionsพร้อม ไม่ใช่roleใหม่ |

ถ้าเครื่องทีมยังไม่มีstaff account ให้ระบุNot Readyสำหรับกรณีนั้น การเปิดโหมดนี้ไม่สร้างบัญชีถาวรหรืออนุมัติCLI `--apply`ใหม่ ไม่ให้รหัสผ่านตัวอย่าง/รหัสจริงในเอกสารนี้

เปิดคนละbrowser profile/private windowตามผู้เล่น แต่ยังใช้Frontend/Backendชุดเดียวกัน ถ้าเปลี่ยนบัญชีในprofileเดิมให้Logoutและตรวจชื่อ/บทบาทใหม่ก่อนทำรายการ

ห้ามใช้ usersจากshared concurrency manifests10+29+42แถวเป็นบัญชีLoginเอง หรือเพิ่ม credentialsให้fixtureเหล่านั้น การเตรียมadvancedphase/บัญชีเพิ่มต้องมีขอบเขตที่อนุมัติแยกต่างหาก

## 3. ตารางตรวจรับ

กรอกผลเป็น **Pass / Fail / Not Ready** หลังทำจริง ค่าเริ่มต้นทุกแถวเป็น **Not Run** หากpreconditionsไม่ครบให้บันทึกNot Readyพร้อมสาเหตุ อย่านับว่าPassหรือเปลี่ยนRequirementเพื่อให้ผ่าน ลำดับสาธิตพื้นฐานอยู่ใน [DEMO_SCRIPT](../user/DEMO_SCRIPT.md)

| ID | ผู้เล่น / Preconditions | ขั้นตอนและผลคาดหวัง | หลักฐานอัตโนมัติที่มี | ผลจริงรอบนี้ |
|---|---|---|---|---|
| UA01 | นักศึกษาใหม่ | สมัครถูกกฎได้student แล้วต้องLoginเอง ไม่เลือกรับroleสูงกว่าได้ | [Auth Browser](../../frontend/tests/auth.spec.ts) | Not Run |
| UA02 | หน้าregister | อีเมลผิด/ซ้ำ รหัสสั้น/ขาดA–Z/0–9 ถูกปฏิเสธ ไม่มีบัญชีซ้ำ | [Auth validation](../../backend/tests/test_auth_validation.py) | Not Run |
| UA03 | บัญชีที่มีอยู่ | รหัสผิดLoginไม่ได้ รหัสถูกเข้าได้ Logoutแล้วหน้าprotectedกลับLogin | [Auth Browser](../../frontend/tests/auth.spec.ts) | Not Run |
| UA04 | นักศึกษาไม่มีทีม | Workspaceแสดงไม่มีทีม ไม่อ่าน/สร้างProjectข้ามC-01 | [Workspace9](../../frontend/tests/workspace.spec.ts) | Not Run |
| UA05 | นักศึกษา Aไม่มีทีม | สร้างทีมพร้อมหัวหน้า อ่านหลังrefresh มีหัวหน้าปัจจุบันหนึ่งคน | [Teams Browser](../../frontend/tests/teams.spec.ts) | Not Run |
| UA06 | Aหัวหน้า/Bสมัครยังไม่มีทีม | เพิ่มBด้วยอีเมลเป็นmemberทันที Bอ่านรายชื่อได้แต่เพิ่มสมาชิกไม่ได้ | [Members Browser](../../frontend/tests/team-members.spec.ts) | Not Run |
| UA07 | ทีมในphaseแก้ได้ | หัวหน้าแก้metadata/ยกเลิกฟอร์มได้ memberไม่มีสิทธิ์แก้ ไม่มีการเขียนเมื่อยกเลิก | [Team update](../../frontend/tests/team-update.spec.ts) | Not Run |
| UA08 | Aหัวหน้าทีมยังไม่มีProject | Aสร้างได้ Bรอ/อ่านProjectของทีม Cไม่มีทีมไม่เห็นProjectนี้ | [Projects Browser](../../frontend/tests/projects.spec.ts) | Not Run |
| UA09 | Projectในphaseแก้ได้ | ชื่อ/คำอธิบายแก้ตามสิทธิ์และphase ไม่มีปุ่มลบProject/R-01ยังบังคับ | [Project update report](../progress/PROJECT_UPDATE_IMPLEMENTATION_REPORT.md) | Not Run |
| UA10 | มีadvisor account/Projectพร้อม | ส่ง–ยกเลิก–ปฏิเสธก่อนตอบรับ เก็บประวัติ; acceptedแล้วเปลี่ยนอาจารย์ไม่ได้ | [Invitations Browser](../../frontend/tests/invitations.spec.ts) | Not Run |
| UA11 | Aหัวหน้า/Bmember | ยกเลิกconfirmationแล้วroleไม่เปลี่ยน; ยืนยันโอนแล้วBได้สิทธิ์/Aเสียสิทธิ์หัวหน้า | [Transfer Browser](../../frontend/tests/leader-transfer.spec.ts) | Not Run |
| UA12 | memberในทีม; กรณีC-02ต้องมีTaskfixtureที่อนุมัติ | ออก/ถอดแล้วเสียสิทธิ์เดิมแต่Loginยังอยู่; ถ้าin_progressจะไร้assigneeต้องปฏิเสธทั้งหมด | [Exit Browser](../../frontend/tests/membership-exit.spec.ts) | Not Run |
| UA13 | advisor/coordinator accounts | Workspaceมีเมนูตามrole ไม่เรียกstudent API; advisorเห็นProjectที่accepted/assignedตามสิทธิ์ | [Workspace Browser](../../frontend/tests/workspace.spec.ts) | Not Run |
| UA14 | มีapprovedSubmission/Coordinator/กรรมการก่อนVoteแรก | เพิ่ม/เปลี่ยน/ถอดถูกสิทธิ์ ห้ามadvisorซ้ำ/acceptedAdvisor และล็อกหลังVoteแรก | [Committee Browser](../../frontend/tests/committee.spec.ts) | Not Run |
| UA15 | latestหัวข้อผ่านอาจารย์/กรรมการ≥3พร้อมLogin | Voteครั้งเดียวต่อรอบ; ก่อนครบไม่รั่วผลของคนอื่น หลังครบเปิดข้อมูลตามบทบาท | [Topic Browser](../../frontend/tests/topic-votes.spec.ts) | Not Run |
| UA16 | latestหัวข้อผ่านกรรมการ/completedMilestone≥1 | คะแนน0/100ได้ -1/101/80.5หรือcommentว่างไม่ได้; ยืนยันแล้วimmutable/first-scorelock/privacy/รวมเฉลี่ยตามContract | [Evaluation Browser](../../frontend/tests/evaluations.spec.ts) | Not Run |
| UA17 | บัญชีA/Bคนละทีม/role | สลับบัญชีหรือหมดsessionแล้วไม่ค้างข้อมูลเดิม Direct URLไม่เพิ่มสิทธิ์ให้ผู้ใช้ | [Workspace Browser](../../frontend/tests/workspace.spec.ts) | Not Run |
| UA18 | แผนจำลองnetworkที่ควบคุมและคืนค่าได้ | ผลเขียนไม่แน่นอนต้องGETตรวจ ไม่autoPOSTซ้ำหรือบอกสำเร็จโดยเดา | [Evaluation recovery](../../frontend/tests/evaluations.spec.ts) | Not Run |
| UA19 | BrowserDesktop/Mobile/keyboard | กรอกและอ่านได้ ไม่มีhorizontal overflow โฟกัสมองเห็น ใช้Tabเข้าลิงก์/ปุ่มได้ | [Workspace visual/keyboard](../progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) | Not Run |
| UA20 | จบทุกการทดลองและserver8001ปิด | เปรียบเทียบsnapshot metadata/ACL/rowcountsกลับเดิม fixture connection0 | ขั้นตอนท้ายเอกสารนี้ | Not Run |

**เพิ่มรอบ 2026-11-16:** มี Submission/Milestone/Task API/UI สำหรับทีมแล้ว จัดเตรียม approved Submission, Task/assignee และ completed Milestone ผ่านเว็บตามกฎได้ ไม่เปลี่ยนผลจริงของกรณีเดิมเป็น PASS จากผล automated tests

เพิ่มสี่กรณีด้านล่าง รวมแผน 24 กรณี ให้ทำก่อนจบรอบ UA20:

| ID | Preconditions | Expected | หลักฐาน automated | ผลจริงโดยผู้ใช้ |
| --- | --- | --- | --- | --- |
| UA21 | หัวหน้าทีม/Project/accepted advisor พร้อม Login | ส่ง PDF/PPTX หนึ่งไฟล์, refresh/download ได้; อาจารย์อนุมัติหรือขอแก้ไขพร้อมคำแนะนำและยืนยันครั้งเดียว; เก็บรอบเก่าและส่งรอบใหม่ได้เมื่ออนุญาต | [Submission Browser](../../frontend/tests/submissions.spec.ts) | Not Run |
| UA22 | ทีมมี Project; หัวหน้า/member พร้อม | หัวหน้าสร้าง/แก้/ยืนยันลบ Milestone ว่าง สมาชิกอ่าน; สถานะ derive ไม่ editable; Task/first-score cases ใช้เมื่อมี precondition จริงเท่านั้น | [Milestone Browser](../../frontend/tests/milestones.spec.ts) | Not Run |
| UA23 | Milestone/ทีมปัจจุบัน ไม่มี Evaluation แรก | หัวหน้าสร้าง/แก้/มอบหมาย/ยืนยันถอน-ลบ Task สมาชิกเปลี่ยนสถานะตาม V1; in_progressห้ามไร้ผู้รับผิดชอบ; ถอนแล้วมี history จริง และลบ Task cascade ตามกฎ | [Task Browser](../../frontend/tests/tasks.spec.ts) | Not Run |
| UA24 | หัวข้อล่าสุดผ่านมติและกรรมการได้รับแต่งตั้งถูกต้อง | ทำ Task จน Milestone completed ผ่านเว็บ จากนั้นกรรมการให้คะแนนได้; คะแนนแรกล็อกงานและไม่เปิดผลผู้อื่นก่อนครบ | [Task→Evaluation Browser](../../frontend/tests/tasks.spec.ts) | Not Run |

หากขาด precondition ให้ระบุ Not Ready ไม่ใช้ SQL สร้าง/แก้ phase หรือ grant เอง และไม่บันทึกข้อมูลจำลองถาวรเพื่อให้กดทดสอบได้

## 4. จบรอบและตรวจ ROLLBACK

LogoutในBrowserขณะ8001ยังเปิด ปิดFrontendในTerminal Bด้วยCtrl+C แล้วปิดBackendในTerminal Aด้วยCtrl+C รอจนกลับprompt จากนั้นรันบล็อกนี้ **ในTerminal Aเดิมที่มี `$uatBefore`**:

```powershell
$uatAfter = (& .\backend\.venv\Scripts\python.exe -B -m backend.tests.auth_browser_server --snapshot) | ConvertFrom-Json -ErrorAction Stop
if ($LASTEXITCODE -ne 0 -or -not $uatAfter.metadata_sha256) { throw 'UAT postflight failed' }
$uatRowsBefore = $uatBefore.row_counts | ConvertTo-Json -Compress
$uatRowsAfter = $uatAfter.row_counts | ConvertTo-Json -Compress
$uatRestored = $uatBefore.metadata_sha256 -eq $uatAfter.metadata_sha256 -and $uatRowsBefore -eq $uatRowsAfter -and $uatAfter.fixture_connections -eq 0
if (-not $uatRestored) { throw 'UAT baseline differs; stop and investigate without changing data' }
'UAT ROLLBACK / metadata / row counts / connection cleanup: PASS'
```

การกดCtrl+Cอาจให้ process exit code1บนWindows ให้ตรวจpostflightแยกตามข้างต้น ไม่ใช้exitcodeจากการขัดจังหวะเป็นผลUAT กรณีsnapshotต่างให้เก็บอาการแล้วหยุด ไม่ลบProject/แก้baselineหรือรันCOMMITเพื่อจัดการเอง

Snapshotนี้ตรวจdefinitions/owners/ACLและrow counts ไม่ใช่hashข้อมูลทุกแถว และ **identity sequence valuesไม่คืนเมื่อROLLBACK** จึงไม่ใช้เลขIDที่กระโดดเป็นหลักฐานว่ามีแถวค้าง ข้อมูล/บัญชีที่สร้างในรอบ8001หายหลังปิดตามวัตถุประสงค์ ไม่ใช่bugของRegister ส่วนseedที่อนุมัติไว้ก่อนและบัญชีเดิมยังเป็นbaseline

กลับไปเปิดnormalserverภายหลังต้องLoginใหม่ ไม่ใช้sessionจากfixtureที่ปิดแล้ว เอกสารนี้ไม่อนุมัติให้เขียนข้อมูลถาวรในnormalmode

## 5. แบบบันทึกผลและปัญหา

| รายการ | กรอกโดยผู้ทดลอง |
|---|---|
| วันที่/ชื่อผู้ทดลอง/ผู้ตรวจรับ | ยังไม่ระบุ |
| Branch/commit/working-tree version | บันทึกจาก `git status --short` และ `git log -1 --oneline` โดยไม่แสดง.env |
| DB / API / Frontendที่ใช้ | test DB / localhost:8001 / localhost:3000; ตรวจจริงก่อนเริ่ม |
| Browser/viewport/ผู้เล่นที่ใช้ | ระบุroleและชื่อจำลอง ไม่บันทึกรหัสผ่าน/session |
| UA IDsที่ทำ / Pass / Fail / Not Ready | ยังไม่มีผล |
| ขั้นตอน / ผลคาดหวัง / ผลจริง | แนบตามContractและข้อความที่เห็น |
| หลักฐาน / ผู้รับผิดชอบ / วิธีทดสอบซ้ำ | ภาพหรือHTTPstatusที่ไม่มีsecrets; ระบุเจ้าของงานเมื่อทราบ |
| ROLLBACK postflight / การยอมรับผล | ยังไม่ได้ตรวจรับโดยผู้ใช้ |

อัตราผ่านถ้าจะคำนวณ ใช้ `Pass / (Pass+Fail)` เฉพาะกรณีที่ทดลองจริง และรายงานNot Ready/Not Runแยกเสมอ ไม่ให้เปอร์เซ็นต์เมื่อยังไม่มีกรณีที่รัน และไม่เท่ากับเปอร์เซ็นต์ความเสร็จของProject

## 6. หลักฐานตรวจวิธีเปิดโหมดก่อนส่งคู่มือ

ผู้ช่วยทวนสคริปต์เดิมแบบdefault direct LOGINproject_appจริงบนtest DB 2026-11-15: ROOT200/Register201/Login200/Me200/Team201/Team200/Project201/Project200/Logout204 รวม9คำขอผ่าน สร้างชื่อ/อีเมล/รหัสจำลองในหน่วยความจำ ไม่แสดงข้อมูลบัญชี แล้วปิดด้วยCtrl+C ตรวจmetadata/owners/ACL/rowcountsคืนbaselineและfixture connection0 ไม่แก้source/Schema/RBACหรือบันทึกข้อมูลถาวร

นี่เป็น **startup/API/teardown probe** ไม่ใช่ผลManual UAT20กรณี ไม่ใช่การรับรองว่าคนในทีมทดลองแล้ว และไม่ใช่การตรวจเครื่องทีมอื่น/fresh install พฤติกรรมsourceอ้าง [auth_browser_server.py](../../backend/tests/auth_browser_server.py) ผลBrowser109/lint/TypeScript/buildเป็นรอบWorkspaceก่อนจัดเอกสารนี้

ตรวจเอกสารรอบนี้: PowerShell4บล็อกผ่าน parserแบบไม่execute, ลิงก์ภายใน262จุดไม่มีbroken link, ไม่พบprivate secretใน9ไฟล์ที่ตรวจ protected SQL/Auth/Invitation/dependency/Auth client14ไฟล์ตรงHEADหลังnormalizeEOLและwhitespaceผ่าน ไม่มีsource/config/Schema/RBAC/ข้อมูลถาวรหรือGitstaging/Commit/Pushเปลี่ยนจากงานคู่มือนี้ P20เริ่มIn Progressแต่ยังไม่มีการตรวจรับโดยผู้ใช้
