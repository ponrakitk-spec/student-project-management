# Supabase limited-role connection — 2026-11-18

**ผลขั้นถัดมา:** [Auth HTTP/ASGI rollback smoke21/21ผ่านจริง](SUPABASE_AUTH_SMOKE_REPORT.md) พร้อมbaselineคืนและไม่พบบัญชีจำลองค้าง ข้อความAuthNotRunด้านล่างเป็นsnapshotก่อนรอบAuth ไม่ใช่ผลปัจจุบัน ยังไม่ใช่Browser/Vercel/ทุกbusinessworkflow

ผู้ใช้สร้าง Project ทดสอบ `czylcqdmtzztabkcqewn` และอนุมัติติดตั้ง baseline ผ่าน SQL Editor เอง ส่งภาพ bootstrap PASS แล้วตั้ง password ของ `project_app` และ runtime config บนเครื่องเอง ไม่มีการเปิดเผย credentials ในรายงานนี้

## ปลายทางและสิ่งที่ตรวจจริง

- Session pooler: `aws-1-ap-northeast-1.pooler.supabase.com:5432` ผูกกับ Project ref ที่อนุมัติ ไม่เดา host จาก region
- Database `postgres`, `session_user=current_user=project_app`, PostgreSQL **17.12**, client TLS ใช้งานจริง
- Runtime guard ตรวจ role ไม่เป็น superuser/ไม่มีสิทธิ์ elevated ที่ห้ามไว้ ไม่เป็นสมาชิก owner/read-all/write-all และไม่สลับจาก admin เพื่อผ่าน guard
- `database.tools.Supabase_Preflight` หลังแก้ด้านล่างได้ **PASS_PRELIMINARY_READONLY** ตรวจ14tables/86columns/28FKs/52functions/24triggers/2Auth tables, table/function ownership และ selected effective ACL/ไม่เปิด app objects ให้ API roles ตามขอบเขตที่ script ตรวจ

## ปัญหาที่พบและการแก้ตามอนุมัติ

ก่อนแก้ startup `options` ของ connection ไม่ได้มีผลตามที่ตั้งไว้บน endpoint นี้: default/transaction read-only=`off`, statement_timeout=`2min`, lock_timeout=`0` สคริปต์จึงหยุดที่ guard แบบถูกต้อง ไม่ใช่รหัสผ่านผิดหรือ permission denied และไม่มี SQLSTATE จาก guard `StorageUnavailable`

เมื่อสั่ง `SET TRANSACTION READ ONLY` ชั่วคราวโดยตรง การตรวจผ่าน จึงรายงานและขออนุมัติแก้เฉพาะการเริ่ม transaction ผู้ใช้เลือก “แก้ตามแนวทางนี้และทดสอบต่อ” แล้ว:

1. `backend/auth_store.py`: สำหรับ readonly opener ตั้ง `conn.read_only=True` เพื่อให้ Psycopg เริ่ม transaction ด้วย READ ONLY ไม่พึ่ง startup parameter เพียงอย่างเดียว; ถ้าตั้งค่าเริ่มต้นล้มเหลวให้ปิด connection และซ่อน driver error
2. หลังยืนยัน cloud DB/role/physical LOGIN แล้ว ตั้ง `SET LOCAL statement_timeout='15s'` และ `lock_timeout='3s'` ก่อน business queries ส่วน local guard คงพฤติกรรมเดิมเพื่อไม่เขียนทับ timeout เฉพาะของ fixture/concurrency tests
3. ไม่แก้ Schema, Functions, Triggers, RBAC, `.env` หรือเพิ่มสิทธิ์ ไม่ใช้ admin fallback ไม่แก้ Login/API Contract

อ้างอิง [Psycopg transaction characteristics](https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.read_only), [PostgreSQL SET TRANSACTION](https://www.postgresql.org/docs/17/sql-set-transaction.html)

## ผลทดสอบ

| ชุด | ผล |
|---|---|
| Offline config/Auth security/preflight safeguards | **46 PASS** รวม new timeout/readonly initialization/connection cleanup/invalid-identity/local-mode preservation tests |
| Supabase Preflight CLI จริงหลังแก้ | **PASS_PRELIMINARY_READONLY** ไม่มี temporary SQL patch หรือ role switch |
| Cloud transaction factories ทั้ง10 | **10/10 PASS_READONLY_SETTINGS**: Auth, Team, Project, Invitation, Committee, Vote, Evaluation, Submission, Milestone, Task; ทุกกรณีตรวจ identity/read-only/15s/3s ผ่านแล้ว ROLLBACK |
| Full local regression หลังแก้ | **621 PASS / 42 modules**, 110.321s; local test DB เท่านั้นและ ROLLBACK คืน public values/metadata/owners/ACL/Auth counts (ไม่รวม sequence) เลือก local profile เฉพาะ subprocess ไม่แก้ `.env` ที่ผู้ใช้ตั้ง cloud ไว้ |

Cloud checks นี้ใช้แค่ read-only metadata/identity/settings ไม่เรียก business write functions ไม่สร้างบัญชี/fixture/app data ไม่ COMMIT ไม่เปลี่ยน role defaults ถาวร SQLตั้งค่าtransactionไม่ใช่การผ่อน guard และไม่อ้างว่าผลเฉพาะcounts/selectedACLเท่ากับ full V1 definition parity หรือ workflow/concurrency proof

## ขั้นที่ยังเหลือ

- Auth/Team/Project/Submission/Milestone/Task/Evaluation write workflow บน Supabase แบบ ROLLBACK ยัง **Not Run** การตรวจ factory10/10ตรวจขอบเขตเริ่ม transaction ไม่ใช่การทำCRUDครบ10features
- ยังไม่มี Vercel production domains/config ที่ตรวจรับจริง หรือ HTTPS Browser/proxy test ผ่าน cloud
- Cloud user accounts/ข้อมูลในเครื่องไม่ได้ตามมาพร้อม schema หรือ Git ต้องตกลงขอบเขต seed/การเขียนถาวรก่อนใช้ร่วมกัน
- ชุด local installers/Browser rollback preview/concurrency manifests ยังคง local-only ห้ามเปลี่ยนปลายทางเพื่อใช้กับ cloud
- ไม่ Commit/Push ในรอบนี้; คู่มือ [Vercel/Supabase](../deployment/VERCEL_SUPABASE_SETUP.md)
