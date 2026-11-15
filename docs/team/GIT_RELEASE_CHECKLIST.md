# ตรวจและส่งโค้ดในGit

**รอบปัจจุบัน 2026-11-15:** ดู [รายงานเตรียมส่งต่อ](RELEASE_PREPARATION_2026-11-15.md) งานใหม่อยู่ใน `feature/project-continuation` เจ้าของอนุมัติ Commit/Push ไป branch นี้แล้ว ตรวจ branch/remote และ staged files ก่อนส่งจริง

การเตรียม handoff อย่างเดียวไม่ใช่คำสั่ง stage/Commit/Push ต้องได้รับอนุมัติขอบเขตและปลายทางก่อน รอบนี้ได้รับอนุมัติส่งชุดที่ตรวจแล้วไป `origin/feature/project-continuation` โดยไม่ merge งานเพื่อนหรือแก้ `main`

## สิ่งที่ต้องอยู่ในcommitส่งต่อ

- backend runtime/Auth/Team/Project/Invitations/Committee/Topic votes/Evaluation และtests/requirements/devrequirements รวม concurrency helpers/fixtures
- frontend routes/features/config/package.json/package-lock.json/tests/runner รวมAGENTS.mdของNext
- database schema/auth/migrations/tools/tests/README และ.gitattributesที่รักษาSQLเป็นLFตามpinnedchecksums
- docs/api, docs/database, docs/progress, docs/team, docs/user, docs/uat และhistoricalhandoff/sourcesที่ยังใช้อ้างอิง
- .gitignore และconfigexamplesที่passwordว่าง โดยเฉพาะbackend/.env.exampleใหม่

หลายไฟล์ของรอบTeam/Project/Invitations/Provisioningเป็นuntrackedก่อนhandoff ถ้าcommitเฉพาะREADMEทีมจะไม่มีAPI/helpers/testsครบ ห้ามลบscriptsเดิมเพียงเพราะชื่อคล้ายกัน; บางตัวเป็นsharedimportsหรือหลักฐานDB-only

## สิ่งที่ไม่ส่ง

.envจริง/.env.local/privatepassword/hash/sessiontoken/DBdump, .venv, node_modules, .next, __pycache__, playwright-report/test-results/coverage และIDE/OSartifactsที่ignoreไว้ อย่าใช้git add -fเพื่อข้ามsecretignore บัญชีในPostgreSQLไม่ติดGitไปด้วย

หากใช้เว็บอัปโหลดไฟล์หรือส่งzipทั้งWorkspaceต้องคัดไฟล์เช่นกัน .gitignoreไม่ลบไฟล์จริงออกจากzip/การdrag-drop อย่าแนบ.envหรือdependencyfoldersไปให้ทีม

ตัวอย่างคำสั่งเจ้าของจากroot **เมื่อพร้อมส่งจริง**:

```powershell
git status --short
git diff --check
git ls-files --others --exclude-standard
git add -- .
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
```

ตรวจstageddiffบนเครื่องตนก่อนcommit ไม่ส่งdiffที่มีค่าprivateกลับแชท หากพบsecretให้เอาออกจากstaging/แก้exampleก่อน ไม่แก้ประวัติGitหรือforcepushเอง

หลังตรวจแล้วเจ้าของจึงใช้:

```powershell
git commit -m "Add team management, committee workflows, evaluations and workspace"
git push -u origin feature/project-continuation
```

นี่เป็นคำสั่งแนะนำสำหรับเจ้าของ ไม่ใช่หลักฐานว่าCommit/Pushเกิดแล้ว ตรวจremoteURL/branchให้ตรงก่อนรัน ไม่pushเข้าmainโดยข้ามreview

## สมาชิกตรวจชุดส่งต่อหลังเจ้าของPushแล้ว

```powershell
git fetch origin
git switch -c review/project-continuation origin/feature/project-continuation
```

ตัวอย่างนี้สำหรับ checkout ตรวจงานใน branch ใหม่เมื่อ working tree สะอาด สมาชิกที่มีงานเดิมต้องเก็บงานของตนก่อน ไม่สร้าง branch Submission/Milestone ซ้ำหรือทับ `feature/database-schema2` ของเพื่อน การรวมงานต้องตรวจจุดเชื่อมใน [SCHEMA2_INTEGRATION_HANDOFF.md](SCHEMA2_INTEGRATION_HANDOFF.md) ก่อน

ก่อนmergeแต่ละPRให้บันทึกbase/head, contractsที่อนุมัติ, changedfiles, tests/DBrollbackproof และข้อจำกัด โดยเฉพาะsharedmain.py/router/OpenAPI/harness/repositoryhelperที่สองทีมอาจแก้ชนกัน อย่าforcepush/reset/rebaseงานร่วมโดยไม่ได้ตกลง
