# Evaluation — Implementation and verification

วันที่ 2026-11-15 (Asia/Bangkok) · local `feature/project-continuation` บน `679913a` + working tree · ไม่มี Commit/Push

ผู้ใช้ยืนยัน **ทำครบ API/UI ตามร่าง** และ **ใช้สิทธิ์ดูผลตามข้อเสนอ** ใน [Evaluation Contract](../api/EVALUATIONS_CONTRACT.md) พัฒนาครบขอบเขตนี้ โดยไม่แก้ Schema V1/RBAC หรือ Submission/Milestone/Supabase ของเพื่อน

## สิ่งที่ใช้งานได้

กรรมการเลือกโครงงานจากรายการเดิม ให้คะแนนจำนวนเต็ม 0–100 พร้อมความคิดเห็น และยืนยันก่อนบันทึกครั้งเดียว หากหัวข้อล่าสุดยังไม่ผ่านกรรมการหรือไม่มี Milestone completed อย่างน้อยหนึ่งรายการ จะบันทึกไม่ได้ คะแนนแรกทำให้ SQL เดิมล็อก Milestone/Task/Assignee ตาม V1; ข้อยกเว้นถอน assignee เมื่อออกทีมตาม C-02 ยังคงทำงาน

| บทบาท | ก่อนประเมินครบ | หลังประเมินครบ |
|---|---|---|
| กรรมการที่ได้รับแต่งตั้ง | เห็น Evaluation ของตน | ของตน + รวม/เฉลี่ย ไม่เห็นคะแนนหรือ comment คนอื่น |
| สมาชิกทีมปัจจุบัน / accepted Advisor | `summary:null` | รวม/เฉลี่ยเท่านั้น |
| Coordinator | `summary:null,evaluations:[]` | รวม/เฉลี่ย + คะแนน/comment/ชื่อ/เวลารายบุคคล |

Backend สร้าง projection ตามสิทธิ์ ไม่ส่งข้อมูลที่ต้องซ่อนให้ Browser กรอง คะแนน 0 แสดงจริง; SQL คำนวณ `SUM` เป็น decimal string และ `round(AVG)` เป็นจำนวนเต็ม ทดสอบกรณีค่าเฉลี่ย 0.5 → 1 และผลรวม 0 แล้ว

### API: 5 operations / 4 paths

| Method | Path | ผลสำเร็จ |
|---|---|---|
| GET / POST | `/api/v1/committee/projects/{id}/evaluations` | context 200 / own Evaluation 201 |
| GET | `/api/v1/projects/me/evaluations` | Team context 200 |
| GET | `/api/v1/advisor/projects/{id}/evaluations` | accepted Advisor context 200 |
| GET | `/api/v1/coordinator/projects/{id}/evaluations` | Coordinator context 200 |

Session/CSRF/Origin/no-store ใช้ระบบเดิม Actor/assignment มาจาก session และ scope ของ Project บันทึกผ่าน `v1_record_evaluation` เท่านั้น ขอ Project lock และตรวจเงื่อนไขซ้ำ บังคับ `SET CONSTRAINTS ALL IMMEDIATE` และจบ UOW ก่อนตอบ 201 Team reader ใช้ Team→Project lock พร้อมตรวจสมาชิกภาพซ้ำ ไม่มี direct Evaluation write หรือ owner fallback

Duplicate map เฉพาะ SQLSTATE23505 บน `public.committee_evaluations` และ constraint `committee_evaluations_committee_assignment_id_key` ที่ตรวจจาก catalog จริง SQL error อื่นไม่แปลงเป็น duplicate โดยเหมา: ทดสอบฉีด 42501/P0001 แล้วได้ sanitized500 ไม่เพิ่มสิทธิ์เพื่อข้าม error

### UI: 4 routes

- `/committee/projects/[id]/evaluations`: own/eligibility/form/confirmation
- `/projects/evaluations`: ผลทีมจาก Project ปัจจุบัน
- `/advisor/projects/[id]/evaluations`: ผล Project ที่ตอบรับ
- `/coordinator/projects/[id]/evaluations`: ผลตามสิทธิ์ Coordinator

