# เตรียม Supabase + Vercel — 2026-11-18

**อนุมัติเผยแพร่แล้ว:** ผู้ใช้เลือก Commit/Push ชุดวันที่18พ.ย.ไป `origin/feature/team-integration` หลัง Auth cloud rollback21ผ่าน ข้อความยังไม่Commit/Pushใน snapshot ด้านล่างเป็นประวัติก่อนอนุมัติ ไม่ใช่การรับรองว่าDeployแล้ว ตรวจสถานะ/hashจริงจากGitและผลในแชท รวม [Frontend Vercel template](../../frontend/.env.vercel.example) ที่เพิ่มข้อยกเว้นเฉพาะไฟล์ตัวอย่างในfrontend/.gitignore ไม่รวมsecretsจริงหรือข้อมูลDB

ผู้ใช้สั่งทำ Supabase ต่อ โดยจะสร้าง Project Supabase เองและต้องการ Deploy ผ่าน Vercel คง Login เดิมตามข้อยืนยันแบบ1 ไม่ใช้ Supabase Auth/Storage และไม่เปลี่ยน Schema V1

**สถานะ:** ผู้ใช้ติดตั้ง baseline ตามอนุมัติผ่าน SQL Editor, ตั้ง password `project_app` และ private config เองแล้ว **Backend direct limited LOGIN/TLS/Preliminary read-only preflight ผ่านจริง** บนPostgreSQL17.12 ตาม [รายงาน](../database/SUPABASE_CONNECTION_REPORT.md) แก้ startup options ที่ไม่มีผลผ่าน pooler โดยเพิ่ม explicit READ ONLY และ transaction-local timeouts ตามอนุมัติ ยังไม่ทดสอบ cloud business writes/Deploy/Commit/Push และไม่ได้แก้ `.env` ของผู้ใช้เอง

