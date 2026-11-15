# Evaluation concurrency — Rollback-only rehearsal

วันที่ 2026-11-15 (Asia/Bangkok) · `feature/project-continuation` บน `679913a` + working tree

**รอบต่อมา:** [เตรียม runner/fixture42แถว/installer](EVALUATION_CONCURRENCY_PREPARATION.md) แล้วผู้ใช้อนุมัติเฉพาะ seedใหม่ ติดตั้งและ [EC01–EC08หลายsessionผ่าน8/8](EVALUATION_CONCURRENCY_REPORT.md) พร้อม A-B ROLLBACK รายงานนี้คงเป็นหลักฐาน rehearsal38แถวรอบก่อน ไม่ใช่ข้อมูลที่ติดตั้งถาวร

ต่อจาก [Evaluation API/UI](EVALUATIONS_IMPLEMENTATION_REPORT.md) และคำสั่งให้พัฒนาต่อ รอบนี้เตรียมและซ้อมคำสั่งสำหรับ 8 สถานการณ์ โดยใช้กฎใน [Evaluation Contract](../api/EVALUATIONS_CONTRACT.md) และ Data Dictionary 4.2/4.3/4.4 เท่านั้น ไม่แก้ Submission/Milestone/Supabase ของเพื่อนหรือเพิ่ม API ใหม่

**ผล: DRY RUN ผ่าน คำสั่งแยก16ชุดและ ordered pairs8กรณี พร้อม ROLLBACK คืน baseline** เป็นการซ้อมใน PostgreSQL session เดียว ยัง **ไม่ใช่** ผล concurrent sessions, lock wait, HTTP race, winner-COMMIT หรือ TX-01 ครบ

## สถานการณ์ที่ซ้อม

แต่ละกรณีเริ่มจาก fixture เดิมของตน ซ้อม A และ B แยกกันแล้ว ROLLBACK กลับ จากนั้นซ้อม A→B ใน savepoint อีกชุดหนึ่งและ ROLLBACK อีกครั้ง ไม่ส่ง B จากอีก connection ในรอบนี้

| ID | A / B | ผลเมื่อ A ยังอยู่ใน transaction เดียวกันก่อน B |
|---|---|---|
| EC01 | คะแนนแรก / แก้ metadata ของ Task ที่ยังไม่เริ่ม | B ถูก `v1_task_guard` ปฏิเสธ P0001; B แยกเดี่ยวแก้ได้ |
| EC02 | คะแนนแรก / แก้ metadata ของ Milestone | B ถูก `v1_milestone_guard` ปฏิเสธ P0001; B แยกเดี่ยวแก้ได้ |
| EC03 | คะแนนแรก / ถอน assignee จาก Task ที่ยังไม่เริ่ม | B ถูก `v1_task_assignee_guard` ปฏิเสธ P0001; B แยกเดี่ยวถอนได้และมี history1แถว |
| EC04 | เปิด Task completed เพียงงานเดียวกลับเป็น in_progress / ให้คะแนน | derived Milestone เป็น in_progress; B ได้ `COMPLETED_MILESTONE_REQUIRED` |
| EC05 | ให้คะแนน / ให้คะแนน assignment เดิมซ้ำ | B ได้ `EVALUATION_ALREADY_RECORDED` ไม่มีการแก้คะแนนเดิม |
| EC06 | กรรมการคนแรกให้คะแนน / คนที่สองให้คะแนน | ทั้งคู่บันทึกได้ แต่ Team/Advisor/Coordinator ยังไม่เห็น partial scores |
| EC07 | คะแนนคนสุดท้าย / Team–accepted Advisor–Coordinator อ่านผล | รวม210/เฉลี่ย70; Coordinatorเห็น3รายเมื่อครบ; B แยกเดี่ยวเห็น summary=null/evaluations=[] |
| EC08 | Team อ่านผลขณะมี2คะแนน / กรรมการคนสุดท้ายให้คะแนน | A ยังไม่เห็นผลรวม; B ทำให้ครบและอ่านรวม210/เฉลี่ย70ได้ |

EC07/EC08 เตรียมคะแนน60และ70ใน savepoint เฉพาะกรณี อีก80ทำให้ครบ รวม210/เฉลี่ย70 ไม่สร้างคะแนนตั้งต้นถาวร

## Fixture และความปลอดภัย

เพิ่ม [Evaluation_Concurrency_Rehearsal.py](../../database/tools/Evaluation_Concurrency_Rehearsal.py) และ [offline safeguards](../../database/tests/test_evaluation_concurrency_rehearsal.py)

