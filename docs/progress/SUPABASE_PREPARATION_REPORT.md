# Supabase PostgreSQL preparation — 2026-11-16

ผู้ใช้เลือกแบบ 1: ฐานข้อมูลกลางของทีม คงระบบ Login เดิม และระบุให้สร้าง Project ทดสอบใหม่หากเพื่อนไม่มี Project เดิม การตรวจ Git เพื่อนพบ SQL/คู่มือเตรียมไว้ แต่ไม่มีหลักฐาน live deployment จึงยังไม่สรุปว่ามีหรือไม่มี Project ในบัญชีของเพื่อน

## ส่วนที่เตรียม

- `backend/db_target.py`: โหมด explicit `supabase_test` + Project ref/host/database/limited-role/TLS allowlist; default local test ไม่เปลี่ยน ไม่มี admin fallback รองรับ Direct/Session pooler 5432
- `backend/auth_store.py`: ใช้ target ที่ผ่าน validation และ namespace คงที่ `auth` สำหรับ local หรือ `spms_auth` สำหรับ Supabase; ไม่เปลี่ยน hashing/session/API contract/สิทธิ์ผู้ใช้
- `backend/.env.supabase.example`: template ว่าง ไม่อ่านหรือคัดลอก secrets ไปเอกสาร ไม่แก้ `.env` จริง
- `database/supabase/`: deployment draft จาก peer `31c4fcb` ตรวจเทียบ canonical source โดยไม่แก้ Schema V1 เพิ่ม atomic roles/installer SET ROLE, ถอน CREATE หลังติดตั้ง และ abort หาก API roles เข้าถึง objects ของแอป ไม่ใช้ password ที่ถูก mask ใน pg_roles เป็นหลักฐาน Login
- `database/tools/Supabase_Preflight.py`: runtime-role read-only structural/selected ACL guard ไม่มี install/seed/COMMIT mode; ไม่รับรอง full parity หรือ workflow
- Tests/config/setup guide พร้อมบันทึกสถานะใน Backlog/README
- `backend/tests/auth_browser_server.py`: ป้องกันไม่ให้ local rollback preview ใช้โหมด Supabase ก่อนเปิด connection ตรวจช่วงท้ายพบพอร์ต3000/8001ไม่มี listener จึงเปิด local ROLLBACK preview รุ่นปัจจุบันตามคำขอเดิม ไม่ปิด server ของผู้ใช้ ไม่ seed staff/phase ใหม่

## หลักฐาน

| รายการ | ผล |
|---|---|
| Offline config/Auth security/SQL source/read-only safeguards | 41 PASS; synthetic URLs ไม่เปิด cloud connection |
| V1 source parity ของ draft | DDL ทั้งส่วนและ RBAC ตรง canonical เมื่อตัด deployment wrapper/comments และแทน psql role variables ด้วยชื่อที่ยืนยันแล้ว; รวม 14 CREATE TABLE และ 52 function definitions |
| Auth source parity ของ draft | 2 tables/2 functions ตรง canonical หลังเปลี่ยน namespace auth → spms_auth |
| Full local regression หลังเพิ่ม config | **603 PASS**, 80.072s / 40 modules; local test DB เท่านั้น ค่า public rows/metadata/owners/ACL/Auth counts คืน baseline หลัง ROLLBACK (ไม่รวมค่า sequence) |
| Direct LOGIN project_app local smoke | PASS: Auth/Team/Project/Milestone/Task/assign/history และ negative guards; session_user=current_user=project_app, metadata/ACL/counts คืน baseline หลัง ROLLBACK |
| Source/private config checks | Python AST/relative doc links/whitespace ผ่าน ไม่พบค่าลับจาก `.env` ที่นำมาเทียบในไฟล์ใหม่หรือไฟล์ runtime ที่แก้ canonical SQL ไม่เปลี่ยน ไม่มี staging |
| Supabase Project/ref/SQL installation/live connection | **Not Verified / Not Run** ไม่มีปลายทางหรือสิทธิ์เข้าถึงบัญชี Supabase ที่ยืนยันแล้ว |
| Supabase API workflow/rollback/concurrency | **Not Run** ผล local ไม่ใช่ผล cloud |

ไม่ได้สร้าง Project ผ่านบัญชีผู้ใช้ ไม่รัน SQL/Role/Grant กับ Supabase ไม่คัดลอก local data/บัญชี/fixtures ไม่เปลี่ยน DB หลัก ไม่ Commit/Push ไม่เปลี่ยน Frontend/Storage/Supabase Auth เว็บทดลองที่เปิดให้ยังใช้ local test DB/ROLLBACK ไม่ใช่ Supabase

## สิ่งที่ต้องมีเพื่อทำต่อ

1. ผู้ใช้แจ้งว่ามี Project แล้ว แต่ยังไม่ได้ระบุชื่อ/ref/URL หรือว่ามี application objects/data เดิมหรือไม่ ต้องยืนยันข้อมูลเหล่านี้ก่อน ไม่สร้าง Project ซ้ำโดยอัตโนมัติ
2. ตรวจเวอร์ชัน PostgreSQL/managed roles, Data API exposure และตรวจ SQL installation effects บนปลายทางนั้นก่อนติดตั้งถาวร
3. ตั้งค่า restricted credentials บนเครื่องเอง ตรวจ read-only และเตรียม cloud rollback test suite แยก ไม่ผ่อน local-test guards หรือใช้ local installers กับ cloud
4. ตกลงการเตรียมบัญชีทดสอบ/ข้อมูลกลางและ COMMIT runtime ก่อนเปิดใช้ร่วมกัน

คำแนะนำ/ขั้นตอน: [Supabase Setup](../team/SUPABASE_SETUP.md) โหมด Supabase ไม่ได้ Deploy Backend/Frontend อัตโนมัติ และไม่รับรองว่าบัญชีหรือ Project ในเครื่องจะตามไป
