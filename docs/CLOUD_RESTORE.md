# Cloud Restore Guide

เอกสารนี้เก็บบริบทสำหรับกรณีที่ต้องการกลับไปใช้ deployment แบบ cloud หลังจากที่รีโปถูกปรับกลับมาเป็น local-only เมื่อวันที่ 2026-04-23

## Status

- ตอนนี้รีโปทำงานแบบ local-only
- remote resources เดิมยังไม่ได้ถูกลบ
- ถ้าจะกลับไปใช้ cloud อีกครั้ง ให้ใช้เอกสารนี้เป็น checklist หลัก

## Preserved Remote Resources

- Vercel project: `bsie`
- Expected frontend URL: `https://bsie.vercel.app`
- Fly.io app: `bsie-backend`
- Expected backend URL: `https://bsie-backend.fly.dev`
- Supabase project: `bsie-demo`
- Supabase ref: `yehlncpqmfxgfpcrapte`
- Region used previously: `ap-southeast-1` / Singapore

หมายเหตุ:
- secrets จริงไม่ได้เก็บไว้ในรีโป
- ก่อน restore ให้ตรวจใน dashboard/CLI ว่า resources ชุดนี้ยังอยู่และชื่อยังไม่เปลี่ยน

## What Was Removed From The Repo

### Backend/runtime

- external Postgres path ผ่าน `BSIE_DATABASE_URL`
- Supabase JWT verification และ user sync
- cloud-specific CORS config สำหรับ Vercel/Fly

### Frontend/runtime

- Supabase client
- login gate และ Google SSO login screen
- Bearer token injection ใน `frontend/src/api.ts`
- Vercel-specific build output switch

### Deploy/config files

- `vercel.json`
- `.vercelignore`
- `Dockerfile`
- `fly.toml`
- `render.yaml`
- `requirements-cloud.txt`
- `frontend/.env.example`
- `frontend/.env.production`

## Repo Changes Needed To Restore Cloud

### 1. Backend database runtime

คืน logic ใน `persistence/base.py` ให้รองรับ:

- `BSIE_DATABASE_URL`
- rewrite `postgres://` -> `postgresql://`
- dynamic `IS_SQLITE`
- Postgres engine config:
  - `pool_pre_ping=True`
  - `pool_size=5`
  - `max_overflow=10`
  - `pool_recycle=3600`
- skip `Base.metadata.create_all()` และ `SQLModel.metadata.create_all()` บน Postgres path

### 2. Backend auth runtime

คืนไฟล์ `services/supabase_auth.py` พร้อมความสามารถต่อไปนี้:

- verify Supabase JWT ผ่าน JWKS
- รองรับ asymmetric keys และ HS256 fallback
- validate `aud=authenticated`
- validate `iss=<supabase-url>/auth/v1`
- upsert local user row จาก `sub`

คืน logic ใน `services/auth_service.py` ให้ dispatch ตาม:

- `BSIE_AUTH_MODE=local`
- `BSIE_AUTH_MODE=supabase`

### 3. Backend app config

คืน logic ใน `app.py` ให้รองรับ:

- `BSIE_CORS_ALLOW_ORIGINS`
- extra allow origin สำหรับ `https://bsie.vercel.app`
- preview regex สำหรับ Vercel deployment URLs

### 4. Frontend auth/runtime

คืนไฟล์:

- `frontend/src/lib/supabase.ts`
- `frontend/src/lib/useAuth.ts`
- `frontend/src/components/Login.tsx`
- `frontend/src/components/LoginGate.tsx`

คืนการแก้ใน:

- `frontend/src/main.tsx`
  - wrap `<App />` ด้วย `<LoginGate>`
- `frontend/src/api.ts`
  - inject `Authorization: Bearer <jwt>`
  - ใช้ `VITE_API_BASE_URL`
- `frontend/package.json`
  - add `@supabase/supabase-js`
- `frontend/vite.config.ts`
  - `outDir = 'dist'` เมื่อ `VERCEL=1`
  - `outDir = '../static/dist'` ใน local mode

### 5. Deployment files

คืนไฟล์ต่อไปนี้ตาม stack เดิม:

- `vercel.json`
- `.vercelignore`
- `Dockerfile`
- `fly.toml`
- `render.yaml`
- `requirements-cloud.txt`

## Environment Variables To Prepare

### Backend

- `BSIE_AUTH_REQUIRED=true`
- `BSIE_AUTH_MODE=supabase`
- `BSIE_DATABASE_URL=<supabase postgres url>`
- `BSIE_SUPABASE_URL=https://<project-ref>.supabase.co`
- `BSIE_SUPABASE_JWT_SECRET=<optional only for legacy HS256 projects>`
- `BSIE_JWT_SECRET=<bsie local secret>`
- `BSIE_CORS_ALLOW_ORIGINS=https://bsie.vercel.app`

### Frontend

- `VITE_SUPABASE_URL=https://<project-ref>.supabase.co`
- `VITE_SUPABASE_ANON_KEY=<supabase publishable/anon key>`
- `VITE_API_BASE_URL=https://bsie-backend.fly.dev`

## Deployment Shape Used Previously

### Frontend

- Host: Vercel
- Build command: `cd frontend && npm install && npm run build`
- Output directory: `frontend/dist`
- SPA rewrite to `/index.html`

### Backend

- Host: Fly.io
- Container from `Dockerfile`
- Auth required
- Port used on Fly: `8080`
- Health check path: `/health`

### Database/Auth

- Supabase Postgres
- Supabase Auth with Google OAuth
- invite-only model used previously

## Validation Checklist After Restore

1. Backend `/health` returns `200`
2. Backend `/api/spni/health` returns `401` when unauthenticated
3. Frontend loads from Vercel URL
4. Login flow redirects through Supabase Google auth successfully
5. Backend accepts Supabase Bearer token
6. `pytest tests/` still passes in local mode
7. `npm test` still passes in frontend

## Operational Warnings

- secrets เดิมไม่ได้ถูกเก็บไว้ในรีโป อาจต้อง re-enter จาก dashboard/CLI
- remote resources อาจยังมีอยู่ แต่ config ฝั่ง dashboard อาจ drift ไปจากตอนเดิม
- cloud image เดิมตัด `easyocr` ออกเพื่อลดขนาด image
- ถ้าจะกลับไปใช้ cloud ควรทำบน branch แยกจาก local-only line เพื่อให้เปรียบเทียบ diff ง่าย

## Recommended Restore Workflow

1. สร้าง branch ใหม่สำหรับ cloud reactivation
2. คืน runtime/auth/deploy files ตาม checklist นี้
3. เติม env/secrets จาก dashboard
4. ทดสอบ local ก่อน deploy
5. deploy backend ก่อน
6. deploy frontend หลัง backend URL พร้อม
7. verify login + API flow แบบ end-to-end