- ค่าเริ่มต้นแสดงแผนแบบ offline ไม่อ่าน config/เชื่อม DB; `--dry-run` เป็นโหมดเขียนชั่วคราวเพียงโหมดเดียว ไม่มี `--apply`, manifest export หรือ COMMIT
- Pin `student_project_management_v1_test` ผ่าน connection helper และตรวจ `current_database()` ซ้ำก่อน baseline/fixture หากผิดชื่อให้หยุด ไม่มี fallback
- ตรวจ installed V1 52 functions ตรง source ก่อนเริ่ม ใช้ owner ที่ไม่ใช่ superuser เตรียม users และ effective `project_app` ทำ business operations ตามสิทธิ์เดิม
- ใช้ Topic fixture helper เดิมสร้าง graph ใหม่ใน UUID namespace แยกจาก fixture ถาวรเดิม ไม่เลือก Project/ผู้ใช้จริงมาทดลองและไม่เปลี่ยน shared manifest
- Base fixture **38แถวชั่วคราว**: users8, teams2, members2, projects2, invitations2, submissions2, files2, committee assignments6, votes6, milestones2, tasks2, assignees2 ไม่มี credentials/sessions ส่วน Evaluation/history ที่เพิ่มระหว่างแต่ละ action/pair ก็ ROLLBACK
- Milestone หนึ่ง completed จาก Task จริง อีก Milestone มี not_started Task สำหรับทดสอบ metadata/assignee lock ไม่เขียน derived status ตรง ไม่เปิด phase flag เพื่อข้าม guard
- ซ้อมครั้งแรกพบ Task completed แก้ metadata ไม่ได้ตามกฎ V1 จึงแยก editable Task ดังกล่าวเพื่อไม่ใช้ข้อห้ามของ completed Task เป็นหลักฐาน first-score lock ไม่แก้ SQL ให้ยอมรับสถานะที่ผิดกฎ
- แต่ละ action/pair ตรวจ hash ของ public row values และ metadata/owners/ACL กลับเหมือนเดิม หลังจบตรวจ snapshot รวม row counts ของ public/auth อีกครั้ง ไม่แสดงข้อมูลแถว/hash/รหัสผ่านใน output; sequence values ไม่คืนเมื่อ ROLLBACK
- SQL error ที่ไม่ตรง expected P0001 หรือ business code ทำให้ FAIL ไม่ถูกนับเป็นผลสำเร็จ ตัวตรวจ offline ครอบคลุม wrong DB, metadata drift, role guard, permission failure, connection failure, redaction, rollback/close และห้ามโหมด apply/export

## ผลตรวจรอบนี้

| ชุด | ผล |
|---|---|
| Safeguards ใหม่ | **13 PASS** แบบ offline |
| Targeted regression | **64 PASS** = safeguards13 + Evaluation validator12 + Auth security16 + Evaluation API14 + Topic fixture safeguards9 |
| Baseline ก่อน DRY RUN | **PASS**, 52 functions/differences=[]/effective app ACL |
| PostgreSQL DRY RUN | **PASS**, isolated16/ordered8, baseline_restored=true, committed=false |
| ตรวจหลังซ้อม | **PASS**, baseline52 functions/ACL ตรง source; manifests ถาวรเดิม10+29แถว valid ผ่าน direct app แบบอ่านอย่างเดียว |
| ไฟล์/เอกสาร | **PASS**, Python syntax2ไฟล์/ลิงก์ภายใน103จุด/whitespace; SQLและdependency7ไฟล์ตรง HEAD หลัง normalize EOL ไม่พบ private secrets ใน6ไฟล์ที่ตรวจ ไม่มี staging |

Full Backend456/Browser100/lint/TypeScript/build ในรายงาน Evaluation เป็นผลรอบก่อน ไม่ได้รันทั้งหมดซ้ำรอบนี้ เพราะไม่มี production Backend/Frontend/SQL/dependency changes ผล64ไม่ใช่64live concurrency cases

## เรียกใช้บน Windows

หยุดงานเขียน test DB อื่นก่อนซ้อม เพื่อให้การเปรียบเทียบ baseline ไม่ปะปนกับข้อมูลจากโปรแกรมอื่น ไม่จำเป็นต้องเปิด Frontend หรือ Backend server

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Rehearsal
& .\backend\.venv\Scripts\python.exe -B -m unittest database.tests.test_evaluation_concurrency_rehearsal backend.tests.test_evaluation_validation backend.tests.test_auth_security backend.tests.test_evaluation_api database.tests.test_topic_vote_fixture -q
& .\backend\.venv\Scripts\python.exe -B -m database.tools.V1_Baseline_Prepare --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Evaluation_Concurrency_Rehearsal --dry-run
```

## งานถัดไปและขอบเขตที่ยังไม่อนุมัติ

ขั้นหลาย session ต้องมี fixture ที่ทั้ง A/B มองเห็นตั้งแต่เริ่ม เช่น Project พร้อมประเมินและกรณีที่เหลือคะแนนคนสุดท้าย พร้อม manifest/validation และ observer ยืนยัน `pg_blocking_pids`/PID แยกกัน โค้ดรอบนี้ยังไม่มี multi-session runner หรือ installer/manifest ที่พร้อมติดตั้ง

ห้ามนำ IDs ของ DRY RUN ไปใช้ใน session ใหม่ เพราะแถวเหล่านี้ ROLLBACK แล้ว และห้าม COMMIT fixture เองเพื่อแก้เรื่อง visibility ต้องเตรียมขอบเขต/จำนวนแถวและเครื่องมือให้ตรวจสอบก่อนขออนุมัติถาวรแยกต่างหาก การอนุมัติ fixture เดิม10+29แถวไม่ครอบคลุม fixture Evaluation ใหม่หรือ winner-COMMIT

Peer API integration/UAT/Task-Evaluation multi-session concurrency ยัง Not Verified ตามเดิม P18คง In Progress และ Done6/20=30% เป็น checklist เดิม ไม่มีงานหลักปิดเพิ่ม ไม่มี staging/Commit/Push