Supabase Dashboard: [Project ที่อนุมัติ](https://supabase.com/dashboard/project/czylcqdmtzztabkcqewn) · Project URL: `https://czylcqdmtzztabkcqewn.supabase.co` ข้อมูลนี้ไม่ใช่ database password หรือ API key

**หลักฐานตามลำดับจากผู้ใช้:** Preflight เป็น database/role=`postgres`, PostgreSQL **17.12**, existing tables/functions/roles=`0`, spms_auth_exists=`false`; รัน `000_roles.sql` ได้ `Success. No rows returned`; รัน `001_bootstrap.sql` ได้ภาพ PASS และ counts ตามด้านบน ไม่รัน bootstrap ซ้ำบน objects ที่มีแล้ว ทั้งนี้เครื่องเดิมใช้18.6 ผล local ไม่ใช่ proof บน17.12

**ขั้นเชื่อมต่อที่ผ่านแล้ว:** ผู้ใช้ระบุ Session host `aws-1-ap-northeast-1.pooler.supabase.com:5432`, ตั้ง `project_app` password แบบซ่อน และ private config เอง เครื่องมือตรวจ ref/host/userก่อนconnect แล้วได้PreflightPASSด้วย `session_user=current_user=project_app`/TLSจริง ไม่ส่ง secrets ในแชท ต่อมา [Auth HTTP/ASGI rollback21/21ผ่านแล้ว](../database/SUPABASE_AUTH_SMOKE_REPORT.md) พร้อมbaselineคืนและcredentialจำลองไม่ค้าง ขั้นถัดไปคือ Vercel HTTPS/proxy validation และbusinessworkflowอื่น แยกจากstructural/Auth checks

## 1. สร้าง Supabase Project

1. เจ้าของบัญชีเปิด [Supabase Dashboard](https://supabase.com/dashboard) แล้วสร้าง **Project ทดสอบใหม่** เช่น `spms-team-test` เลือก organization/region/แผนที่ต้องการเอง ตรวจค่าใช้จ่ายก่อนยืนยัน
2. ตั้ง database password ส่วนตัว เก็บในเครื่อง/secret manager ไม่ใส่ Git หรือแชท รหัสนี้เป็นของผู้ดูแล PostgreSQL ไม่ใช่รหัส Login นักศึกษาหรือรหัส `project_app`
3. ปิด Data API เพราะ V1 กรองสิทธิ์แถวผ่าน FastAPI ไม่ใช้ frontend เรียกตาราง/RPC โดยตรง ห้ามเปลี่ยน RLS/Schema เพื่อข้าม FastAPI
4. แจ้งเฉพาะ Project URL `https://<project-ref>.supabase.co` และยืนยันว่าไม่มีตาราง/ข้อมูลแอปเดิม ไม่ต้องส่ง password, API key หรือ PostgreSQL URL ที่มี password
5. ตรวจ PostgreSQL version/managed roles และ review [SQL draft](../../database/supabase/README.md) บนปลายทางที่ระบุ ก่อนอนุมัติ/ติดตั้ง Roles/Schema ถาวร ตาม [Supabase Setup](../team/SUPABASE_SETUP.md)

ไม่มีการย้ายบัญชี/ข้อมูลทดสอบในเครื่องไป cloud อัตโนมัติ โครงการของเพื่อนที่ไม่ได้ระบุ URL/เจ้าของ/ข้อมูลเดิมยังเป็น Not Verified

## 2. การวาง Frontend และ Backend — ยืนยันแล้ว

Vercel สอง Projects จาก repo เดียว Frontend ใช้ Next.js และ Backend ใช้ FastAPI โดย browser เรียก `/api/v1/...` ผ่านโดเมน Frontend แล้ว proxy ไป Backend Cookie จึงอยู่ที่ host ที่เปิดเว็บและ frontend อ่าน CSRF cookie ได้

| ค่า | Backend Project | Frontend Project |
|---|---|---|
| Root Directory | repository root (`.`) **ไม่ใช่ backend/** เพราะใช้ imports `backend.*` | `frontend` |
| Framework | FastAPI ตาม root `vercel.json` | Next.js ตาม `frontend/vercel.json` |
| Runtime | Python3.12 ตาม `pyproject.toml`; dependencies ตรง requirements เดิม | เลือก Node22.x (>=22.13.0) ตาม engine ของ transitive dependencies; เครื่องปัจจุบันNode20.10มี engine warning แม้ build/lint ผ่าน |
| Entrypoint | `backend.main:app` ตาม `tool.vercel.entrypoint` | Next.js App Router เดิม |
| HTTPS config | `AUTH_WEB_ORIGIN=https://<frontend-domain>` | `SPMS_BACKEND_ORIGIN=https://<backend-domain>` |
| Database | `AUTH_DB_TARGET=supabase_test`, `SUPABASE_PROJECT_REF=czylcqdmtzztabkcqewn`, `AUTH_DATABASE_URL` ของ project_app พร้อมTLS | **ไม่มี DB URL/password/API keys** |
| Browser API base | — | เอา `NEXT_PUBLIC_API_BASE_URL` ออก; config ใส่ empty string ให้ client เรียก `/api/v1` |

ใช้ canonical HTTPS production domains ที่กำหนดไว้ให้สองฝั่งตรงกัน ไม่ใช้ hashed Preview URLs หรือ wildcard origins; ยังไม่สร้าง Vercel Projects หรือรู้ domains จริงในรอบนี้

โค้ด config/patch รอบนี้ยังไม่ได้ Commit/Push จึงยังไม่มีใน remote commit `8167187` ต้องเผยแพร่ชุดที่ตรวจแล้วตามอนุมัติใหม่ก่อน Deploy จาก GitHub ห้าม Deploy จาก remote เก่าแล้วคาดว่าจะมี config เหล่านี้ และห้ามรัน migration/seed เป็น Build Command

การตั้ง `NEXT_PUBLIC_API_BASE_URL` ให้ชี้ Backend อีกโดเมนโดยตรงเพียงอย่างเดียว **ยังไม่พอ** สำหรับ client ปัจจุบัน เพราะ frontend อ่าน `spms_csrf` จาก `document.cookie` ของหน้าเว็บ โดเมน Backend ต่างกันจะไม่เปิด Cookie นั้นให้หน้าเว็บอ่าน ห้ามแก้เป็น token ใน localStorage หรือปิด CSRF เพื่อให้ใช้งานได้

`frontend/config/deployment.mjs` ให้ Next.js rewrite เฉพาะ `/api/v1/:path*` ไป Backend ที่ระบุ พร้อม no-store/CDN no-store และปิด external-rewrite caching; ไม่รับ insecure/wildcard/credentials ใน URL และไม่ยอม direct browser API override ข้าม proxy ขณะใช้โหมดนี้

`SPMS_LOCAL_API_PROXY=1` ใช้ได้เฉพาะการทดสอบ localhost/127.0.0.1 HTTP บนเครื่องที่ไม่ใช่ Vercel ไม่ใช่ตัวเลือก deployment และไม่ส่งค่านี้ขึ้น Vercel; default local direct API เดิมไม่เปลี่ยน

## 3. ส่วน HTTPS ที่เตรียมแล้ว

Backend อ่าน environment variable `AUTH_WEB_ORIGIN` เช่น `https://your-frontend-project.vercel.app` โดยต้องเป็น origin HTTPS เพียงค่าเดียว ไม่มี path/wildcard/query/user/password

- เปิด `Secure` ให้ session/CSRF cookies อัตโนมัติ และยังเป็น host-only, SameSite=Lax, session HttpOnly, อายุ8ชั่วโมงตามเดิม
- CORS และการตรวจ Origin อนุญาตเฉพาะ origin นี้ ไม่เติม localhost หรือ preview wildcard ในโหมดHTTPS
- ถ้า Backend อยู่บน Vercel (`VERCEL=1`) แต่ไม่ตั้ง `AUTH_WEB_ORIGIN` จะหยุดเริ่ม app แทนการใช้ HTTP-localhost policy บนเว็บจริง
- ค่าต้องอยู่ใน **environment ของ Backend** ไม่ใช่ `NEXT_PUBLIC_*` และไม่อ่านจากไฟล์ `.env.https.example` หรือ `.env` โดยอัตโนมัติ ดู [template](../../backend/.env.https.example)
- Local เดิมที่ไม่ระบุค่าเหล่านี้ยังใช้ localhost HTTP policy ตามเดิม

ค่าฐานข้อมูลใช้ [`.env.supabase.example`](../../backend/.env.supabase.example) เฉพาะ Backend: `AUTH_DB_TARGET=supabase_test`, `SUPABASE_PROJECT_REF`, `AUTH_DATABASE_URL` ของ `project_app` พร้อมTLS หลังตรวจ baselineจริงแล้ว ปัจจุบันรองรับ Direct/Session pooler5432 ไม่รองรับ Transaction pooler6543 ห้ามนำ admin URL/API keys ใส่ Frontend

## 4. สิ่งที่ยังต้องทำก่อน Deploy

- สร้าง/ระบุ Vercel Projects และ canonical domains ที่ใช้จริงตาม topology ที่ยืนยันแล้ว
- Bootstrap และ Backend restricted-role read-only connection ผ่านแล้ว ยังต้องทดสอบ cloud write workflow แบบROLLBACK และสร้าง/ตรวจบัญชีทดสอบตามขอบเขตที่ตกลง
- Entrypoint/dependency/config/proxy เตรียมแล้ว ต้องทดสอบบน Vercel จริง รวม Cookie/Origin/headers และ deployment protection ของ Backend ที่อาจคืนหน้า Login ของผู้ให้บริการแทน JSON ห้ามข้าม safety barrier หรือแชร์ bypass secret ใน browser
- ตรวจ Python/runtime/binary dependencies บน Linux และ file upload/download ที่ขอบขนาด V1: ไฟล์สูงสุด4,000,000 bytes แต่ยังมี multipart/headers/platform limits ไม่ถือว่าทดสอบผ่านจาก local อย่างเดียว
- ป้องกัน Preview/Build ต่อ DB กลางหรือรัน installer/seed โดยไม่ตั้งใจ ไม่รัน migration ระหว่าง build/import และไม่เปิด broad wildcard origins
- ตรวจ Supabase แบบอ่านอย่างเดียว แล้วใช้ cloud test suite แยกแบบ ROLLBACK ที่ตรวจ target ก่อนเขียน ไม่ชี้ local installers/Browser fixture/concurrency manifests ไป cloud
- ทดสอบบน HTTPS จริง: Login → refresh/me → สร้างทีม → CSRF writes → Logout รวม wrong Origin, expired/revoked cookie และสิทธิ์ทุกบทบาท
- ยังต้องยืนยันการสร้างบัญชีทดสอบ/ข้อมูลกลางและขอบเขตเขียนถาวรก่อนเปิดใช้งานร่วมกัน

เอกสารอ้างอิง: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Function payload limits](https://vercel.com/docs/functions/limitations), [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres), [Data API security](https://supabase.com/docs/guides/api/securing-your-api)

## หลักฐานรอบเตรียม

| รายการ | ผล |
|---|---|
| Full local Backend regression | **613 PASS / 41 modules**, 87.662s พร้อม ROLLBACK คืน full public values/metadata/owners/ACL/Auth counts (ไม่รวม sequence) |
| HTTPS settings/cookies/CSRF/CORS | 10 tests ใหม่อยู่ใน613; synthetic repository ไม่มีการต่อ cloud |
| Deployment manifest | 3 PASS แยกจาก613 ตรวจ dependency pins/entrypoint/runtime/bundle exclusions |
| รวม focused Python safeguards หลัง manifest | 54 PASS (รวม tests ที่อยู่ใน613แล้ว ไม่บวกซ้ำ) |
| Frontend proxy config | 6/6 PASS ด้วย Node test runner ไม่ใช่ Browser หรือ live proxy |
| Next security patch | ผู้ใช้อนุมัติ `next` และ `eslint-config-next` 16.4.4 → **16.4.6** พร้อม lockfile แล้ว |
| Production build / TypeScript / ESLint | PASS หลัง patch; build เป็น local test-proxy profile ไม่ใช่ cloud deployment |
| npm production audit | `npm audit --omit=dev` พบ0; full npm audit หลัง install ยังแจ้ง15รายการ (6moderate/9high) ใน tooling/transitive development chains ไม่ใช้ force/downgradeเพื่อทำตัวเลขเป็น0 |
| Live local proxy Browser | **Not Run** automatic approval review ปฏิเสธการเปิด Frontend3012 โดยระบุเพียง `blocked by policy`; ปิด Backend8012ของชุดทดสอบแล้ว ตรวจ digest baseline ก่อน/หลังตรงกัน ไม่ปิดเว็บทดลองของผู้ใช้ |
| Supabase installation | **User-reported PASS**: Preflight17.12/empty, roles Success, bootstrap screenshot14/28/52/24/2; ผู้ใช้รันเองผ่าน SQL Editor ตามอนุมัติ ไม่มีการตรวจ direct app ใหม่จากเครื่องมือ |
| Supabase preliminary Backend connection | **PASS จริง** limited LOGIN/TLS/14tables/86columns/28FKs/52functions/24triggers/2Auth และ selected ACL; transaction factories10/10ได้READ ONLY/15s/3sหลังแก้ตามอนุมัติ ดู[รายงาน](../database/SUPABASE_CONNECTION_REPORT.md) |
| Supabase Auth write API rollback | **21/21 PASS** signup/hash/Login/session/Me/relogin/CSRF/Logout/forcedconstraints ผ่านHTTP/ASGIและcloudPGจริง คืนbaseline/credentialจำลองไม่ค้าง [รายงาน](../database/SUPABASE_AUTH_SMOKE_REPORT.md) |
| Supabase business/HTTPS cloud workflow | **Not Run** สำหรับTeam/Project/Submission/Milestone/Task/Vote/Evaluation และBrowser/proxy/Vercel/concurrency ไม่ขยายผลAuth21เป็นทุกเส้นทาง |

Next.js16.4.4 ถูก Build หยุดด้วย security warning และตรวจยืนยันด้วย npm audit/ประกาศทางการก่อนขออนุมัติ patch: [GHSA-mfr8-8qww-v76h](https://github.com/vercel/next.js/security/advisories/GHSA-mfr8-8qww-v76h), [GHSA-vc7v-qv4w-wrv8](https://github.com/vercel/next.js/security/advisories/GHSA-vc7v-qv4w-wrv8), [16.4.6 release](https://github.com/vercel/next.js/releases/tag/v16.4.6) ไม่ใช้คำสั่ง retry เพื่อข้าม warning

การตรวจ Dashboard อัตโนมัติทำไม่ได้: Windows Computer Use native pipe unavailable หลัง recovery ตามคู่มือ ผู้ใช้เลือกดำเนิน SQL Editor เองแทน ไม่มีการส่ง credentials ผ่านแชทหรือดึงข้อมูลจากบัญชีที่ไม่ได้เปิดให้
