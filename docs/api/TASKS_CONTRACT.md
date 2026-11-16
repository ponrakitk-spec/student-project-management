# Task / ผู้รับผิดชอบงาน — ขอบเขตยืนยัน 2026-11-16

**สถานะ: Approved scope** ผู้ใช้เลือก “พัฒนา Task/ผู้รับผิดชอบตามร่างครบ workflow” แล้ว ต่อยอด [Milestone สำหรับทีม](MILESTONES_CONTRACT.md) เพื่อให้ทำ Task จน Milestone completed และไปถึง Evaluation ผ่านเว็บได้ ไม่เปลี่ยน Schema V1/RBAC/Business Rules และไม่เพิ่มบทบาทใน users สถานะทดสอบให้ดูรายงาน ไม่ถือว่าอนุมัติ scope แล้วเท่ากับ runtime ผ่าน

## ขอบเขตที่ยืนยัน

- student สมาชิกปัจจุบันอ่าน Task/ผู้รับผิดชอบ/ประวัติถอนงานของ Project ทีมตนได้เท่านั้น รอบนี้ยังไม่เพิ่มหน้าอ่าน Task สำหรับ advisor/coordinator
- หัวหน้าทีมปัจจุบันสร้าง/แก้ metadata/ลบ Task และเพิ่ม/ถอนผู้รับผิดชอบ เลือกจากสมาชิกปัจจุบันของทีม ไม่ใช้ email หรือเปิด user directory ใหม่
- สมาชิกปัจจุบันเปลี่ยนสถานะ Task ที่ยังไม่ completed ได้ตามกฎเดิม ไม่เพิ่มเงื่อนไขว่าต้องเป็น assignee; completed เปิดกลับ in_progress ได้เฉพาะหัวหน้า
- เพิ่มหน้า `/projects/milestones/{milestone_id}/tasks` จากลิงก์ในรายการ Milestone มี form งาน/สถานะ/ผู้รับผิดชอบ และส่วนอ่านประวัติถอนงาน ยืนยันก่อนลบ/ถอนผู้รับผิดชอบ

## กฎที่ยืนยันแล้วจาก V1 (ไม่ใช่ข้อเสนอใหม่)

อ้างอิง [Data Dictionary](../database/Database_Schema_V1_Data_Dictionary.md) ตาราง12–14/4.2 และ `v1_task_guard`, `v1_task_assignee_guard`, `v1_refresh_milestone` ใน [SQL](../../database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql)

- name trim ASCII whitespace ไม่ว่าง สูงสุด255 Unicode code points; unique case-insensitive ภายใน Milestone เดียวกัน; description optional TEXT ว่างเป็น null ไม่มี maxlen ใหม่
- due_date optional/null; เมื่อสร้าง/เปลี่ยน ถ้ามีค่าต้องไม่ก่อน DB Bangkok date และไม่เกิน Milestone due_date; ไม่เลื่อนวันงานหรือ Milestone อัตโนมัติ
- สร้างเป็น not_started เสมอ actor/เวลา/milestone_id immutable ตาม DB; status ไม่อยู่ใน create/metadata request
- not_started→in_progress/completed และ in_progress→not_started/completed ตามกฎ; เข้า in_progress หรือ completed ต้องมี assignee อย่างน้อย1; completed→not_started ไม่ได้; completed→in_progress เฉพาะหัวหน้า
- completed ต้องเปิดกลับก่อนแก้ metadata/ลบ; completed หรือหลัง Evaluation แรกห้ามจัด assignee ตามปกติ; หลัง Evaluation แรกล็อก Task writes ทั้งหมดโดยยังรักษาข้อยกเว้น member-exit เดิม
- เพิ่ม assignee ได้เฉพาะสมาชิกปัจจุบันทีมเดียวกันและไม่ซ้ำ ถอนแล้ว DB บันทึก user_id/assigned_at/unassigned_at ลง history; C-02 ห้ามทิ้ง Task in_progress ไร้ assignee
- ลบ Task ที่อนุญาตแล้ว cascade assignees/history ตาม V1 โดยไม่สร้างประวัติถอนเทียม ไม่ลบ Project/Milestone
- Milestone derive สถานะจาก Tasks ใน transaction เดียว ไม่รับ milestone.status หรือ Task timestamps จาก Browser

## API ที่ยืนยัน — 10 operations / 6 paths

