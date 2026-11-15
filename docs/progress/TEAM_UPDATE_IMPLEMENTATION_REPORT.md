# Team update — ผลพัฒนาและทดสอบ

วันที่ 2026-11-14 (Asia/Bangkok) · P09/P15/P16/P17/P19 · Branch `feature/project-continuation` จาก `679913a` + Working tree ยังไม่ Commit/Push

ผู้ใช้ตอบ “ดำเนินการพัฒนาได้เลย” หลังเสนอ Team metadata update จึงพัฒนาหัวหน้าแก้ชื่อ/คำอธิบายทีมตามกฎ V1 โดยยึด partial PATCH/session/CSRF แบบเดียวกับ Project update ดู [Contract](../api/TEAM_UPDATE_CONTRACT.md) และ [ขอบเขตงานเพื่อน](../team/SCHEMA2_INTEGRATION_HANDOFF.md)

## ผลลัพธ์

- เพิ่ม `PATCH /api/v1/teams/me` รับ name และ/หรือ description อย่างน้อยหนึ่ง field; ส่งเฉพาะช่องที่แก้ ช่องที่ไม่ส่งคงค่าเดิม description null/ASCII blank ล้างเป็น NULL
- เลือกทีมจาก active student session ไม่รับ actor/team/membership/role/status จาก client ให้เฉพาะหัวหน้าปัจจุบัน และ recheck หลัง Team lock
- หากมี Project ล็อก Project และตรวจ `v1_topic_metadata_editable` ก่อนเขียนผ่าน `v1_update_team_metadata` เดิม No-op ยังคงตรวจ role/phase ไม่ข้ามกฎด้วยการส่งค่าเดิม
- อ่าน omitted fields จาก row หลัง lock ไม่ใช้ค่าจาก client หรือ stale pre-lock read; ไม่เปลี่ยน membership/Project/submission snapshot เดิม
- ตอบ200หลัง transactionจบด้วย DTO เดียวกับGET /teams/me; phase locked409, member403, no team404 และ error envelope/no-store ตาม Contract
- หน้า `/teams` เพิ่มปุ่มและฟอร์มให้ leader บันทึก/ยกเลิก พร้อม validation/pending guard และ GET reconciliation เมื่อผลเครือข่ายไม่แน่นอน ไม่ automatic PATCH retry
- รักษารายชื่อ/เพิ่มสมาชิกและลิงก์ Project เดิม ไม่เพิ่มออก/ถอดสมาชิก/โอนหัวหน้า/ลบทีม API หรือหน้าใหม่

## ไฟล์ที่เปลี่ยนในงานนี้

| ไฟล์ | เหตุผล |
|---|---|
| `backend/team_api.py` | TeamUpdateInput/PATCH/errors/validation |
| `backend/team_store.py` | Lock/recheck/phase/controlled metadata update/DTO |
| `backend/tests/test_team_update_api.py` | HTTP+PostgreSQL12tests พร้อม reuse reviewed Project phase fixtures ใน outer ROLLBACK เดียวกัน |
| `backend/tests/test_auth_security.py` | OpenAPI GET/PATCH ของ Team โดยไม่ต่อ DB |
| `backend/tests/team_api_direct_smoke.py` | Direct app PATCH ชื่อ/description และ role/rollback proof |
| `frontend/src/features/teams/api.ts` | PATCH client และ reuse current-team DTO parser/errors |
| `frontend/src/features/teams/use-current-team.ts` | รับข้อมูลที่แก้สำเร็จจาก server โดยผูก owner เดิม |
| `frontend/src/features/teams/team-edit-form.tsx` | Partial form/validation/CSRF/pending/cancel/GET reconciliation |
| `frontend/src/features/teams/team-screen.tsx` | Leader-only editing, response team/membership checks, success notice และ React key แยกจาก member list |
| `frontend/src/features/teams/teams.module.css` | Edit panel/actions รองรับมือถือ |
| `frontend/tests/team-update.spec.ts` | Browser7tests รวม cancel/reopen/duplicate-key regression |
| Contract/report/backlog/team docs | บันทึก scope ผลใหม่และการรวมงาน |

ไม่มีการเปลี่ยน SQL/RBAC/Requirements/.env/dependencies/connection policy หรือ Submission/Milestone/Supabase source ของเพื่อน Main/CORS และ Browser UOW harness ใช้ของรอบ Project update ที่มี PATCH และ Team override ครบอยู่แล้ว ไม่ต้องเปลี่ยนในรอบ Team นี้

Working tree มี Project update และเอกสารตรวจ branch จากรอบก่อนอยู่ด้วย รายงานนี้ระบุเฉพาะส่วน Team update ไม่ถือว่าเป็นงานใหม่ทั้งหมดเมื่อเทียบ Git HEAD

## ผลทดสอบใหม่