เชื่อมลิงก์จาก Project/Committee/accepted Advisor/Coordinator เดิม ฟอร์ม pending ส่งครั้งเดียว หาก response สูญหาย/ผิดรูป/500 ต้องอ่าน GET เพื่อยืนยันผล ไม่มี auto POST retry; 409 โหลด context ใหม่ รองรับ Desktop/Mobile และไม่เก็บคะแนน/session ใน localStorage

## ไฟล์ในขอบเขตรอบนี้

| กลุ่ม | ไฟล์ / เหตุผล |
|---|---|
| Backend | [evaluation_api.py](../../backend/evaluation_api.py), [evaluation_store.py](../../backend/evaluation_store.py), [main.py](../../backend/main.py): endpoints/UOW/projection/handlers/no-store |
| Validation | [evaluation_validation.py](../../backend/evaluation_validation.py), [test_evaluation_validation.py](../../backend/tests/test_evaluation_validation.py): pure validator เตรียมจากรอบก่อน รวมในการตรวจรับครั้งนี้ |
| Backend tests | [test_evaluation_api.py](../../backend/tests/test_evaluation_api.py), [test_auth_security.py](../../backend/tests/test_auth_security.py): integration/privacy/error cases และ OpenAPI 33 paths |
| Fixture isolation | [auth_browser_server.py](../../backend/tests/auth_browser_server.py), [http_concurrency.py](../../backend/tests/http_concurrency.py): override Evaluation เป็น UOW ลำดับที่7 ใน outer ROLLBACK |
| Frontend feature | [api.ts](../../frontend/src/features/evaluations/api.ts), [evaluation-screen.tsx](../../frontend/src/features/evaluations/evaluation-screen.tsx), [evaluations.module.css](../../frontend/src/features/evaluations/evaluations.module.css) และ route pages ทั้ง4 |
| Navigation / Browser | Project/Committee/Topic screen links, [evaluations.spec.ts](../../frontend/tests/evaluations.spec.ts); Topic test เลือกลิงก์เดิมด้วยชื่อให้ชัดหลังเพิ่มลิงก์ Evaluation |
| Docs | Contract/รายงานนี้/Backlog/Schema reference/README/Frontend README/START_HERE/LOCAL_SETUP/SCHEMA2_INTEGRATION_HANDOFF |

Working tree มีงานสะสมจากรอบก่อนจำนวนมาก ตารางนี้ไม่กล่าวว่าทุกไฟล์ modified/untracked เป็นงานรอบ Evaluation

## ผลทดสอบจริง

| ชุด | ผล / สิ่งที่พิสูจน์ |
|---|---|
| Evaluation validator | **12 PASS**: 0/100/type/blank/NUL/surrogate/Unicode/ASCII trim ไม่มีเพดาน TEXT ใหม่ |
| Evaluation API + PostgreSQL | **14 PASS**: eligibility/role/scope/session/CSRF/Origin/duplicate/immutable/first-score lock/exit/privacy/rounding/UOW failure |
| Targeted Backend | **42 PASS** = Evaluation API14 + validator12 + Auth security16 |
| Full Backend ตาม LOCAL_SETUP | **456 PASS** รวม feature เดิม/DB tools/HTTP-Dual harness safeguards/Evaluation; ไม่ใช่456 live concurrency cases |
| Focused Browser | **10 PASS** บน Browser→FastAPI→test PostgreSQL และ transport-error cases |
| Full Browser | **100 PASS**, `browser_database_rollback:PASS`, `fixture_connections:0` |
| Frontend | lint / TypeScript / production build **PASS**; ตรวจภาพ Desktop/Mobile390 และ horizontal overflow ผ่าน |
| Baseline หลังทดสอบ | **PASS**: V1 52 functions ตรง source, differences=[], effective app privileges/Public ACL ตรงเดิม |
| Fixture เดิม / cleanup | **PASS**: manifest10+29แถว valid ผ่าน direct app, temporary Browser users0, shared fixture credentials/sessions0, fixture connections0 และพอร์ต runner3000/8001ไม่ค้าง |
| Source / docs audit | **PASS**: Python syntax9ไฟล์, local links206จุด, protected SQL/Auth/Invitation/dependency13ไฟล์ตรง HEAD หลัง normalize EOL, ไม่พบ private secret ใน22ไฟล์ที่ตรวจ; Git diff whitespace ผ่านและไม่มี staging |

