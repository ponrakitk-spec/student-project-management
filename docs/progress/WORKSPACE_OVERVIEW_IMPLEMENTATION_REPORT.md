# Workspace overview — Implementation and verification

วันที่ 2026-11-15 (Asia/Bangkok) · local `feature/project-continuation` บน `679913a` + working tree

ผู้ใช้ยืนยัน **“พัฒนาหน้าพื้นที่ทำงานตามร่าง”** ใน [Workspace Contract](../api/WORKSPACE_OVERVIEW_CONTRACT.md) เพิ่มหน้า `/workspace` และลิงก์จากหน้าบัญชีแล้ว ใช้ API/สิทธิ์เดิม ไม่เปลี่ยน Requirements/Schema/RBAC หรือ source Submission/Milestone/Supabase ของเพื่อน

## พฤติกรรมที่เพิ่ม

- หลัง Login ยังกลับหน้าบัญชี `/` ตามเดิม กด **พื้นที่ทำงาน →** เพื่อเปิดหน้าใหม่ มีลิงก์กลับบัญชี
- student อ่านชื่อ/คำอธิบายทีมและ membershipของตนจาก `GET /api/v1/teams/me` ถ้ามีทีมจึงอ่าน `GET /api/v1/projects/me` เพื่อแสดง Projectของทีม
- ไม่มีทีม: แสดงเริ่มสร้างทีมและลิงก์ไป `/teams`; มีทีมแต่ไม่มี Project: leaderมีลิงก์ไปฟอร์มเดิม `/projects` ส่วนmemberเห็นว่าหัวหน้าทีมเป็นผู้สร้าง ไม่ข้าม C-01/สร้าง Projectจากหน้าภาพรวมเอง
- มี Project: แสดงข้อมูลจริงและลิงก์ไปหน้าจัดการเดิม ไม่มี write actionในหน้าภาพรวม
- advisorมีทางเข้า “คำเชิญของฉัน”, “โครงงานที่ปรึกษา”, “งานกรรมการ”; coordinatorมีทางเข้า “จัดการกรรมการโครงงาน” ใช้ scopeของปลายทางเดิม ไม่เรียก student APIสำหรับสองบทบาทนี้

หน้านี้เป็น workspace summary/navigation ที่ยืนยัน ไม่เพิ่มกราฟ/เปอร์เซ็นต์/จำนวนงาน/Contribution/Timeline/Notification เพราะ U03ยังไม่กำหนดนิยาม และไม่ถือว่า ST-01 Dashboardทั้งหมดพร้อมใช้

## การอ่านข้อมูลและความปลอดภัย

ใช้ AuthShell/useSession และ API clientsเดิมแบบ cookies/no-store แยก loading/error/empty และ retry เชื่อเฉพาะ `TEAM_NOT_FOUND`/`PROJECT_NOT_FOUND` ตาม Contractเดิม Generic404, 403, malformed response และ network errorไม่กลายเป็นการแสดงว่าไม่มีข้อมูล

ตรวจ positive BIGINT strings/ชื่อไม่ว่างตาม ASCII trim และ Project.team_idตรงกับ Team.idก่อนแสดงพร้อมกัน หาก scopeเปลี่ยนระหว่างคำขอให้ error/โหลดใหม่ ไม่รวมข้อมูลคนละทีม ข้อมูลยังเป็น snapshotจากสอง transaction ไม่ใช่ atomic snapshot สิทธิ์ของ actionที่หน้าปลายทางต้องตรวจโดย Backendทุกครั้งตามเดิม

student componentผูก keyกับuser.id ยกเลิกคำขอเมื่อ unmount/เปลี่ยนบัญชี เมื่อfocus/pageshowจะซ่อนภาพรวมเก่าและตรวจ sessionใหม่ก่อน mount/อ่าน business data ไม่มีข้อมูลส่วนตัว/sessionลง localStorage หรือ sessionStorage และไม่ใส่actorจากclientในpayload

## ไฟล์ที่เปลี่ยน

| ไฟล์ | เหตุผล |
|---|---|
| [workspace/page.tsx](../../frontend/src/app/workspace/page.tsx) | เพิ่ม route `/workspace` |
| [workspace-screen.tsx](../../frontend/src/features/workspace-overview/workspace-screen.tsx) | session/role gates, student overview, staff navigation, stale-request handling |
| [workspace.module.css](../../frontend/src/features/workspace-overview/workspace.module.css) | layout/cards/loading/error/focus/mobileตาม visual styleเดิม |
| [account-screen.tsx](../../frontend/src/features/auth/account-screen.tsx) | เพิ่มลิงก์ไปพื้นที่ทำงานหนึ่งรายการ ไม่เปลี่ยน Login/Logout |
| [workspace.spec.ts](../../frontend/tests/workspace.spec.ts) | Browser tests9กรณี ใช้ APIจริงใน fixture ROLLBACK และ transport/error mocks |
| เอกสาร | Contract/รายงานนี้/README/Frontend README/Backlog/LOCAL_SETUP/SCHEMA2_INTEGRATION_HANDOFF |

