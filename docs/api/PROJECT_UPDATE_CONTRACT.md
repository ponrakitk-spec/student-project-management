# Project metadata update — Approved and implemented

วันที่ 2026-11-14 · P09/P15/P16/P17 · **ผู้ใช้ตอบ “เริ่ม Project update ตามร่าง” แล้ว; implemented/tested** ดู [รายงานผล](../progress/PROJECT_UPDATE_IMPLEMENTATION_REPORT.md)

เพื่อนรับผิดชอบ Submission และ Milestone พร้อมเตรียม Supabase สำหรับอนาคต งานนี้ทำแยกบนฐาน `679913a` ใน `feature/project-continuation` โดยไม่แก้ branch เพื่อนหรือย้ายฐานข้อมูล ดู [บันทึกขอบเขต](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

## กฎเดิมที่ใช้ ไม่เปลี่ยน Schema V1

- หัวหน้าทีมปัจจุบันเท่านั้นที่แก้ชื่อ/คำอธิบาย Project ของทีมตนได้; รับ actor จาก active session และตรวจสมาชิกภาพใหม่หลังได้ lock
- ใช้ `public.v1_update_project_metadata(bigint,text,text)` และ `public.v1_topic_metadata_editable(bigint)` ที่มีอยู่ใน [SQL V1](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql) และ [RBAC](../../database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql) ไม่เพิ่ม direct UPDATE privilege
- แก้ได้ก่อนมี Submission หรือเมื่อรอบล่าสุดถูกขอแก้ไขโดย advisor หรือกรรมการลงครบและสรุปขอแก้ไข; ระหว่างรอตรวจ/หลัง advisor approved ที่ยังไม่เข้าเงื่อนไขแก้ไข/หลังกรรมการอนุมัติแล้ว แก้ไม่ได้ ใช้ผล SQL ไม่สร้าง phase rule ใหม่
- การแก้ Project ไม่เปลี่ยน snapshot/ไฟล์/ผลตรวจของ Submission เดิม งานเพื่อนยังเป็นผู้สร้าง Submission รอบใหม่และ snapshot ตาม V1
- ไม่เปลี่ยน team_id/created_by/id หรือเพิ่ม Project DELETE workflow; R-01 คงเดิม
- ชื่อ trim ASCII whitespace, ห้ามว่าง, ไม่เกิน 255 Unicode code points; description ไม่บังคับ trim แล้วว่างเป็น NULL ไม่เพิ่ม unique name หรือเพดาน description

## HTTP ที่ยืนยันและ implement แล้ว

`PATCH /api/v1/projects/me` ใช้ session, Origin, CSRF และ `Cache-Control: no-store` เดิม เลือก Project จากสมาชิกภาพผู้ใช้ ไม่รับ ID/actor/team/status/phase จาก client

```json
{"name":"ชื่อโครงงานที่แก้ไข","description":null}
```

- ส่ง name อย่างเดียวหรือ description อย่างเดียวได้ ต้องมีอย่างน้อยหนึ่ง field; field ที่ไม่ส่งให้คงค่าเดิม
- name ต้องเป็น string ที่ผ่านกฎเดิม ไม่รับ null; description รับ string หรือ null (ล้างคำอธิบาย) ไม่รับ field อื่น
- อ่านค่าเดิม/ตรวจหัวหน้า/phase และผสาน field ที่ส่งภายใต้ lock เดียวกัน ก่อนเรียก controlled function เพื่อไม่เขียนทับ field ที่ client ไม่ส่ง
- สำเร็จ 200 หลัง transaction จบ ใช้ DTO เดียวกับ [GET /api/v1/projects/me](PROJECT_CREATE_CONTRACT.md): id/name/description/team_id/created_by โดย IDs เป็น string
- ข้อมูลเหมือนค่าเดิมตอบ 200 เมื่อยังมีสิทธิ์และ phase อนุญาต ไม่ใช้ no-op เพื่อข้ามการตรวจสิทธิ์หรือ phase
- เพิ่มเฉพาะ PATCH ใน CORS methods ของ app พร้อมทดสอบ preflight/Origin/CSRF; GET/POST เดิมคงพฤติกรรม

| HTTP / code | เงื่อนไข |
|---|---|
| 401 AUTHENTICATION_REQUIRED | session ไม่มี/หมดอายุ/ถูกยกเลิก |
| 403 PROJECT_ACCESS_FORBIDDEN | advisor/coordinator เรียก student endpoint |
| 404 TEAM_NOT_FOUND / PROJECT_NOT_FOUND | ไม่มีทีม หรือทีมตนไม่มี Project |
| 403 PROJECT_UPDATE_FORBIDDEN | เป็นสมาชิกแต่ไม่ใช่หัวหน้าปัจจุบัน |
| 409 PROJECT_METADATA_LOCKED | phase ไม่อนุญาตให้แก้ |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | คำขอเขียนไม่ผ่านนโยบาย Auth เดิม |
| 422 VALIDATION_ERROR | payload ว่าง/field เกิน/ชนิดหรือข้อความผิด |
| 500 INTERNAL_ERROR | storage/transaction/สิทธิ์ DB ที่จำแนกไม่ได้; ไม่คืน SQL/traceback |

ใช้ transaction-local actor และ lock order Team → Project ตาม controlled function ตรวจสิทธิ์/phase หลังได้ lock ก่อนแก้ ไม่แปลง P0001/42501 ทุกกรณีเป็น business error และไม่ใช้ owner ข้าม permission denied

## UI ที่ยืนยันและ implement แล้ว

- ใช้หน้า `/projects` เดิม เพิ่มปุ่มและฟอร์มแก้ชื่อ/คำอธิบายสำหรับหัวหน้า พร้อมบันทึก/ยกเลิก; member อ่านได้ตามเดิม
- ไม่เพิ่ม eligibility endpoint หรือเปลี่ยน DTO ของ GET เดิมในรอบนี้ Server ตรวจ phase ทุก PATCH; เมื่อถูกล็อกแสดงข้อความจาก 409 ไม่สรุป phase เองจากชื่อสถานะบน Browser
- หลังสำเร็จใช้ข้อมูลจาก server; ไม่ retry PATCH อัตโนมัติ หากผลเครือข่ายไม่ชัดเจนให้โหลด Project ใหม่ก่อนส่งซ้ำ
- ไม่แก้หรือเพิ่มหน้า Submission/Milestone/Supabase ไม่แก้ snapshot หรือเพิ่มปุ่มลบ Project

## ขอบเขต implementation

- `backend/project_api.py`, `backend/project_store.py`: endpoint/model/authorization/controlled update
- `backend/main.py`: CORS PATCH เท่านั้น ไม่รับ Submission router จาก branch เพื่อนในงานนี้
- `backend/tests/test_project_api.py`, `backend/tests/test_auth_security.py`: DB rollback/permissions/phase/HTTP/OpenAPI expectations
- `backend/tests/team_api_direct_smoke.py`: PATCH บน direct LOGIN project_app และคืน baseline หลัง ROLLBACK
- `frontend/src/features/projects/` และ `frontend/tests/projects.spec.ts`: ฟอร์มแก้ไข/API client/การทดสอบ; route เดิม
- Browser harness ใช้ Project UOW override ที่มีอยู่ ตรวจยืนยันก่อน Browser writes; เอกสารรายงานและ backlog ตามผลจริง

SQL/RBAC/Requirements/.env/connection policy และ source ของ Submission/Milestone ไม่อยู่ในไฟล์ที่จะเปลี่ยน

## เกณฑ์ทดสอบ

1. หัวหน้าปัจจุบันแก้ metadata ได้ สมาชิก/staff/cross-team/spoof actor แก้ไม่ได้; หลังโอนหัวหน้าใช้สิทธิ์ปัจจุบัน
2. name/description แยก field, null/blank/255/256/Unicode, empty/unknown payload, normalize และ no-op authorization
3. phase ก่อนส่ง/รอตรวจ/advisor ขอแก้/approved/กรรมการขอแก้/อนุมัติสุดท้าย ตาม SQL; ใช้ fixture DB ที่ได้รับอนุมัติและ ROLLBACK ไม่แก้ runtime ของเพื่อนเพื่อสร้าง phase
4. snapshot เดิมคงค่าเดิมเมื่อ Project แก้ได้; created_by/team_id/id คงเดิม และ Project deletion ยังถูกห้าม
5. Auth/CSRF/Origin/CORS preflight, sanitized storage errors และ rollback เมื่อ transaction completion ล้มเหลว
6. Browser หัวหน้าแก้/ยกเลิก/refresh/member อ่าน/phase locked/network failure บน Desktop/Mobile โดยผูกทุก write กับ outer ROLLBACK

ทุกชุด DB ตรวจ `student_project_management_v1_test` ก่อน ใช้ project_app ใน business requests และตรวจ metadata/ACL/rows คืน baseline หลัง ROLLBACK ผล multi-session concurrency ยังเป็นงานแยก ไม่ COMMIT fixture เอง

ผลรอบนี้: Backend202 tests (Project32), direct app smoke, Browser49 (Project16), lint/TypeScript/build ผ่าน พร้อม ROLLBACK proof อ่านขอบเขตจริง/mocked HTTP failures/ข้อจำกัดที่รายงาน ไม่ได้รวม Submission/Milestone runtime ของเพื่อนหรืออนุมัติ Supabase
