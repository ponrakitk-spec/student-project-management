# เตรียมส่งต่อก่อนขึ้น GitHub — 2026-11-15

หยุดพัฒนาฟังก์ชันตามคำสั่งเจ้าของ รายงานนี้บันทึกผลตรวจไฟล์และเตรียมเอกสารก่อนเผยแพร่ ในขั้นเตรียมไม่มี stage, Commit, Push, merge หรือคำสั่งฐานข้อมูล ผลทดสอบด้านล่างเป็นหลักฐานจากรายงานรอบก่อน ไม่ได้รันใหม่ในรอบเตรียม Git

**อนุมัติเผยแพร่ภายหลังการตรวจ:** เจ้าของสั่ง Commit/Push ชุดนี้ไป `origin/feature/project-continuation` แล้ว โดยไม่รวมงานเพื่อน ให้ตรวจ SHA ของ local HEAD เทียบ remote หลัง Push; สถานะก่อนเผยแพร่ด้านล่างเก็บไว้เป็นหลักฐาน ไม่ใช่สถานะ remote ปัจจุบัน

## Git ที่ตรวจยืนยันก่อนเผยแพร่

- Local branch: `feature/project-continuation`
- HEAD/ฐานที่เผยแพร่ครั้งก่อน: `679913a2736df9da1896ec0542742ad33ab9fae4` — `Prepare tested application baseline and team handoff`
- Remote repository: `https://github.com/ponrakitk-spec/student-project-management.git`
- `origin/feature/database-schema` ยังชี้ `679913a`; `origin/main` ชี้ `9867354`
- Branch เพื่อน `origin/feature/database-schema2` ชี้ `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` ยังไม่ได้รวมเข้าชุดนี้
- ยังไม่มี remote branch `feature/project-continuation` และงานต่อจากฐานยังเป็น working tree ที่ไม่ได้ Commit
- ปลายทางที่เสนอสำหรับชุดนี้คือ `origin/feature/project-continuation` หลังเจ้าของสั่งเผยแพร่ ไม่ทับ branch เพื่อนหรือ `main`

## สิ่งที่เพิ่มจากฐาน 679913a

ฐานเดิมมี Auth, สร้างทีม/อ่านทีม/เพิ่มสมาชิก, สร้างและอ่าน Project, คำเชิญอาจารย์ และเครื่องมือติดตั้ง V1/Auth แล้ว รายการต่อไปนี้คือส่วนเพิ่มใน working tree:

| ส่วน | พฤติกรรมที่พัฒนาเพิ่ม | หลักฐานรายละเอียด |
| --- | --- | --- |
| Team/Project | แก้ชื่อ/คำอธิบายตามสิทธิ์และช่วงงาน, โอนหัวหน้า, สมาชิกออกเอง/หัวหน้าถอดสมาชิก พร้อมยืนยันและตรวจ Task ที่จะไร้ผู้รับผิดชอบ | [Team update](../progress/TEAM_UPDATE_IMPLEMENTATION_REPORT.md), [Project update](../progress/PROJECT_UPDATE_IMPLEMENTATION_REPORT.md), [โอนหัวหน้า](../progress/TEAM_LEADER_TRANSFER_IMPLEMENTATION_REPORT.md), [ออก/ถอด](../progress/TEAM_MEMBERSHIP_EXIT_IMPLEMENTATION_REPORT.md) |
| Coordinator/กรรมการ | CLI เตรียมบัญชี Coordinator; API/UI รายการโครงงานที่ผ่านอาจารย์แล้ว เพิ่ม/เปลี่ยน/ถอดกรรมการ และล็อกหลัง Vote แรก | [รายงาน Committee](../progress/COMMITTEE_ASSIGNMENTS_IMPLEMENTATION_REPORT.md) |
| Topic votes | กรรมการลงมติ; Team/อาจารย์ที่ตอบรับ/กรรมการ/Coordinator อ่านรายชื่อและผลตามสิทธิ์ รวมหน้ารายการโครงงานของอาจารย์ | [รายงาน Topic votes](../progress/TOPIC_VOTES_IMPLEMENTATION_REPORT.md) |
| Evaluation | กรรมการให้คะแนนจำนวนเต็ม 0–100 พร้อมความคิดเห็นครั้งเดียว; เปิดผลรวม/เฉลี่ยเมื่อครบ และให้ Coordinator ดูรายบุคคลหลังครบ | [รายงาน Evaluation](../progress/EVALUATIONS_IMPLEMENTATION_REPORT.md) |
| Workspace | หน้า `/workspace` อ่านทีม/Project จริงของนักศึกษา และทางเข้างานตามบทบาท พร้อมตรวจ session/ข้อมูลเมื่อกลับมาหน้า | [รายงาน Workspace](../progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md) |
| ทดสอบหลาย transaction | เครื่องมือ/fixture/ข้อป้องกันสำหรับ Team–Project, Vote และ Evaluation ทั้ง direct PostgreSQL และ HTTP ภายใต้ขอบเขต ROLLBACK | [Team/Project](../progress/TEAM_PROJECT_CONCURRENCY_IMPLEMENTATION_REPORT.md), [Vote](../progress/TOPIC_VOTE_CONCURRENCY_REPORT.md), [Evaluation](../progress/EVALUATION_CONCURRENCY_REPORT.md), [HTTP](../progress/EVALUATION_HTTP_CONCURRENCY_REPORT.md) |
| ส่งต่อ/ทดลอง | Contracts, backlog, บันทึกจุดเชื่อมงานเพื่อน, คู่มือผู้ใช้, Demo และแผน Manual UAT 20 กรณี | [จุดเชื่อมเพื่อน](SCHEMA2_INTEGRATION_HANDOFF.md), [คู่มือ](../user/USER_GUIDE.md), [Demo](../user/DEMO_SCRIPT.md), [UAT](../uat/MANUAL_UAT.md) |