| ชุด | ผล / ขอบเขต |
|---|---|
| V1 baseline readonly | PASS52functions/no differences/effective app ACL; test DBเท่านั้น committed=false |
| Auth direct runtime readonly | PASS project_app/student_project_management_v1_test |
| Team update HTTP+DB | PASS12tests / 3.762s ในรอบเฉพาะ feature |
| Full Backend regression | PASS214tests / 28.447s = Auth65 + Team37 + Members18 + Project32 + TeamUpdate12 + Invitations24 + DBboundary9 + provisioning17 |
| Direct app ASGI smoke | PASS session_user=current_user=project_app; Team PATCHชื่อ/description และ Project PATCH ผ่านโดยใช้สิทธิ์เดิม; ROLLBACK/baseline PASS |
| Frontend lint/TypeScript/build | PASS หลังแก้ React key แล้ว; routesเดิม ไม่มีSubmission/Milestone |
| Browser full suite | PASS56tests / 52.1s = Auth5 + Invitations12 + Project16 + Members8 + Team8 + TeamUpdate7; cleanupPASS/fixture_connections0 |
| Desktop/Mobile screenshots | ตรวจภาพ form Desktop และ Mobile390px อ่านได้ ไม่มี horizontal overflow และไม่มีฟอร์มซ้ำ |

คำสั่ง Backend จาก root ด้วย Pythonใน `backend/.venv`:

```powershell
python -B -m unittest backend.tests.test_auth_validation backend.tests.test_auth_security backend.tests.test_auth_api backend.tests.test_team_api backend.tests.test_team_members_api backend.tests.test_project_api backend.tests.test_team_update_api backend.tests.test_invitation_api database.tests.test_test_database database.tests.test_advisor_provision -q
python -B -m backend.tests.team_api_direct_smoke
```

Frontendจาก `frontend`: `npm run lint`, `npx tsc --noEmit`, `npm run build`, `npm run test:e2e`

## สิ่งที่พิสูจน์และขอบเขต

- DB guards ตรวจชื่อ test DB ก่อนทุกชุด ไม่เข้าฐานหลัก ไม่มี persistent DDL/grant changes หรือ COMMIT fixture
- Business requests ใช้ project_app; ownerเฉพาะเตรียม advisor/coordinator/session fixture ภายใน outer rollback ตามรูปแบบเดิม Direct LOGIN app มี smoke แยก ไม่ใช้ superuserข้ามสิทธิ์
- HTTPphase fixturesใช้ SQL V1/controlled functions สร้าง Project/Invitation/Submission/file/review/committee/vote ใน connection เดียวกันและ rollback ไม่ใช้หรือแก้ Submission API ของเพื่อน; file fixtureเป็นDB-only ไม่ใช่PDFcontent-validation
- ทดสอบแก้ทีมก่อนมีProject/ก่อนส่งครั้งแรก, pending/approvedที่ล็อก, advisorขอแก้, committeepartial/complete-revision/final-approval, no-op checks, สมาชิก/actor spoof/เปลี่ยนหัวหน้า และ Project/snapshot คงเดิม
- ทดสอบ stale pre-lock read ผ่าน test double และ recheck authority หลัง lock; นี่ไม่ใช่ real multi-session concurrency
- ทดสอบคืนข้อมูลเมื่อ SQLเขียนแล้วเกิด failure หรือเมื่อ transaction completion ล้มเหลว; unexpected42501/P0001ยังเป็นsanitized500 ไม่จำแนกจากข้อความ trigger ทั้งหมด
- Browserhappy path/partial update/member403/CSRF/sessionใช้ API→DB จริง; Browser409phaseเป็นmockเพื่อพิสูจน์UI ส่วน phaseSQLจริงพิสูจน์ในBackend
- Browserlost-success-responseเรียกbackendให้เปลี่ยนข้อมูลในouter test transactionจริงก่อนตัดresponse แล้วGETตรวจค่าโดยไม่ส่งPATCHซ้ำ สุดท้ายROLLBACKทั้งหมด
- พบ React key ของ edit form ซ้ำกับ member list ใน Browserรอบแรก (55ผ่าน/1ไม่ผ่าน) แก้ด้วย edit-key prefix และเพิ่มการตรวจ console duplicate-key; รัน Browserใหม่ครบ56ผ่าน ไม่เหลือ failureนั้น
- Cleanupยืนยัน metadata/owners/ACL/rowcountsคืนbaselineและไม่มีfixtureconnectionค้าง **ไม่รวม identity sequence values** ที่อาจเดินหน้าแม้ ROLLBACK

## จุดรวมงานเพื่อนและงานคงค้าง

1. รักษา Team API/store update และ DTO เดิมเมื่อรวม source เพื่อน อย่า overwrite Teamไฟล์ทั้งไฟล์จาก snapshotเก่า
2. รักษา CORS PATCH จากรอบProject และ OpenAPI `{get,patch}` ทั้ง `/teams/me` และ `/projects/me` เมื่อเพิ่ม Submission/Milestone endpoints
3. Browser harness ต้องรักษา Team/Project UOW overrides และเพิ่มของเพื่อนให้ครบก่อน writes ปัญหา B01–B03 ในบันทึกเพื่อนยังไม่ได้แก้แทนเพื่อน
4. Supabaseยังสำหรับอนาคต งานนี้ไม่ย้ายDB/runtime/config และไม่ใช้ฐานข้อมูลอื่น
5. ยังเหลือออก/ถอดสมาชิก/โอนหัวหน้า API/UI, การรวมงานเพื่อน, multi-session concurrency, fresh install/HTTPS/LAN/UAT/runtime COMMIT ที่ไม่ได้ตรวจรับในรอบนี้

Team updateเสร็จเฉพาะContractนี้ ยังไม่ปิดP09ทั้งแถว คงDone5/20=25%ตามChecklistเดิม ไม่ใช้จำนวนtestsแทนเปอร์เซ็นต์effortหรือความครบของทั้งระบบ ไม่มีCommit/Pushในรอบนี้
