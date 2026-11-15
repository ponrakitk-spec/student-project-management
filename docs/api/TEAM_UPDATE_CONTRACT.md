# Team metadata update — approved scope and implementation

วันที่ 2026-11-14 · P09/P15/P16/P17 · ผู้ใช้อนุมัติพัฒนา Team update ตามแนวทางที่เสนอด้วย “ดำเนินการพัฒนาได้เลย” รูปแบบ partial PATCH ใช้แนวทางเดียวกับ [Project update](PROJECT_UPDATE_CONTRACT.md) ที่ยืนยันแล้ว

ขอบเขตคือหัวหน้าทีมแก้ชื่อและคำอธิบายทีมที่หน้า `/teams` โดยใช้กฎ V1 เดิม ไม่เพิ่มออก/ถอดสมาชิก/โอนหัวหน้า/ลบทีม ไม่เปลี่ยน Schema/RBAC หรือ Submission/Milestone/Supabase ของเพื่อน ดู [บันทึกแบ่งงาน](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

## API

`PATCH /api/v1/teams/me` ใช้ Login/session8ชั่วโมง, Origin และ session-bound CSRF เดิม ทุก response no-store

```json
{"name":"ชื่อทีมที่แก้ไข","description":null}
```

- รับ name และ/หรือ description อย่างน้อยหนึ่ง field; field ที่ไม่ส่งคงค่าเดิม
- name ต้องเป็น string ที่ trim ASCII whitespace แล้วไม่ว่าง และไม่เกิน255Unicode code points ไม่รับ null
- description รับ string หรือ null; ASCII blank/null ล้างเป็น NULL ไม่มีเพดานความยาวใหม่ ไม่เปลี่ยนกฎ unique name ของ V1
- ปฏิเสธ fields อื่น รวม actor/team/id/membership/role/status ไม่ใช้ client headers/query เพื่อเลือกทีม
- Backendเลือกทีมจากสมาชิกภาพของ active student; ตรวจหัวหน้าทีมปัจจุบันอีกครั้งหลัง Team lock
- สำเร็จ200หลัง transaction จบ คืน DTO เดียวกับ [GET /teams/me](TEAM_CURRENT_CONTRACT.md): id/name/description/membership(id,role) IDsเป็นstrings ไม่เปิดข้อมูลสมาชิกอื่น
- no-op request ยังตรวจสิทธิ์และ phase; ไม่ใช้การส่งค่าเดิมเพื่อข้ามการล็อก

| HTTP / code | กรณี |
|---|---|
| 401 AUTHENTICATION_REQUIRED | sessionไม่มี/ผิด/หมดอายุ/ถูกยกเลิก |
| 403 TEAM_ACCESS_FORBIDDEN | advisor/coordinator เรียก student endpoint |
| 404 TEAM_NOT_FOUND | ไม่มีทีมปัจจุบัน หรือออก/เปลี่ยนทีมระหว่างรอ lock |
| 403 TEAM_UPDATE_FORBIDDEN | เป็นสมาชิกแต่ไม่ใช่หัวหน้าปัจจุบัน |
| 409 TEAM_METADATA_LOCKED | phase ของ Project ไม่อนุญาตให้แก้ metadata |
| 403 CSRF_INVALID / ORIGIN_NOT_ALLOWED | คำขอเขียนไม่ผ่านนโยบาย Auth เดิม |
| 422 VALIDATION_ERROR | JSON/ชนิด/name/descriptionผิด ไม่มีfieldหรือมีfieldเกิน |
| 500 INTERNAL_ERROR | storage/transaction/สิทธิ์ที่จำแนกไม่ได้; sanitized ไม่เผย SQL/secret |

## SQL และกฎ phase เดิม

- ตั้ง transaction-local actor จาก session ไม่รับ user_id จาก Browser
- ล็อก Team ผ่าน `public.v1_lock_team` ก่อน แล้ว recheck สมาชิกภาพ/หัวหน้า
- หากมี Project ล็อก Project และใช้ `public.v1_topic_metadata_editable`; ก่อนมี Project แก้ได้ตามสิทธิ์หัวหน้า ไม่เพิ่ม phase gate เอง
- ก่อนส่งครั้งแรก/ช่วง advisor ขอแก้/กรรมการลงครบและสรุปขอแก้ แก้ได้ ระหว่าง pending หรือ approved ที่ยังไม่เข้าเงื่อนไขขอแก้ และหลังกรรมการอนุมัติสุดท้าย แก้ไม่ได้
- อ่านและผสาน omitted fields จาก row ภายใต้ lock ก่อนเรียก `public.v1_update_team_metadata(bigint,text,text)` ไม่ให้ stale client values ทับช่องที่ไม่ได้ส่ง
- ใช้สิทธิ์ EXECUTE เดิมของ project_app ไม่มี direct UPDATE/owner fallback ไม่มี DDL/grant changes; ตรวจ constraints ก่อนตอบสำเร็จ
- ข้อมูล Project, snapshot/file/review เดิมและ membership ไม่เปลี่ยน; ไม่สร้าง Submission รอบใหม่ในงานนี้

## Frontend

- เพิ่มปุ่ม “แก้ไขทีม” และฟอร์มบันทึก/ยกเลิกใน `/teams` ให้ leader เท่านั้น สมาชิกยังอ่านข้อมูลและรายชื่อได้ตามเดิม
- บันทึกเฉพาะ field ที่เปลี่ยน; กรณี no-op ส่งชื่อเดิมเพื่อตรวจสิทธิ์/phase กับ server
- ไม่เพิ่ม phase/eligibility endpoint หรือเปลี่ยน GET DTO; Backendตรวจ phase ทุก PATCH และ UIแสดง409เมื่อถูกล็อก
- ป้องกัน submit ซ้ำระหว่าง pending; ยกเลิกก่อนส่งไม่เขียนข้อมูล
- ไม่มี automatic PATCH retry เมื่อ network/500/invalid success ทำให้ผลไม่แน่นอน ปิดการบันทึกซ้ำและเสนอ GET ตรวจทีมก่อน หลังสำเร็จใช้ข้อมูล server และรองรับ refresh
- ไม่เก็บข้อมูลทีม/session ลง localStorage/sessionStorage และไม่เปลี่ยน TTL/CORS ในรอบนี้ PATCHได้รับอนุญาตใน CORSจากรอบProject updateแล้ว

## การตรวจรับ

อ่าน [ผลทดสอบและไฟล์ที่เปลี่ยน](../progress/TEAM_UPDATE_IMPLEMENTATION_REPORT.md) โดยแยก real PostgreSQL phase tests ออกจาก mocked Browser error responses ทุก DB fixtureอยู่ใน student_project_management_v1_test และ Transaction/ROLLBACK ไม่เพิ่มสิทธิ์หรือ COMMITข้อมูลจำลอง