| Method/path | Request / response |
| --- | --- |
| GET `/api/v1/milestones/{milestone_id}/tasks` | 200 `{data:{milestone,can_manage,tasks:[]}}` |
| POST `/api/v1/milestones/{milestone_id}/tasks` | name, description optional/null, due_date optional/null →201 `{data:task}` |
| GET `/api/v1/tasks/{task_id}` | 200 `{data:task}` เฉพาะทีมปัจจุบัน |
| PATCH `/api/v1/tasks/{task_id}` | partial name/description/due_date ไม่รับ `{}` หรือ null name →200 `{data:task}` |
| DELETE `/api/v1/tasks/{task_id}` | หัวหน้าทีมยืนยันลบ →204 bodyว่าง |
| POST `/api/v1/tasks/{task_id}/status` | `{status:not_started/in_progress/completed}` →200 `{data:task}` |
| GET `/api/v1/tasks/{task_id}/assignees` | 200 `{data:assignee[]}` |
| POST `/api/v1/tasks/{task_id}/assignees` | `{team_member_id:string}` →201 `{data:assignee}` |
| DELETE `/api/v1/tasks/{task_id}/assignees/{team_member_id}` | หัวหน้าถอนหลังยืนยัน →204 |
| GET `/api/v1/tasks/{task_id}/assignment-history` | 200 `{data:history[]}` |

Task DTO: 11 fields ตามตาราง tasks — id/milestone_id/created_by/updated_by เป็น decimal strings (updated_by nullable); name/description/due_date/status/created_at/updated_at/completed_at ใช้รูปแบบเดียวกับ Milestone (description/date/completed_at nullable)

Collection คืน Milestone DTO เดิมและ can_manage สำหรับสิทธิ์หัวหน้าที่ยังไม่มี Evaluation แรก; งานที่ completed มีข้อจำกัดตามกฎ Task แยกต่างหาก รายการเรียงตาม DD4.5: due_date ASC NULLS LAST,id ASC

Assignee DTO เสนอ `{id,team_member_id,user:{id,full_name},assigned_at}` ไม่ส่ง email; history เสนอ `{id,user:{id,full_name},assigned_at,unassigned_at}` เรียง unassigned_at DESC,id DESC ส่วน assignees เรียง assigned_at ASC,id ASC ตาม DD4.5

## Auth / errors / transaction

ใช้ session8h/Origin/CSRF/no-store เดิม ทุก ID เป็น string ไม่รับ actor/role/history/เวลาเอง; request เขียนไม่ทราบผลต้อง GET ตรวจ ไม่มี automatic retry

401 AUTHENTICATION_REQUIRED; 403 TASK_ACCESS_FORBIDDEN/TASK_ACTION_FORBIDDEN/CSRF_INVALID/ORIGIN_NOT_ALLOWED; 404 TASK_NOT_FOUND/MILESTONE_NOT_FOUND/ASSIGNEE_NOT_FOUND เมื่อไม่มีหรือไม่มีสิทธิ์รับรู้

422 VALIDATION_ERROR/TASK_DUE_DATE_INVALID; 409 TASK_NAME_CONFLICT/TASK_LOCKED/TASK_COMPLETED/TASK_ASSIGNEE_REQUIRED/TASK_STATUS_CONFLICT/ASSIGNEE_ALREADY_ASSIGNED/ASSIGNEE_NOT_CURRENT_MEMBER; storage/42501/SQLSTATE ที่ระบุไม่ได้เป็น sanitized500 ไม่เปลี่ยน grant เพื่อให้ผ่าน

ใช้ `v1_create_task`, `v1_update_task_metadata`, `v1_set_task_status`, `v1_delete_task`, `v1_assign_task`, `v1_unassign_task` เดิม ผ่าน project_app และลำดับ Team→Project→Milestone→Task โดย controlled functions ตรวจซ้ำหลัง lock ไม่ตั้ง member-exit context เพื่อถอนงานตามปกติ ต้องบังคับ deferred constraints ก่อนสำเร็จเมื่อเหมาะสม

## การตรวจรับที่ต้องทำหลังยืนยัน

- HTTP+PostgreSQL/Browser ทำ Task→assign→completed→Milestone derive completed→เปิด Evaluation form ได้จริง
- member เปลี่ยนสถานะได้ตาม SQL แต่แก้ metadata/assign/delete ไม่ได้; leader reopen; cross-team/exited member ไม่รั่ว
- วัน/null/name/unique/invalid transition/ไม่มี assignee/C-02/completed/first-score locks และ rollback ทั้งชุด
- assignee history จากการถอน/exit และ cascade เมื่อลบ Task ตามกฎ ไม่มี history จำลองจาก Browser
- 10 UOW overrides หลังเพิ่ม Task ให้ TestClient/Browser/HTTP harness ก่อนรันเขียน ไม่ให้หลุด normal connection COMMIT
- ทดสอบเฉพาะ test DB/ROLLBACK และคืน baseline; ช่วงเว็บทดลองปัจจุบันยังเปิดอยู่ ห้ามหยุดหรือรันทดสอบเขียนชนกับรอบนี้โดยยังไม่แจ้งเจ้าของเรื่องข้อมูลทดลองที่จะหาย

API/DTO/errors/UX ในเอกสารนี้ได้รับการยืนยันขอบเขตแล้ว ดู [รายงาน implementation และผลทดสอบจริง](../progress/TASK_IMPLEMENTATION_REPORT.md) สำหรับแยก source ที่พร้อมจากสิ่งที่ยังไม่ได้ทดสอบ
