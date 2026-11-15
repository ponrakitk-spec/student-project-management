# Workspace overview — Approved UI contract

วันที่ 2026-11-15 (Asia/Bangkok) · ผู้ใช้ยืนยัน **“พัฒนาหน้าพื้นที่ทำงานตามร่าง”** แล้ว ขอบเขต UI ด้านล่างได้รับอนุมัติ ไม่ขยายไป Dashboard metrics/งานเพื่อน

เสนอหน้าพื้นที่ทำงานเริ่มต้นที่ใช้ฟังก์ชันยืนยันแล้ว ช่วยเข้าถึงงานตามบทบาทจากจุดเดียว อ้างอิง [Schema V1 Reference](../database/SCHEMA_V1_REFERENCE.md) และ [Backlog](../progress/BACKLOG.md) ขอบเขตนี้ไม่เปลี่ยน Business Rules หรืออนุมัติ Dashboard metrics/Timeline/Contribution ใน U03

## หน้าและการนำทางที่ยืนยัน

- เพิ่ม `/workspace` แบบ protected page ใช้ Login/Session เดิม และเพิ่มลิงก์ “พื้นที่ทำงาน” จากหน้าบัญชี `/`
- หลัง Login ยังกลับหน้าบัญชีตาม Contract เดิม หน้าพื้นที่ทำงานมีลิงก์กลับบัญชี ไม่เปลี่ยนเส้นทางหน้า feature เดิม
- แยกโค้ดใน `src/features/workspace-overview` และ routeใน `src/app/workspace/page.tsx` ใช้รูปแบบภาพรวม Desktop/Mobile ที่สอดคล้องกับระบบเดิม

## ข้อมูลตามบทบาท

| ผู้ใช้ | ข้อมูล/ทางเข้าที่อนุมัติ |
|---|---|
| student | อ่านทีมตนเองจาก `GET /api/v1/teams/me`; แสดงชื่อทีมและบทบาท leader/member ถ้ามีทีมจึงอ่าน `GET /api/v1/projects/me` เพื่อแสดงชื่อ/คำอธิบาย Project ของทีม มีลิงก์ไปทีมและโครงงาน |
| advisor | แสดงทางเข้า “คำเชิญของฉัน”, “โครงงานที่ปรึกษา”, “งานกรรมการ” ไปหน้าที่มีอยู่แล้ว ไม่อ่าน Project ข้าม scope หรือประกาศว่าเป็นกรรมการทุก Project |
| coordinator | แสดงทางเข้า “จัดการกรรมการโครงงาน” ไปหน้าเดิมซึ่งใช้ approved Project scope ตาม G-12 |

หน้านี้ไม่เพิ่ม Backend API/SQL/grants และไม่รวมข้อมูลรายชื่อผู้ใช้/สมาชิกอื่น/คะแนนรายบุคคล ผู้ใช้เห็นข้อมูลจาก API ที่ตนมีสิทธิ์เดิมเท่านั้น ไม่มีตัวเลขสรุปความคืบหน้า/จำนวนงาน/สูตรContribution/กราฟ/กิจกรรมล่าสุด/Notification เพราะยังไม่ได้ยืนยันนิยาม

## สถานะและข้อผิดพลาด

- ยังไม่มีทีม: แสดงข้อความที่ชัดเจนและลิงก์ไปเริ่มสร้างทีม ไม่แสดง Project creation ที่ข้าม C-01
- มีทีมแต่ไม่มี Project: leaderมีลิงก์ไปเริ่มสร้างที่หน้า Project เดิม; memberเห็นว่าหัวหน้าทีมเป็นผู้สร้าง ไม่ให้ปุ่มเขียนข้อมูลจากหน้าภาพรวม
- มีทีม/Projectแล้ว: อ่านข้อมูลจริงและไปหน้าจัดการเดิม การสร้าง/แก้ไข/โอน/ออก/ถอดยังใช้ confirmationและAPIเดิม
- แยก loading/error/empty; generic404/403/network/malformed responseไม่ตีความว่าไม่มีทีม/Project ห้ามแสดงข้อมูลตัวอย่างเป็นผลจริง มี retryและตรวจข้อมูลใหม่ได้
- ถ้า sessionหาย/หมดอายุ: ไป Loginตามพฤติกรรมเดิม ไม่มี business requestก่อนรู้บทบาท; เปลี่ยนบัญชี/roleต้องยกเลิกคำขอเก่าและไม่ค้างข้อมูลผู้ใช้เดิม
- อ่านแบบ `credentials:include`/`cache:no-store` และใช้ AbortController ไม่เก็บข้อมูลส่วนตัวหรือsessionลง localStorage

## การตรวจรับ

1. studentไม่มีทีม/มีทีมไม่มีProjectทั้งleader-member/มีProject ใช้ APIจริงและแสดงข้อมูลตรงบัญชีหลัง refresh
2. advisor/coordinatorเห็นทางเข้าตามบทบาทและไม่ส่งคำขอ APIของstudent; URLตรงยังให้ Backendตรวจscopeเดิม
3. anonymous/sessionexpired/403/404ทั่วไป/network/malformed response/retry ไม่แสดงข้อมูลหรือสิทธิ์ที่คาดเดา
4. Desktop/Mobile/keyboard navigation/no horizontal overflow และ regressionการ Login/หน้าบัญชีเดิม
5. Browser fixtureใช้ test DB เท่านั้น ทุกข้อมูลทดลอง ROLLBACK ไม่เพิ่มข้อมูลถาวรหรือใช้ DBหลัก

**เกณฑ์สถานะ:** การทำหน้านี้สำเร็จถือว่ามี workspace navigation/summary ตามขอบเขตเท่านั้น ไม่ปิด ST-01 Dashboardเต็ม/U03/P15/P17/P19 หรืออ้างว่า Submission/Milestoneของเพื่อนพร้อมใช้งาน

## ไฟล์ในขอบเขตพัฒนา

เพิ่ม workspace route/feature styles/screen และ Browser tests; เพิ่มลิงก์ใน `frontend/src/features/auth/account-screen.tsx` พร้อมอัปเดต README/Backlog/implementation reportตามผลจริง ไม่แก้ Auth flow/Backend/Schema/RBAC หรือ sourceงานเพื่อน

อ่านผล implementation และข้อจำกัดที่ตรวจพบใน [Workspace implementation report](../progress/WORKSPACE_OVERVIEW_IMPLEMENTATION_REPORT.md)
