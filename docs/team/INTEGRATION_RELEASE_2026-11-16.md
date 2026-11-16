# ชุดส่งต่อ branch รวม — 2026-11-16

ผู้ใช้สั่งพักงาน Supabase และอนุมัติ Commit/Push ความคืบหน้าวันนี้บน `feature/team-integration` ฐาน `6040702` ไม่เปลี่ยน `main`, `feature/project-continuation` หรือ branch เพื่อน `feature/database-schema2` การเผยแพร่นี้เป็น source/tests/docs ไม่ใช่การติดตั้งฐานข้อมูล

## งานที่รวมในชุดนี้

| ส่วน | ผลงาน |
|---|---|
| Submission | รับ Backend จาก snapshot เพื่อน `31c4fcb881ddff12d2f0a35b1e92c3c20eee8764` แบบเลือกส่วน เพิ่ม UI ส่งไฟล์/ประวัติ/ดาวน์โหลด/ตรวจและขอแก้ไข พร้อมแก้จุดเชื่อม fixture/UOW |
| Milestone | API/UI สำหรับทีมตนเอง หัวหน้าสร้าง/แก้/ลบ สมาชิกอ่านได้ ใช้กฎวันที่และสถานะคำนวณจาก Task เดิม |
| Task/Assignee/History | API/UI งานย่อย ผู้รับผิดชอบ เปลี่ยนสถานะ เปิดกลับ และประวัติถอนงาน พร้อมสิทธิ์/ล็อกหลัง Evaluation ตาม V1 |
| Integration | เชื่อม Project → Submission/Review → Committee/Vote → Task/Milestone → Evaluation ผ่าน API/UI ตาม Contract ที่ยืนยัน |
| Supabase | explicit test profile, Project/TLS/role guard, SQL deployment draft, read-only preflight และคู่มือ คง Login เดิม ยังไม่เปิดใช้งาน cloud |
| เอกสาร | Contracts, คู่มือ/Demo/UAT24กรณี, Backlog และรายงานรับช่วงงานเพื่อน/ผลทดสอบ |

รายละเอียด: [Submission integration](../progress/SUBMISSION_INTEGRATION_REPORT.md), [พัฒนาต่อจากเพื่อน](../progress/PEER_WORK_CONTINUATION_REPORT.md), [Task](../progress/TASK_IMPLEMENTATION_REPORT.md), [Supabase preparation](../progress/SUPABASE_PREPARATION_REPORT.md)

## หลักฐานก่อนส่ง

- Full local Backend regression ล่าสุด **603 PASS / 40 modules** หลังเพิ่ม Supabase profile และ local-preview guard พร้อม ROLLBACK คืน public row values/metadata/owners/ACL/Auth counts (ไม่รวม sequence values)
- Direct physical LOGIN `project_app` smoke ผ่าน Auth/Team/Project/Milestone/Task/assignee/history และคืน baseline หลัง ROLLBACK
- Offline Supabase/config/source safeguards **41 PASS** เป็นส่วนหนึ่งของ603 ไม่บวกซ้ำ
- Browser **130/130 PASS**, ESLint/TypeScript/production build ผ่านในรอบ Task ก่อนเพิ่ม backend-only Supabase profile ไม่มีการเปลี่ยน Frontend หลังผลนั้น ไม่อ้างว่าเป็นการทดสอบ Supabase หรือรัน Browser ใหม่ในรอบ Push
- Canonical V1/Auth SQL ไม่เปลี่ยน ไม่มี source requirement หรือ business rule ใหม่จากการเผยแพร่
- ตรวจ staged artifacts/known private secrets/ignore/whitespace ก่อน Commit และตรวจ remote commit หลัง Push โดยรายงาน commit จริงในแชท

## หยุดไว้ตรงไหนและทำต่ออย่างไร

1. Supabase: ผู้ใช้แจ้งว่ามี Project แล้ว แต่ยังไม่มีชื่อ/ref/URL และสถานะข้อมูลเดิม **Not Verified** ไม่สร้าง Project ซ้ำ ไม่รัน SQL draft หรือย้ายข้อมูล รอข้อมูลปลายทางเมื่อกลับมาทำต่อ
2. Cloud ต้องตรวจ version/managed roles/Data API exposure และอนุมัติการติดตั้งถาวรบน Project ที่ระบุ ก่อนตรวจ read-only/rollback workflow ตาม [คู่มือ](SUPABASE_SETUP.md) ห้ามนำ local installers/fixture runners ไปใช้กับ cloud
3. บัญชี/ข้อมูลจาก PostgreSQL ในเครื่องและ concurrency manifests ไม่ติดไปกับ Git สมาชิกทีมต้องตั้งค่า DB/config แยกตาม [Local Setup](LOCAL_SETUP.md) หากใช้ local profile
4. Manual UAT, fresh-machine setup และ Task/cloud concurrency ที่ยังไม่พิสูจน์ยังเปิดอยู่ ไม่ถือว่าระบบเสร็จจากจำนวน automated tests

ไฟล์ `.env` จริง รหัสผ่าน API keys DB dumps generated caches และบัญชี/ข้อมูลในเครื่อง ไม่อยู่ในชุดเผยแพร่ เว็บทดลอง local ROLLBACK แยกจาก Git การ Commit/Push ไม่ได้ยืนยันหรือยกเลิก transaction ของเว็บ

ข้อความ “ยังไม่ Commit/Push” ในรายงานรอบก่อนเป็นสถานะ ณ เวลาทดสอบของแต่ละรอบ เอกสารนี้บันทึกขอบเขตที่ได้รับอนุมัติให้เผยแพร่ ตรวจสถานะส่งสำเร็จและ commit hash จาก Git/แชทผลจริง
