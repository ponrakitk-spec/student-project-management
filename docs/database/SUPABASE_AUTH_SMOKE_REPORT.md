# Supabase Auth API rollback smoke — 2026-11-18

ผู้ใช้สั่ง “ดำเนินการขั้นตอนต่อไป” ต่อจากข้อเสนอทดสอบสมัครสมาชิก/Login/Logout บน Supabase แบบ ROLLBACK ใช้ Project ทดสอบที่อนุมัติ `czylcqdmtzztabkcqewn` ผ่าน Session pooler เดิม ไม่แตะ DB ในเครื่องหรือฐานหลัก ไม่แก้ API/Schema/RBAC/private config และไม่สร้างบัญชีถาวร

## ผลจริง

**PASS 21/21 กรณี** ผ่าน FastAPI HTTP/ASGI ด้วย TestClient และ PostgreSQL Supabase จริง ใช้ physical LOGIN `project_app` ผ่าน TLS ไม่ใช่การต่อ Backend/Frontend ที่ Deploy บน Vercel หรือ Browser/proxy/TCP proof

| กลุ่ม | กรณีที่ผ่าน |
|---|---|
| ก่อน Login/validation | Me401, emailผิด422, passwordอ่อน422, spoof role422, wrong Origin403 |
| สมัครสมาชิก | 201/student/IDstring/email lowercase/name trim, ไม่autoLogin, ตรวจArgon2idด้วยรหัสสังเคราะห์, emailซ้ำ409โดยไม่มี userซ้ำ |
| Login/session | รหัสผิด401, Login200พร้อมSecure/HttpOnly/CSRF/SameSite=Lax/host-only cookies, digest32bytes/TTL8ชั่วโมง, Meคืนidentityจากsessionแม้ส่งqueryspoof |
| Loginซ้ำ | 200และยกเลิกsessionเก่า |
| Logout/CSRF | ขาดCSRF403, CSRFผิด403, rejectedlogoutยังไม่ทำลายsession, Logout204/revokeจริง, MeหลังLogout401 |
| จบ transaction | บังคับ `SET CONSTRAINTS ALL IMMEDIATE` ก่อนออกและ ROLLBACK |

## ขอบเขตความปลอดภัยและ cleanup

- Runner ใหม่ `backend/tests/supabase_auth_smoke.py` defaultเป็น **offline plan** ต้องระบุ `--run --project-ref <approved-ref>` เพื่อทำงาน ตรวจ explicit ref ตรงกับ runtime host/limited user/TLS profile ก่อนเปิด connection และเช็ก DB/roleในทุก request transaction
- Snapshotก่อน–หลังเป็น read-only connection แยก Hashแถวของ14V1tablesและ`spms_auth.sessions` พร้อมmetadata owners/ACL/function definitions ที่อ่านได้ ไม่แสดงข้อมูลจริงหรือhashes/sessiontokensในoutput
- ไม่อ่านตาราง `spms_auth.credentials` โดยตรงด้วยสิทธิ์พิเศษ ตรวจบัญชีจำลองผ่าน `lookup_credentials` ที่ระบบออกแบบไว้; หลังจบไม่พบ user/credential จำลองจาก connection ใหม่
- Auth requests ยืม connectionเดียวภายใน outer `transaction(force_rollback=True)` แต่ละ requestใช้savepoint ตรวจว่าoutertransactionยังอยู่ และบล็อก `psycopg.connect` ระหว่างส่งHTTPเพื่อกันเปิดconnectionนอกfixture
- ไม่มี owner/admin fallback, SET ROLE, DDL/GRANT, installer, seedถาวร หรือการแก้ role defaults
- ผล **baseline_restored=true / fixture_credentials_absent=true / rollback_only=true** ข้อมูลที่ตรวจกลับตรงก่อนเริ่ม ไม่มีบัญชี/credential/session จำลองค้าง
- ค่า identity sequence อาจเลื่อนแม้ ROLLBACK ไม่อ้างว่าคืน sequence values และไม่ใช้จำนวน ID gap เป็นข้อมูลค้าง

## Tests ของเครื่องมือ

`backend/tests/test_supabase_auth_smoke.py` **11 PASS แบบoffline** ตรวจ defaultไม่อ่านprivateconfig/ไม่connect, explicit target/role, localDBไม่กลายเป็นcloudwrite target, outertransactionguard, snapshotreadonly, redaction, cleanupเมื่อเกิดfailure/credentialค้าง และ SQLSTATE/function diagnostics ที่ไม่แสดงข้อความลับ

เป็น testsใหม่ของ runnerแยกจาก **Full local Backend621** รอบก่อน ซึ่งไม่ได้รันซ้ำในรอบนี้เพราะ production API ไม่เปลี่ยน ไม่บวกจำนวนเพื่ออ้างว่าเป็นFullsuiteรอบใหม่

## คำสั่งทำซ้ำ

จาก rootและprivateconfigSupabaseที่ตั้งถูกต้อง โดยไม่มีผู้อื่นเขียนข้อมูลในProjectทดสอบระหว่างตรวจ:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.supabase_auth_smoke
& .\backend\.venv\Scripts\python.exe -B -m unittest backend.tests.test_supabase_auth_smoke -q
& .\backend\.venv\Scripts\python.exe -B -m backend.tests.supabase_auth_smoke --run --project-ref czylcqdmtzztabkcqewn
```

baselineแตกต่างจากผู้ใช้คนอื่นที่เขียนพร้อมกันจะทำให้runnerFAIL ต้องตรวจสาเหตุก่อน ไม่ทำcleanupด้วยDELETE/GRANTหรือรันinstallerซ้ำเพื่อทำให้ผ่าน

## งานถัดไป

- Vercel2Projects/HTTPSBrowser/proxy/liveTCPและdeploymentprotectionยัง **Not Verified** ตาม [คู่มือ Deploy](../deployment/VERCEL_SUPABASE_SETUP.md)
- Cloud Team→Project→Submission→Milestone/Task→Vote/Evaluation ยัง **Not Run** ไม่ขยายผล Auth21 เป็นทุกworkflowหรือconcurrency
- บัญชีทดสอบถาวรของstudent/advisor/coordinatorยังไม่ถูกสร้างจากsuiteนี้ ต้องกำหนดขอบเขตก่อนเตรียมข้อมูลกลาง
- ยังไม่Commit/Pushในรอบทดสอบ; code/configของ18พ.ย.ยังไม่อยู่ในremote8167187 ไม่อ้างว่าพร้อมDeployจากGitHubรุ่นเก่า
