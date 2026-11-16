# ตรวจขอบเขตรวมงาน — 2026-11-16

**ผลต่อจากการตรวจ:** เจ้าของยืนยัน “ดำเนินการได้เลย” ตามข้อเสนอแล้ว รับ Backend Submission และแก้จุดเชื่อมบน `feature/team-integration` โดยคง DB/role เดิมและพัก Supabase ดู [รายงานผลและหลักฐานปัจจุบัน](../progress/SUBMISSION_INTEGRATION_REPORT.md) เนื้อหาตรวจด้านล่างเก็บสถานะก่อนอนุมัติ ไม่ใช่รายการที่ยังรออนุมัติในปัจจุบัน

เจ้าของสั่งสร้าง branch ใหม่เพื่อรวมงานของเราและเพื่อน ตรวจ remote ด้วย `git fetch origin` แล้วสร้าง local `feature/team-integration` จาก `origin/feature/project-continuation` โดยยังไม่ตั้ง upstream เพื่อป้องกันการส่งไป branch ต้นทางผิดตัว ไม่มี Commit/Push หรือคำสั่งฐานข้อมูลในรอบตรวจนี้

## แหล่งงานที่ pin ไว้

| แหล่ง | Commit | สิ่งที่ตรวจพบ |
| --- | --- | --- |
| งานของเรา | `6040702d75044645bdb67c3894be2553ee7e1351` | Auth/Team/Project/Invitations/Committee/Vote/Evaluation/Workspace และ tests/docs |
| งานเพื่อน `origin/feature/database-schema2` | `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` | Submission Backend, tests, Contract และการเตรียม Supabase |
| Merge base | `986735411dc0de328cb7cf9a354033f025127a35` | main รุ่นแรก จึงมีไฟล์ add/add หลายรายการ ห้ามใช้ branch เพื่อนทับชุดของเรา |

Remote เพื่อนยังเป็น snapshot เดิม ไม่พบ Submission UI หรือ Milestone API/UI ใน tree นี้ งานที่ยังอยู่เฉพาะเครื่องเพื่อน Not Verified ดูประวัติใน [SCHEMA2_INTEGRATION_HANDOFF.md](SCHEMA2_INTEGRATION_HANDOFF.md)

## ขอบเขตที่รวมได้หลังยืนยันจุดขัดแย้ง

- รับ `backend/submission_api.py`, `submission_store.py`, `submission_validation.py`, tests Submission 3 ไฟล์ และ `docs/api/SUBMISSIONS_CONTRACT.md` จาก snapshot เพื่อน พร้อมบันทึกที่มา
- ผสาน `backend/main.py` เฉพาะ Submission router, validation/storage handlers, no-store และ body-limit middleware โดยรักษา routes/CORS PATCH/handlers ของเรา
- ผสาน `backend/tests/auth_browser_server.py` เพิ่ม Submission UOW ลงใน borrowed outer transaction เดิม รักษา 7 UOW overrides และ fixture/cleanup ของเรา
- ผสาน `backend/requirements.txt` เฉพาะ dependency ของ Submission; ตรวจ compatibility และติดตั้งเมื่อยืนยันขอบเขตแล้ว ไม่เขียนทับ dependencies เดิม
- ปรับ `test_auth_security.py` ให้ตรวจ OpenAPI ครบทั้งระบบ และแก้ Submission integration fixture ก่อนรันทดสอบ DB
- ยังไม่สร้าง UI หรือ Milestone ใหม่ เพราะไม่มี source ใน snapshot และไม่ทราบงานที่เพื่อนยังไม่ Push

Contract เพื่อนมี 7 operations: ประวัติ/eligibility/ส่งไฟล์ของทีม, inbox อาจารย์, รายละเอียด/ดาวน์โหลด Submission และอาจารย์ตรวจผล ใช้ PDF/PPTX 1–4,000,000 bytes, atomic Submission+file, immutable snapshot/history, session/Origin/CSRF เดิม เอกสารเพื่อนระบุ confirmed แต่หลักฐานอนุมัติ API/วิธีตรวจไฟล์นอก thread นี้ยังไม่ยืนยันโดยเจ้าของในรอบรวมงาน

## จุดที่ต้องหยุดและขอข้อสรุป

### Connection policy / Supabase

`backend/auth_store.py` ฝั่งเพื่อนรองรับ `AUTH_DATABASE_URL`, `AUTH_DB_NAME`, `AUTH_DB_USER`, owner/schema ที่เปลี่ยนได้ จึงเปิดทางเชื่อม DB/role อื่น ซึ่งขัดกับข้อกำหนดเดิมที่จำกัด test DB และ `project_app` ต้องให้เจ้าของตัดสินใจก่อนรับส่วนนั้น

ข้อเสนอ: คง `auth_store.py` ของเราและใช้ `student_project_management_v1_test`/`project_app` เท่านั้น รวม Backend Submission ผ่าน connection เดิม ส่วน Supabase ให้พักไว้ใน branch เพื่อนโดยยังไม่รัน script หรือย้าย runtime ไม่เปลี่ยน Schema/RBAC

### Test fixture / rollback

`test_submission_api.py` ยัง override เฉพาะ Auth/Team/Submission ขณะที่ setup เรียก Project และ Invitation ผ่าน HTTP ต้องเพิ่ม UOW overrides ให้ครบก่อนรัน เพื่อไม่ให้เปิด connection คนละ transaction หรือ COMMIT นอก fixture ใช้ baseline+delta แทนการสมมติว่าตาราง submissions ว่าง

Submission transaction ต้องรักษา statement/lock timeouts และตรวจ effective role ตามระบบเดิม ตรวจ G-12 และสิทธิ์ดาวน์โหลดจาก V1 ก่อนถือว่า Contract ผสานได้ ไม่ข้ามสิทธิ์ด้วย owner/superuser

## สิ่งที่ไม่รับทับจาก snapshot

- `__pycache__/*.pyc` 17 ไฟล์เป็น generated artifacts ไม่รวมในชุดใหม่
- Team/Project/Auth และ Frontend shared files รุ่นเก่าของเพื่อน ไม่ใช้ทับ feature ของเรา
- SQL Schema V1/Auth/migration ที่เปรียบเทียบร่วมกันไม่มีเนื้อหาต่างหลัง normalize EOL จึงไม่ต้องเปลี่ยน SQL
- `test_auth_store_config.py` ผูกกับ configurable DB/Supabase จึงไม่รับหากเลือกคงนโยบาย DB เดิม
- ไม่รัน Supabase bootstrap/roles scripts หรือใช้ DB อื่นโดยอาศัยเพียงคำสั่งรวม branch

## สถานะและขั้นถัดไป

สร้าง integration branch และตรวจ source แล้ว ยังไม่ได้ merge/copy Submission runtime, ติดตั้ง dependencies, รัน tests หรือเชื่อม DB จึงไม่มีผล PASS ของระบบรวม

รอเจ้าของยืนยันข้อเสนอ: รวม Backend Submission ทั้ง 7 operations ตาม Contract เพื่อน พร้อมแก้จุดเชื่อมและ rollback fixture โดยคง test DB/role เดิม และพัก Supabase ไว้ก่อน หลังยืนยันจึงผสาน source → offline tests → test DB rollback integration → regression และบันทึกผลจริง ไม่ Commit/Push branch ใหม่นี้จนกว่าจะได้รับคำสั่ง
