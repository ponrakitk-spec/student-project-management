# Supabase PostgreSQL — deployment draft

ผู้ใช้เลือกใช้ Supabase เป็นฐานข้อมูลกลาง **คง Login/Session เดิม** วันที่ 2026-11-16 ไม่ใช้ Supabase Auth, Storage, Data API หรือ frontend SDK

สถานะ: เตรียม source/การเชื่อมต่อแล้ว **ยังไม่ติดตั้งหรือทดสอบบน Supabase จริง** ไม่มีการคัดลอกข้อมูลจาก DB ในเครื่อง ต้องระบุ Project ทดสอบที่ได้รับอนุญาตก่อน

## ที่มาของ SQL

รับเฉพาะ deployment draft จาก peer commit `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` ไม่ merge หรือเขียนทับ business source ของเพื่อน:

- `000_roles.sql`: เตรียม owner/app สอง roles ใน transaction เดียว และให้ผู้ติดตั้ง `postgres` ใช้ `SET ROLE project_owner` ได้บน PostgreSQL >=16; ไม่มี password ในไฟล์
- `001_bootstrap.sql`: ติดตั้ง V1 14 ตาราง/86 columns/28 FKs/52 functions/24 triggers และ Auth 2 ตารางใน `spms_auth` เฉพาะฐาน `postgres` ของ Project ทดสอบใหม่ที่ไม่มี objects ของแอป ใช้ transaction เดียว และหยุดเมื่อพบ objects เดิม
- ไม่แก้ไฟล์ canonical ใน `database/schema` และ `database/auth` V1 function/table definitions เทียบต้นฉบับแบบข้อความ; Auth เปลี่ยนเฉพาะ namespace `auth` → `spms_auth`
- แก้จาก peer: ไม่อ้าง `pg_roles.rolpassword` ที่ถูกปกปิดเพื่อรับรองว่ามี password; ต้องพิสูจน์ด้วย direct LOGIN app ภายหลัง, ถอน CREATE ที่ใช้ติดตั้งของ owner และ abort หาก Supabase API roles มีสิทธิ์เข้าถึง application objects

การรันไฟล์เหล่านี้ **สร้าง Roles/Schema/สิทธิ์ถาวร** แม้ยังไม่มีข้อมูลผู้ใช้ จึงเป็นขั้นแยกจากการตรวจ source และ rollback-only tests ปัจจุบัน ยังไม่อนุมัติปลายทางใดจากการมีไฟล์นี้

## ข้อจำกัดก่อนติดตั้ง

1. ตรวจ Project/ref ว่าเป็น Project ทดสอบที่ถูกต้อง ไม่มี application data เดิม ปิด Data API เพราะ V1 กรองแถวด้วย FastAPI ไม่ใช่ Supabase RLS ห้ามแก้ `auth` ของ Supabase
2. ตรวจ PostgreSQL version/managed role capabilities จริง จำนวน objects ตรงไม่ใช่หลักฐาน runtime compatibility โดยเฉพาะ Triggers/Deferred Constraints/lock ordering
3. ตรวจ SQL ทั้งสองไฟล์และผลกระทบกับเจ้าของก่อนรัน ไม่ใช้ local installers หรือ regression suites กับ Supabase
4. หากติด permission denied ให้เก็บ SQLSTATE และชื่อ function โดยปกปิดข้อมูลลับ ห้ามเพิ่มสิทธิ์ project_app หรือเปลี่ยนไปใช้ admin ใน request

ดู [คู่มือตั้งค่า](../../docs/team/SUPABASE_SETUP.md) และ [รายงานการเตรียม](../../docs/progress/SUPABASE_PREPARATION_REPORT.md)
