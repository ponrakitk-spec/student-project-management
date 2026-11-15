# Project update — ผลพัฒนาและทดสอบ

วันที่ 2026-11-14 (Asia/Bangkok) · P09/P15/P16/P17/P19 · Branch `feature/project-continuation` · ฐาน `679913a` + Working tree ยังไม่ Commit/Push

ผู้ใช้ยืนยัน [Project Update Contract](../api/PROJECT_UPDATE_CONTRACT.md) ด้วยคำตอบ “เริ่ม Project update ตามร่าง” และยืนยันเพื่อนรับผิดชอบ Submission + Milestone รวม Supabase สำหรับอนาคต งานนี้จึงเพิ่มเฉพาะ Project metadata update บนฐานเจ้าของ ไม่ merge/แก้ runtime เพื่อน ดู [บันทึกรับช่วง](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

## พฤติกรรมที่พัฒนาแล้ว

- `PATCH /api/v1/projects/me` ใช้ active session/Origin/session-bound CSRF เดิม ผู้ใช้ต้องเป็น student และหัวหน้าทีมปัจจุบัน
- รับ name และ/หรือ description อย่างน้อยหนึ่ง field; field ที่ไม่ส่งคงค่าเดิม, description null/ASCII blank ล้างเป็น NULL, name null/blank/เกิน255/ข้อความ DB ไม่รองรับหรือ fields อื่นตอบ sanitized422
- เลือก Project จากสมาชิกภาพฝั่ง server ไม่รับ client actor/project/team/status; IDs และ created_by/team_id คงตาม DTO เดิม
- ตั้ง transaction-local actor, ล็อก Team → Project, ตรวจสมาชิกภาพ/หัวหน้าใหม่หลัง Team lock แล้วอ่านค่าเดิม/SQL phase predicate ภายใต้ Project lock ก่อนผสาน partial fields
- เขียนผ่าน `public.v1_update_project_metadata` เดิมโดย project_app ไม่ใช้ direct UPDATE/owner fallback ไม่แก้ Schema/grants; phase ที่ล็อกตอบ409PROJECT_METADATA_LOCKED รวม no-op requests
- ก่อนส่งครั้งแรกแก้ได้; pending/approved ที่ยังไม่มีผลกรรมการขอแก้ไขแก้ไม่ได้; advisor ขอแก้หรือกรรมการลงครบและขอแก้จึงแก้ได้; หลังผลอนุมัติสุดท้ายล็อกตาม SQL เดิม
- ความเปลี่ยนแปลงอยู่ที่ Project เท่านั้น snapshot Submission เดิมไม่เปลี่ยน; R-01 ห้ามลบ Project ยังคงเดิม
- หน้า `/projects` เพิ่มฟอร์มแก้ไขให้ leader พร้อมบันทึก/ยกเลิก ใช้รูปแบบเดิม ไม่สร้าง route/Auth ใหม่ ไม่เปิด form ให้ member
- UI ส่งเฉพาะค่าที่เปลี่ยน; no-op ส่งชื่อเดิมให้ server ตรวจสิทธิ์/phase อีกครั้ง การบันทึกล้มเหลวไม่ทำ automatic PATCH retry กรณีผลไม่แน่นอนปิดปุ่มบันทึกและให้ GET ตรวจข้อมูลก่อน
- เพิ่ม PATCH ใน CORS ของแอป ไม่เพิ่ม PUT/DELETE ไม่แก้ TTL หรือ connection policy

## ไฟล์ที่เปลี่ยนสำหรับ feature นี้

| ไฟล์ | เหตุผล |
|---|---|
| `backend/project_api.py` | Partial request validation, PATCH, error mapping |
| `backend/project_store.py` | Locks/authorization/phase/controlled SQL update/อ่านผลหลังแก้ |
| `backend/main.py` | CORS methods เพิ่ม PATCH เท่านั้น |
| `backend/tests/test_project_api.py` | Project suite21→32 tests; ยืนยัน GET/PATCH และห้าม PUT/DELETE แทนเกณฑ์เดิมที่ยังไม่มี update |
| `backend/tests/test_auth_security.py` | ยืนยัน approved methods ใน OpenAPI โดยไม่ต่อ DB |
| `backend/tests/team_api_direct_smoke.py` | Direct app partial update ชื่อ/description และ role/baseline proof |
| `frontend/src/features/projects/api.ts` | PATCH client/error messages |
| `frontend/src/features/projects/project-edit-form.tsx` | Form/validation/pending/cancel/reconciliation/error handling |
| `frontend/src/features/projects/project-screen.tsx` | Leader-only editing, creator/team/id response checks และข้อความผลสำเร็จ |
| `frontend/src/features/projects/projects.module.css` | Edit panel/actions ใช้ style เดิมและรองรับมือถือ |
| `frontend/tests/projects.spec.ts` | Project Browser9→16 tests และปรับเกณฑ์เดิมให้อนุญาต edit ที่ยืนยันแล้ว |
| Contract/report/backlog/team handoff | บันทึกการอนุมัติ ผลใหม่ และจุดรวมงานเพื่อน |

ไม่มีการแก้ SQL/RBAC/Requirements/.env/connection module/dependencies หรือ Submission/Milestone/Supabase source ของเพื่อน เอกสาร progress/scope จากรอบตรวจ branch ก่อนหน้ายังอยู่ใน Working tree เดียวกัน แต่แยกหลักฐานและขอบเขตไว้แล้ว

## ผลทดสอบใหม่บนเครื่องนี้

| ชุด | ผล | ขอบเขต |
|---|---|---|
| `python -B -m database.tools.V1_Baseline_Prepare --check` | PASS | Readonly test DB, 52 functions ไม่มี differences, effective privileges/ACL ผ่าน; committed=false |
| `python -B -m database.tools.Auth_Install --check-runtime` | PASS | Direct LOGIN project_app/read-only/test DB |
| Backend regression | PASS202 tests / 22.146s | Auth65 + Team37 + Members18 + Project32 + Invitations24 + DB boundary9 + advisor provisioning17; SQL/ACL/rows กลับ baseline |
| Direct app ASGI smoke | PASS | session_user=current_user=project_app; PATCH ชื่อและ description ผ่าน controlled SQL; ROLLBACK/baseline PASS |
| `npm run lint`, `npx tsc --noEmit` | PASS | Frontend source/tests |
| `npm run build` | PASS | Production build; route เดิม ไม่มี Submission/Milestone routes |
| `npm run test:e2e` | PASS49 tests / 43.3s | Auth5 + Invitations12 + Project16 + Members8 + Team8; browser_database_rollback=PASS, fixture_connections=0 |
| Desktop/Mobile visual inspection | PASS | ตรวจ screenshots ฟอร์ม Desktop และ Mobile390px; ไม่พบ horizontal overflow ปุ่ม pending/cancel อ่านได้ |
| SQL/config boundary | PASS | SQL V1/RBAC/Auth4ไฟล์ byte-identical กับ HEAD และ backend/auth_store.py ไม่เปลี่ยน |

Backend regression command จาก root:

```powershell
python -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_invitation_api database.tests.test_test_database database.tests.test_advisor_provision -q
python -B -m backend.tests.team_api_direct_smoke
```

ใช้ Python ใน `backend/.venv` ตามคู่มือตั้งค่า ไม่ใช่ Python system ที่ไม่ทราบ dependencies; คำสั่ง Frontend รันจาก `frontend`

### ขอบเขต DB fixtures และ Browser failures

- ทุกชุดตรวจชื่อ `student_project_management_v1_test` ผ่าน connection/role guards ก่อน business operations ไม่เข้าฐานหลัก
- HTTP integration ใช้ owner เฉพาะบัญชี advisor/coordinator/การจัด session fixtures แล้วสลับกลับ project_app ทุก business operation; ทดสอบ direct LOGIN app แยกอีกชุด ไม่มี superuser ข้ามสิทธิ์
- Phase fixtures สร้าง Invitation/Submission/file/review/committee/vote ด้วย SQL V1 และ controlled functions ใน transaction ทดสอบเดียวกัน ไม่เพิ่มหรือใช้ Submission API ของเพื่อน และไม่ COMMIT fixture
- File bytes ใน phase fixture เป็น DB-only data ไม่ใช่ PDF content-validation หรือการตรวจรับ upload ของเพื่อน
- การโอนหัวหน้าใน fixture defer cardinality จนเปลี่ยนบทบาทครบแล้วบังคับ IMMEDIATE ไม่แก้ trigger/function/schema
- Backend พิสูจน์ pending/advisor-approved/advisor-revision/committee-partial/committee-final-approval/committee-final-revision กับ PostgreSQL จริง และ snapshot เดิมคงเดิม
- Browser ใช้ API→DB จริงสำหรับ happy path/partial update/member denial/CSRF/session; กรณี409 phase ใน Browser เป็น mocked response เพื่อพิสูจน์ UI ส่วน phase rule จริงพิสูจน์ใน Backend ข้างต้น
- กรณี lost PATCH response ใน Browser เรียก backend ให้บันทึกลง outer test transaction จริงก่อนตัด response แล้วใช้ GET ตรวจค่าที่เปลี่ยน ไม่มีการ retry write และสุดท้าย ROLLBACK
- Browser harness มี Project UOW override เดิมอยู่แล้วจึงไม่แก้ harness; outer rollback ครอบคลุม Project PATCH ด้วย RLock เดิม ไม่หลุดไป normal app connection
- ตรวจ metadata/owners/ACL/row counts กลับ baseline และ test connection ปิดทั้งหมด **ไม่รวม identity sequence values** ที่อาจเพิ่มแม้ ROLLBACK

## จุดรวมกับงานเพื่อน / สิ่งที่ยังเหลือ

1. เพื่อนยังเป็นเจ้าของ Submission/Milestone/Supabase งานนี้ไม่เปลี่ยน branch/ref ของเพื่อน
2. ตอนรวม `backend/main.py` ต้องรักษา CORS PATCH ที่เพิ่ม กับ Submission middleware/router ของเพื่อนพร้อมกัน ไม่ overwrite ไฟล์ใดทั้งไฟล์; รักษาลำดับ CORS/body-limit/error/no-store เดิมของแต่ละงาน
3. OpenAPI paths ยัง15 paths เพราะ PATCH เพิ่ม method ใน pathเดิม; เพื่อนเพิ่ม Submission ต้องรักษา `{get,patch}` ของ `/projects/me` และเพิ่ม paths/test expectations ตาม scope ของตน
4. Browser harness ต้องรักษา Project UOW override และเพิ่มของ Submission/Milestone ให้ครบก่อน Browser writes เสมอ ปัญหา isolation ของ peer HTTP suite ที่บันทึกก่อนหน้ายังไม่ได้แก้แทนเพื่อน
5. Supabase เป็นอนาคต ยังไม่ใช้ AUTH_DATABASE_URL/DBอื่นหรือเปลี่ยน role/runtime policy ในงานนี้
6. ไม่ได้พิสูจน์ multi-session concurrency, fresh-machine install, HTTPS/LAN/production/UAT หรือ successful runtime COMMIT; ผลที่รันเป็น rollback tests ตามข้อกำหนด

สถานะ Project update เฉพาะ Contract นี้: implemented/tested ทั้ง Backend/Frontend แต่ P09 รวมออก/ถอดสมาชิก/โอนหัวหน้า API/UI และจัดการ Team ส่วนที่ยังเหลือ จึงไม่ปิด P09 ทั้งแถว ไม่มีงานหลัก Done เพิ่ม คง checklist Done5/20=25% ไม่ใช้จำนวนtestsแทนความคืบหน้าทั้งระบบ