ไม่มี SQL source เปลี่ยนจาก HEAD ในชุดนี้ ไม่เปลี่ยน Schema/RBAC เพื่อทำ feature ใหม่ ไม่เพิ่มระบบลบ Project ตาม R-01

## หลักฐานทดสอบที่มีอยู่

| ชุด | ผลที่บันทึกไว้ | ขอบเขตการอ้างผล |
| --- | --- | --- |
| Full Backend | 508 PASS | [หลังติดตั้ง Evaluation fixture](../progress/EVALUATION_CONCURRENCY_REPORT.md); ก่อนเพิ่ม module safeguards Evaluation HTTP 19 tests จึงไม่อ้างว่า full suite ล่าสุดรันครบแล้ว |
| HTTP safeguards | 79 PASS | [Targeted regression](../progress/EVALUATION_HTTP_CONCURRENCY_REPORT.md) รวม 19 tests ใหม่ ไม่บวกเป็นผล full suite |
| Live Evaluation HTTP concurrency | 10/10 PASS | Login/session/CSRF/Origin, PostgreSQL wait/overlap และทั้งสอง worker ROLLBACK |
| Full Browser | 109/109 PASS | [หลังเพิ่ม Workspace](../progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md); cleanup คืนข้อมูลและ fixture connections เป็น 0 |
| ESLint/TypeScript/production build | PASS | รอบ Workspace ตามรายงานเดียวกัน |
| Manual-mode API probe | 9 คำขอ PASS | ตาม [Manual UAT](../uat/MANUAL_UAT.md); ไม่ใช่ผล UAT โดยผู้ใช้ครบ workflow |

ยังไม่ยืนยัน fresh install เครื่องใหม่, Manual UAT ทั้งแผน, ระบบรวมกับ Submission/Milestone ของเพื่อน หรือ concurrency กรณีผู้ชนะ COMMIT มี log Windows ConnectionResetError10054 ใน Browser รอบหนึ่งซึ่ง tests/cleanup ผ่าน แต่สาเหตุเฉพาะยัง Not Verified

## ตรวจชุดไฟล์สำหรับ Git รอบนี้

- หลังเพิ่มรายงานนี้และปรับ checklist: ไฟล์ tracked เปลี่ยน 26 ไฟล์ + ไฟล์ใหม่ที่ยัง untracked 115 ไฟล์ รวมเปลี่ยน 141 ไฟล์; candidate ทั้ง repository 250 ไฟล์ โดยยังไม่มี staged files
- ตรวจ candidate ตาม Git ignore: ไม่พบ `.env` จริง, `.venv`, `node_modules`, `.next`, cache, browser artifacts, DB dump/backup ที่จะติดไปด้วย
- ตรวจเทียบค่าลับ PASSWORD/SECRET/TOKEN ความยาวอย่างน้อย 8 ตัวจาก `backend/.env` กับไฟล์ข้อความ candidate: ไม่พบตรงกัน การตรวจนี้มีขอบเขตตามค่าที่รู้จัก ไม่ใช่คำรับรองว่าไม่มี secret ทุกชนิด
- `.env.example`, `.env.auth.example` ของ Backend และ `.env.example` ของ Frontend ไม่มีค่าในช่อง PASSWORD/SECRET/TOKEN
- Python AST parse ผ่าน และ `git diff --check` ผ่าน โดยไม่ import runtime หรือเชื่อม DB
- ไม่ส่งข้อมูล/บัญชี/รหัสผ่าน/hash/session ใน PostgreSQL หรือ private fixture manifests ไปกับ Git; สมาชิกแต่ละคนติดตั้ง test DB และสร้างบัญชีบนเครื่องตาม [คู่มือตั้งค่า](LOCAL_SETUP.md) และ [Database setup](DATABASE_SETUP.md)

## งานที่เหลือหลังรับชุดนี้

1. รวม Backend Submission ของเพื่อนโดยจัดการ B01–B03 ใน [บันทึก integration](SCHEMA2_INTEGRATION_HANDOFF.md) ก่อนทดสอบ DB; ยังไม่ merge หรือแก้ Supabase
2. รับ/เชื่อม Submission UI และ Milestone API/UI เมื่อเพื่อนพร้อม แล้วทดสอบ flow ส่งหัวข้อ → อาจารย์อนุมัติ → กรรมการ → Vote → งาน/Milestone → Evaluation
3. ทดสอบ fresh setup บน Windows อีกเครื่อง และ Manual UAT ตามแผนพร้อมบันทึกหลักฐานจริง
4. ข้อกำหนด Dashboard metrics/Timeline/Contribution และหัวข้อที่ยังเปิดใน [Backlog](../progress/BACKLOG.md) ต้องยืนยันขอบเขตก่อนพัฒนา

การเตรียมกับการเผยแพร่เป็นคนละขั้น รอบนี้เจ้าของอนุมัติ Commit/Push ภายหลังตรวจชุดไฟล์แล้ว ใช้ [Git release checklist](GIT_RELEASE_CHECKLIST.md) และตรวจ remote SHA หลังส่งเพื่อยืนยันผลจริง
