# Supabase สำหรับฐานข้อมูลกลางของทีม

ขอบเขตยืนยัน 2026-11-16: Next.js → FastAPI → Supabase PostgreSQL, **คงระบบ Login เดิม** รวมทั้ง session 8 ชั่วโมง/CSRF/บทบาท V1; เก็บไฟล์ใน `project_submission_files.file_data` ตาม V1 เดิม ไม่เพิ่ม Storage/Auth ของ Supabase

สถานะ: **เตรียมโค้ดและ SQL draft เท่านั้น ยังไม่มี Project ปลายทางที่ตรวจยืนยัน และยังไม่เชื่อม Supabase จริง** การติดตั้งจริง/การทดสอบเขียน/การนำเข้าข้อมูลต้องแยกขอบเขตให้ชัด ไม่ถือว่าเปลี่ยน config แล้วข้อมูลหรือบัญชีจากเครื่องจะตามไปเอง

## 1. เลือก Project ทดสอบ

ตรวจ Dashboard กับเพื่อนก่อนว่ามี Project สำหรับทีมแล้วหรือไม่ โค้ดใน Git ยืนยันได้เพียงว่ามีสคริปต์ ไม่ยืนยันทรัพยากรในบัญชีของเพื่อน

ถ้ายังไม่มี ให้เจ้าของบัญชีสร้าง Project ทดสอบใหม่ใน [Supabase Dashboard](https://supabase.com/dashboard) เช่นชื่อ `spms-team-test` เลือก region ที่เหมาะกับทีม ตั้ง DB password แบบส่วนตัว และตรวจแผน/ค่าใช้จ่ายก่อนกดยืนยัน ไม่ต้องส่ง password หรือ API key ในแชท แจ้งได้เฉพาะชื่อ Project และ Project URL/ref ที่ไม่ใช่ความลับ

ใช้ Project แยกสำหรับทดสอบ ห้ามนำขั้นตอนนี้ไปใช้กับ `student_project_management` หรือฐานที่มีข้อมูลสำคัญ

## 2. ตรวจและติดตั้ง baseline — ยังไม่ดำเนินการ

ก่อนลงจริงต้องตรวจปลายทาง/ข้อกำหนด PostgreSQL และอนุมัติชุด [SQL draft](../../database/supabase/README.md) ที่จะสร้าง Roles/Schema/สิทธิ์ถาวร

- ใช้ฐาน `postgres` ของ Supabase Project ทดสอบที่ระบุเท่านั้น ต่างจาก local `student_project_management_v1_test`
- `project_owner`: non-login/non-superuser เจ้าของ objects; `project_app`: limited LOGIN ของ FastAPI
- ไม่เปลี่ยน V1 14 ตาราง/86 columns/28 FKs กฎและ functions คงเดิม Auth 2 ตารางของเราใช้ `spms_auth` เพื่อไม่ชน `auth` ของ Supabase
- ปิด **Data API** ก่อนติดตั้ง เพราะเรากรองสิทธิ์การอ่านผ่าน FastAPI ไม่เปิด frontend ข้าม Backend ไปอ่านตาราง/RPC
- ต้องตั้ง password ของ `project_app` ส่วนตัวหลังสร้าง role และพิสูจน์ด้วยการ Login จริง หาก Dashboard ไม่มีช่องตั้ง role password ใช้ psql `\password project_app` แบบ interactive ภายใต้ผู้ติดตั้งที่ได้รับอนุญาต ห้ามบันทึก ALTER ROLE พร้อม password ลงไฟล์/Git/แชท
- `000_roles.sql` กับ `001_bootstrap.sql` เป็นคนละ transaction ถ้าขั้น schema ล้มเหลว Roles จากขั้นแรกอาจยังอยู่ ห้ามรันซ้ำทั้งชุดหรือ DROP เพื่อแก้เอง ต้องตรวจสภาพก่อน

## 3. Runtime config หลัง baseline พร้อม

ค่าจริงอยู่ใน ignored `backend/.env` หรือ environment ของ Backend เท่านั้น ใช้ [template](../../backend/.env.supabase.example) เป็นรายการอ้างอิง **ห้ามคัดลอกทับ `.env` เดิม** และยังไม่ต้องสลับระหว่างที่เว็บทดลองเดิมเปิดอยู่

| ค่า | ความหมาย |
|---|---|
| `AUTH_DB_TARGET=supabase_test` | เปิดโหมดใหม่อย่างชัดเจน; ถ้าไม่ระบุยังใช้ `local_test` |
| `SUPABASE_PROJECT_REF` | ref 20 ตัวของ Project ทดสอบที่อนุมัติ ใช้ผูก host/username ให้ตรงเป้าหมาย |
| `AUTH_DATABASE_URL` | PostgreSQL URL ของ limited role พร้อม TLS ไม่ใช่ HTTPS Project URL หรือ API key |

จาก **Connect** เลือก Direct หากเครือข่ายรองรับ หรือ **Session pooler** สำหรับ IPv4:

- Direct: host `db.<project-ref>.supabase.co`, user `project_app`, port `5432`, database `postgres`
- Session pooler: คัดลอก host จริงจาก Connect, user `project_app.<project-ref>`, port `5432`, database `postgres`
- password ใน URL ต้อง percent-encode; ใช้ `sslmode=require` หรือ `sslmode=verify-full` พร้อม certificate ของ server ที่เชื่อถือได้
- โหมดนี้ยังไม่รองรับ Transaction pooler `6543`, custom domains, admin logins หรือ query options อื่นนอกจาก SSL ไม่ผ่อน guard เพื่อให้ต่อได้
- ไม่ใช้ `DB_USER/DB_PASSWORD` หรือ `postgres` เป็น fallback ใน business request

เอกสารทางการ: [Connection modes/TLS](https://supabase.com/docs/guides/database/connecting-to-postgres), [Data API security](https://supabase.com/docs/guides/api/securing-your-api), [Supabase auth schema](https://supabase.com/docs/guides/auth/managing-user-data)

## 4. ตรวจแบบอ่านอย่างเดียว

หลังระบุ config และติดตั้ง baseline ตามที่อนุมัติแล้ว จาก root:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Supabase_Preflight
```

คำสั่งนี้ใช้ `project_app` พร้อม server-side read-only, เช็กชื่อ DB/role/structural counts/selected ACL/การไม่เปิดสิทธิ์ให้ API roles แล้ว ROLLBACK ไม่สร้าง Roles/ข้อมูล ไม่แสดง URL/password และไม่ fallback ไป local เมื่อ config ผิด

`PASS_PRELIMINARY_READONLY` ยังไม่รับรอง Schema parity ทุกจุด, API writes, managed-platform compatibility หรือ workflow/concurrency ต้องทดสอบแยกหลังมี Project จริง หาก FAIL ให้หยุดตรวจสาเหตุ ไม่แก้ grants เอง

## 5. การทดสอบและข้อมูลร่วมกัน — รอ Project จริง

- การทดสอบในเครื่องเดิมยังใช้ local test DB และ ROLLBACK ตาม [LOCAL_SETUP](LOCAL_SETUP.md) ห้ามชี้ชุด local installers/fixtures/concurrency manifests ไป Supabase
- ยังไม่รัน local Browser fixture runner กับ Supabase; snapshot/cleanup และ staff provisioning ของเครื่องมือเดิมยังจำกัด local test DB
- ต้องเตรียมชุดทดสอบ cloud แยกที่ตรวจ ref/host/database/role ก่อนทุกชุดและ ROLLBACK รวมการทดสอบบัญชีและสิทธิ์แต่ละบทบาท
- บัญชี student/advisor/coordinator และ Project ในเครื่องไม่ได้ถูกย้ายขึ้น Supabase อัตโนมัติ ต้องตกลงว่าจะสร้างบัญชีทดสอบใหม่หรือนำเข้าข้อมูลใดก่อน ห้ามนำ test seeds/รหัสผ่านจริงขึ้นไปโดยปริยาย
- ถ้าอนุมัติใช้ข้อมูลกลางถาวรแล้ว สมาชิกทีมใช้ Backend ของตนที่เชื่อม Project เดียวกันได้ตามสิทธิ์ จึงต้องระวังการแก้ข้อมูลร่วมกัน การใช้ Supabase ไม่ได้เผยแพร่ FastAPI/Next.js ให้เป็นเว็บออนไลน์เอง

กลับโหมด local: คืนค่า config เดิมและ `AUTH_DB_TARGET=local_test`, เอา `AUTH_DATABASE_URL` ออกจาก process/.env ที่ใช้ พร้อม local AUTH_DB_HOST/PORT/PASSWORD การสลับไม่คัดลอกหรือลบข้อมูลฝั่งใด หากมีเว็บ ROLLBACK เปิดอยู่ให้จบรอบอย่างชัดเจนก่อน restart
