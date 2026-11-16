# Milestone สำหรับทีม — ขอบเขตยืนยัน 2026-11-16

ผู้ใช้เลือก “เริ่ม Milestone สำหรับทีมตามขอบเขตนี้” สมาชิก student อ่านได้เฉพาะทีมปัจจุบัน หัวหน้าทีมจัดการได้ ใช้ Login/CSRF/Origin เดิม ไม่มี Task API หรือหน้าอ่านของ advisor/coordinator ในรอบนี้ ไม่เปลี่ยน Schema/RBAC/กฎ V1

| Method/path | ผล |
| --- | --- |
| GET `/api/v1/projects/me/milestones` | 200 `{data:{project_id,can_manage,milestones:[]}}` เรียง due_date ASC,id ASC; `can_manage` เป็นสิทธิ์หัวหน้าที่ยังไม่มี Evaluation แรก |
| POST `/api/v1/projects/me/milestones` | รับ name, description optional/null, due_date `YYYY-MM-DD`; 201 `{data:Milestone}` |
| GET `/api/v1/milestones/{id}` | 200 `{data:Milestone}` เฉพาะสมาชิกทีมเจ้าของ |
| PATCH `/api/v1/milestones/{id}` | แก้เฉพาะ name/description/due_date ที่ส่ง; ไม่รับ `{}` หรือ null name/date; 200 `{data:Milestone}` |
| DELETE `/api/v1/milestones/{id}` | หัวหน้ายืนยันก่อนลบ; 204 body ว่างเมื่อไม่มี Task และยังไม่ล็อก |

Milestone DTO ใช้ 11 fields ตาม V1: id/project_id/created_by/updated_by เป็น decimal strings (updated_by nullable), name, description nullable, due_date เป็น DATE, status ที่ derive จาก Tasks, created_at/updated_at และ completed_at nullable เป็น ISO timestamps ไม่รับ actor/project/status/timestamps จาก request

ใช้ `v1_create_milestone`, `v1_update_milestone`, `v1_delete_milestone` เดิม กำหนด actor จาก session และ recheck membership/leader หลัง Team→Project locks ไม่เพิ่มสิทธิ์ direct DML due_date เมื่อสร้างหรือเปลี่ยนค่าต้องไม่ก่อน DB Bangkok date (แก้ metadata โดยคง due_date เดิมที่ผ่านไปแล้วได้ตาม SQL); D-01 ไม่เลื่อน Task ให้เอง; first Evaluation ล็อกทุก write; Task FK RESTRICT ยังห้ามลบ ไม่มี advisor/topic approval gate เพิ่ม

Errors: 401 AUTHENTICATION_REQUIRED; 403 MILESTONE_ACCESS_FORBIDDEN (role อื่น)/MILESTONE_ACTION_FORBIDDEN (สมาชิกไม่ใช่หัวหน้า)/CSRF_INVALID/ORIGIN_NOT_ALLOWED; 404 TEAM_NOT_FOUND/PROJECT_NOT_FOUND สำหรับ collection และ MILESTONE_NOT_FOUND สำหรับ ID ที่ไม่เห็น; 409 MILESTONE_NAME_CONFLICT/MILESTONE_LOCKED/TASK_DUE_DATE_CONFLICT/MILESTONE_HAS_TASKS; 422 VALIDATION_ERROR/MILESTONE_DUE_DATE_PAST; 500 INTERNAL_ERROR สำหรับ storage/สิทธิ์ DB/SQLSTATE ที่จำแนกไม่ได้ ไม่เผย SQL

หน้า `/projects/milestones` แสดงรายการ/derived status/วันไทย หัวหน้าสร้างและแก้ metadata และยืนยันก่อนลบ สมาชิกอ่านอย่างเดียว เมื่อ request เขียนไม่ทราบผลให้โหลดรายการก่อนทำใหม่ ไม่มี automatic write retry วันที่จาก browser เป็นข้อมูลกรอก ส่วน business date ยึด PostgreSQL Asia/Bangkok