อ่าน frontend/AGENTS.md และ docsของ Next.js16.4.4ที่ติดตั้งจริงเรื่อง Server/Client Components และ Link ก่อน implement ไม่มี package/lockfileหรือdependencyเปลี่ยน

## ผลตรวจ

| ชุด | ผล |
|---|---|
| ESLint | PASS รวม source/testsใหม่ |
| TypeScript | PASS (`tsc --noEmit` และ production build type checking) |
| Production build | PASS มี route `/workspace` และไม่มี Backend/DB connectionระหว่าง build |
| Focused Browser | **9/9 PASS**, browser_database_rollback=PASS/fixture_connections=0 |
| Visual/keyboard | ตรวจ Desktop1440และMobile390จากภาพจริง ไม่มี horizontal overflow; Tabจากลิงก์กลับบัญชีไป reloadได้และเห็น focus outline |
| Full Browser | **109/109 PASS**, browser_database_rollback=PASS/fixture_connections=0 |
| DB postflight | **PASS**, V1 52 functions/differences=[]/effective app ACLตรงsource; manifests10+29+42แถว valid, workspace fixture users0/shared fixture credentials0/sessions0/client connectionsอื่น0 และไม่มี runnerค้างบน3000/8001 |
| Source/เอกสาร | **PASS**, links168จุด, ไม่พบ private secret ใน12ไฟล์ที่ตรวจ; protected SQL/Auth/Invitation/dependency/Auth client14ไฟล์ตรง HEADหลัง normalize EOL, whitespaceผ่านและไม่มี staging |

Focused9ครอบคลุม anonymous→Login/เข้าจากบัญชี/ไม่มีทีม, leaderไม่มีProject, memberรอแล้ว refreshพบProjectจริง, realProject/คำอธิบาย/readonly/keyboard/DesktopMobile, advisor/coordinator navigation, generic404/403/malformed/invalidID/crossTeam, Auth+business network retry, Logoutจริงแล้วหมดสิทธิ์ และเปลี่ยนบัญชีระหว่างมี Project responseเก่าค้าง

Happy pathsใช้ Browser→FastAPI→test PostgreSQLจริง Error transport/malformed/crossTeamใช้ route mocks ส่วน stale-account caseถือ responseจริงไว้ก่อนเปลี่ยนบัญชีและตรวจว่าคำขอเก่าถูกยกเลิก ไม่ใช่หลักฐาน concurrent DB lock เพิ่มเติม

Full Browserมี test-server log Windows ConnectionResetError10054หนึ่งครั้งในชุดที่มีการยกเลิก connection ทั้ง109tests/runner cleanupยังผ่าน สาเหตุเฉพาะของlogยัง Not Verified ไม่มีการแก้ Backendหรือถือเป็นผลAPIfailureจากlogนี้

Browserใช้ runnerเดิมบน `student_project_management_v1_test` ทั้ง7UOWยืม outer ROLLBACK ไม่มี fixtureถาวร/บัญชีLogin/Schema/RBACใหม่ ไม่แก้ `.env` หรือใช้ DBหลัก Seed10+29+42แถวที่อนุมัติเดิมยังเป็น baseline ไม่นำ IDs/บัญชีทดสอบชั่วคราวไปใช้สาธิตถาวร

Full Backend508/Browser100 และ HTTP concurrency79/live10 เป็นหลักฐานรอบก่อนตามรายงานของแต่ละชุด รอบนี้ไม่มี Backend sourceเปลี่ยนจึงไม่รัน Backendทั้งหมดซ้ำ ไม่อ้างว่าผลเก่าเป็นผลตรวจ sourceใหม่

## การใช้งานและงานคงค้าง

เปิดระบบด้วย configในเครื่องตาม README แล้ว Loginที่ `http://localhost:3000/login` กด **พื้นที่ทำงาน →** จากหน้าบัญชี หรือเข้า `/workspace` โดยตรงหลัง Login หากยังไม่มีทีมให้ไปเริ่มสร้างทีมตามลิงก์ ไม่มีปุ่มข้ามไปสร้าง Projectก่อนมีทีม

ก่อนเลือกงานรอบนี้ตรวจ `git ls-remote` ของ `feature/database-schema2` ได้ `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` เหมือน snapshotเดิม ยังไม่รวม/แก้งานเพื่อน งานที่ค้างในเครื่องเพื่อนยัง Not Verified; จุดเชื่อมและข้อกังวล B01–B03คงตาม [handoff](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

U03 Dashboard metrics/Timeline/Contribution, Submission/Milestone integration, UATระบบรวมและwinner-COMMITยังไม่ครบ P15/P17/P19คง In Progress และ Done6/20=30%ไม่เพิ่มจากการเพิ่มหน้านี้ ไม่มี staging/Commit/Push
