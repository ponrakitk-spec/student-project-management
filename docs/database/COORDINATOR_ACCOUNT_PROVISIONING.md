# เตรียมบัญชี Coordinator — test DB เท่านั้น

วันที่ 2026-11-14 · CLI และ tests พร้อม · ผู้ใช้เลือก **กรอกชื่อ อีเมล และรหัสผ่านผ่าน CLI เอง** ยังไม่สร้างบัญชีถาวรแทนผู้ใช้ในรอบพัฒนานี้

ใช้ [Auth_Provision_Coordinator.py](../../database/tools/Auth_Provision_Coordinator.py) สร้าง users.role=coordinator ใหม่กับ auth.credentials ใน transaction เดียว โดย reuse validation/hash/hidden password/owner guard จากเครื่องมือ advisor เดิม ไม่ใช่เพิ่ม PostgreSQL Role ใหม่หรือเปิด public signup ให้เลือกบทบาท

## ขั้นตอนบน Windows / VS Code Terminal

จาก root `C:\student-project-management` ใช้ Terminal ปกติที่รับรหัสผ่านแบบซ่อนได้ ไม่ใช้ Debug Console และไม่ใส่ password ใน command, .env, input file หรือแชท

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Coordinator --check
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Coordinator --dry-run
```

กรอกชื่อ อีเมลจำลองรูปแบบถูกต้อง และรหัสผ่านผ่านคำถามบนเครื่อง อีเมลไม่ต้องมีกล่องรับจริง รหัสผ่านอย่างน้อย8ตัว มีA–Zและ0–9อย่างน้อยอย่างละ1 ใช้ Argon2id เดิม ไม่ trim password รหัสนี้เป็นของบัญชีในแอป ไม่ใช่รหัส PostgreSQL

DRY RUN สำเร็จจะแสดง `mode=DRY_RUN,persisted=false` แล้ว ROLLBACK ไม่มีบัญชีสำหรับ Login เกิดขึ้น อาจมี sequence ID เพิ่มแม้ ROLLBACK

เมื่อผู้ดูแลต้องการบันทึกบัญชีใหม่ที่กรอกเองจริง ๆ ให้ใช้คำสั่งแยกนี้และกรอกข้อมูลอีกครั้ง:

```powershell
& .\backend\.venv\Scripts\python.exe -B -m database.tools.Auth_Provision_Coordinator --apply --confirm-database student_project_management_v1_test
```

คำสั่ง apply บันทึกเฉพาะบัญชีใหม่1คน users+credentials ไม่รันเป็นส่วนหนึ่งของ tests และไม่เพิ่ม Project/Submission/กรรมการให้เอง ไม่มีการให้ agent รัน apply อัตโนมัติจากคู่มือนี้

หลังได้ `APPLIED,persisted=true` เปิดระบบปกติที่ Backendlocalhost:8000 / Frontendlocalhost:3000 แล้ว Login ด้วยบัญชีที่กรอกเอง จากหน้าบัญชีกด **จัดการกรรมการโครงงาน →**

หน้า Coordinator แสดงเฉพาะ Project ที่มี Submission ซึ่งอาจารย์อนุมัติแล้วตาม G-12 หากยังไม่มีข้อมูลแบบนี้ รายการว่างเป็นพฤติกรรมที่ถูกต้อง ไม่ต้องแก้สิทธิ์เพื่อให้เห็นทุกProject ปัจจุบัน Submission ของเพื่อนยังไม่ได้รวมเข้า branch นี้ Browser tests ใช้ DB-only phase fixtures ที่ ROLLBACK ไม่ใช่ข้อมูลจริงในหน้า runtime

## ขอบเขตและข้อผิดพลาด

- pin `student_project_management_v1_test` ผ่าน Test_Database helper ไม่ใช้ DB_NAME เพื่อเลือกฐานข้อมูลหลัก; ตรวจชื่อก่อนเปลี่ยน effective role เป็น project_owner ที่ไม่ใช่Superuser
- project_app ไม่มีสิทธิ์ใช้CLIสร้าง coordinator; ไม่มีowner fallback ใน API ไม่มีเพิ่มGRANT/DDL/RBAC/.env/dependencies
- บัญชีที่มี email อยู่แล้วทุกroleจะถูกปฏิเสธ ไม่ activate credential, เปลี่ยนrole/resetpassword/upsertบัญชีเดิมเอง ให้ใช้อีเมลใหม่สำหรับบัญชีใหม่
- `--apply` ต้อง confirm test DB; ไม่รับ `--password` หรือ `--role`; argument errorsไม่echoค่าที่อาจเป็นsecret
- `PASSWORD_TTY_REQUIRED` ให้ใช้Terminalที่รองรับ hidden input ไม่fallbackไปechoรหัส; `ACCOUNT_ALREADY_EXISTS` ไม่เปลี่ยนบัญชีเดิม
- เมื่อ storage/permission/configผิด CLI แสดงเฉพาะsafe code ไม่แสดงSQL/DSN/hash/password ให้ตรวจbaselineตามคู่มือ ไม่เพิ่มสิทธิ์เพื่อข้ามปัญหา

## หลักฐานรอบพัฒนา

[test_coordinator_provision.py](../../database/tests/test_coordinator_provision.py) **PASS11 tests**: boundary5 + real PostgreSQL6 รวม normalization/hash, duplicateไม่แก้บัญชีเดิม, credential failureย้อนคืนuser, default/nestedROLLBACK, Loginเป็นcoordinatorและstudentAPIปฏิเสธ และ directLOGINproject_appไม่สามารถassumeownerสร้างบัญชีได้

Positive fixtures ใช้effectiveproject_ownerเฉพาะstaff provisioningแล้วกลับproject_appก่อนAuth/API ไม่อ้างว่าเป็นผลcoordinatorบัญชีถาวรที่ผู้ใช้ยังไม่ได้สร้าง ทุกข้อมูลทดสอบ ROLLBACK และsnapshot definitions/ACL/row countsคืนbaseline ไม่รวมsequence values

ดู [Committee Contract](../api/COMMITTEE_ASSIGNMENTS_CONTRACT.md) และ [รายงาน API/UI](../progress/COMMITTEE_ASSIGNMENTS_IMPLEMENTATION_REPORT.md) สำหรับขอบเขตรอบแรก ซึ่งยังไม่รวม Vote/Evaluation API หรือหน้าจอ