คำสั่ง Full Backend อยู่ใน [LOCAL_SETUP](../team/LOCAL_SETUP.md) Browser ใช้ `cd frontend; npm run test:e2e` ผ่าน runner ที่ตรวจ DB/fixture graph และ ROLLBACK ไม่ใช้ dev server ของผู้ใช้ค้างไว้

Browser ครอบคลุม score0/100/รวม200-เฉลี่ย67, การปัดครึ่ง, ซ่อน partial scores ทุกบทบาท, phase errors จริง, lost201 recovery, role/scope/auth และมือถือ ส่วน malformed GET/invalid POST status/failed GET ใช้ transport mocks; stale eligible snapshot เป็น mock ก่อน POST ที่ถูก DB ปฏิเสธ duplicate จริง **ไม่ใช่ผล concurrency**

Full Browser รอบแรก 99 PASS/1 FAIL เพราะ mock อ่านข้อมูลเก่าถูกใช้หมดเมื่อ development mode อ่านซ้ำ ปรับให้ mock คง snapshot จน POST แล้วรันทั้งหมดใหม่ **100 PASS** ไม่มีการเปลี่ยน production logic เพื่อให้ test ผ่าน

## ข้อมูลและสิทธิ์ระหว่างทดสอบ

- ใช้เฉพาะ `student_project_management_v1_test` ตรวจ target ผ่าน connection guards ก่อน suite/fixture ไม่มีการเข้าถึง DB หลัก
- API runtime opener ยังคง direct LOGIN `project_app`; integration/Browser ใช้ borrowed connection ที่ business effective role เป็น `project_app` ส่วน `project_owner` เตรียมเฉพาะบัญชี fixture ไม่ข้าม permission ของ app
- ทั้ง7 UOW ใช้ connection ใน outer transaction เดียวกัน All new fixtures/credentials/sessions/phase data ROLLBACK ไม่มีบัญชีหรือ Project Evaluation ถาวรใหม่
- Prerequisite สร้างผ่าน controlled SQL: accepted invitation, topic votes, Milestone→Task→assignee→completed แล้วตรวจ derived Milestone ไม่เขียน `milestones.status` ตรง และไม่เรียก API เพื่อนที่ยังไม่รวม
- Shared fixture ที่เคยอนุมัติ10+29แถวยังคงอยู่ตามเดิม ไม่ใช่ข้อมูลใหม่จากรอบนี้ ROLLBACK ไม่คืน sequence values
- ไม่มี SQL DDL/GRANT/requirements/dependency/.env changes และไม่มี Git staging/Commit/Push ในรอบนี้

## งานคงค้าง

1. เชื่อม Submission/Milestone/Task API ของเพื่อนแล้วทดสอบ workflow จริงตั้งแต่ส่งหัวข้อจนประเมิน ยัง **Not Verified** ในขอบเขตนี้
2. Evaluation/Task/Milestone multi-session concurrency และ winner-COMMIT ยัง **Not Verified** ไม่ขยายผลจาก single-session หรือ stale-response test
3. UAT บัญชีจริง/เครื่องทีม/fresh install และตรวจรับระบบรวมยังไม่ครบ ไม่มีการสร้างบัญชี/seedถาวรเพื่อแก้จุดนี้เอง

P14 ปิดเฉพาะ Contract/API/UI/สิทธิ์ที่ยืนยันและทดสอบครบ เกณฑ์ integration/concurrency/UAT ยังคงติดตามใน P17/P18/P19 ของ [Backlog](BACKLOG.md) อัตรา Done6/20=30% เป็น checklist เท่านั้น
