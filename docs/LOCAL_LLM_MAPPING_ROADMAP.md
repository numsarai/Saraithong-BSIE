# Local LLM + Mapping Roadmap

เอกสารนี้สรุปแผนงานสำหรับยกระดับ BSIE ใน 3 ด้านหลัก:

1. mapping / auto-detect ให้แข็งแรงขึ้น
2. learning ของ bank template variants ให้แชร์ได้อย่างปลอดภัย
3. ใช้ Local LLM เป็นตัวช่วยเฉพาะกรณี ambiguous โดยไม่ทำลาย evidentiary integrity

วันที่สรุปแผน: 2026-04-24

## Objectives

- ลดงาน manual mapping ซ้ำ ๆ โดยไม่ลดความน่าเชื่อถือของหลักฐาน
- รองรับ Excel template ของธนาคารเดิมที่เปลี่ยน layout หรือ column naming
- ให้ระบบเรียนรู้รูปแบบใหม่ได้แบบ shared แต่มี guardrail
- ใช้ Local LLM กับงานที่คุ้มที่สุด: mapping assist, ambiguity resolution, investigator copilot

## Locked Decisions

- ผู้ใช้ทุกคนสามารถ `confirm mapping สำหรับรอบงานปัจจุบัน` ได้
- การเรียนรู้ถูกแชร์ทั้งระบบ แต่ไม่ควร publish เป็น trusted template ทันทีจากการยืนยันครั้งเดียว
- โฟกัสหลักระยะแรกคือ `Excel`
- `template ใหม่` ไม่ควร auto-pass
- auto-pass เปิดได้เฉพาะ `trusted Excel variants`
- เครื่องเป้าหมายตอนนี้คือ `MacBook Pro 16" M2 Max RAM 32GB`

## Guiding Principles

- deterministic first
- LLM assist only on ambiguity
- human confirmation required
- learn only after successful confirmation
- variant-based memory, not single-template-per-bank
- audit trail for every detection / suggestion / confirmation / promotion

## Target Architecture

### Layer 1 — Deterministic Detection

ใช้ของเดิมเป็นแกน:

- `core/bank_detector.py`
- `core/column_detector.py`
- `core/mapping_memory.py`
- `core/bank_memory.py`

ระบบต้องพยายาม detect และ map ให้ได้ก่อนด้วย logic แบบ explicit

### Layer 2 — Review + Safe Confirmation

ผู้ใช้ยืนยัน:

- selected bank
- confirmed mapping
- header row / sheet context

แต่ backend ต้อง validate ก่อน save ทุกครั้ง

### Layer 3 — Variant Learning

เปลี่ยนจากแนวคิด:

- 1 bank = 1 config

ไปเป็น:

- 1 bank = many template variants

แต่ละ variant ควรมีข้อมูลอย่างน้อย:

- bank key
- source type (`excel`, `pdf_ocr`, `image_ocr`, etc.)
- sheet name
- header row
- ordered column signature
- set signature
- layout type
- confirmed mapping
- usage count
- correction count
- trust state

### Layer 4 — Local LLM Assist

เรียก Local LLM เฉพาะเมื่อ:

- bank confidence ต่ำ
- required mapping ไม่ครบ
- profile / fingerprint ไม่ match
- OCR header noisy
- ธนาคารเดิมแต่รูปแบบใหม่

LLM ต้องตอบเป็น structured JSON เท่านั้น

## Variant Lifecycle

### 1. Candidate

- เกิดจาก user confirm mapping
- ยังใช้ซ้ำได้แบบ suggestion
- ยังห้าม auto-pass

### 2. Verified

- ยืนยันซ้ำหลายครั้ง
- parse สำเร็จ
- sanity checks ผ่าน

### 3. Trusted

- verified หลายครั้งจากหลายผู้ใช้
- ไม่มี correction rate สูงผิดปกติ
- อนุญาต auto-pass ได้

## Auto-pass Policy

### Never auto-pass

- template ใหม่
- bank ambiguous
- required fields ไม่ครบ
- OCR / image-derived mapping
- parse preview ไม่ผ่าน sanity checks

### Allow auto-pass only when all conditions pass

- file type เป็น Excel
- matched trusted variant
- bank detection confidence สูงมาก
- mapping required fields ครบ
- dry-run preview ผ่าน
- ไม่พบ date / amount / balance anomalies จาก mapping
- variant นี้เคยถูกยืนยันอย่างน้อย 3 ครั้ง
- confirmation มาจากอย่างน้อย 2 ผู้ใช้

## Local Model Recommendations

สำหรับเครื่องปัจจุบัน แนะนำ baseline ดังนี้:

- text reasoning / Thai + JSON / mapping assist:
  - `qwen2.5:14b`
- PDF / image / document understanding:
  - `qwen2.5vl:7b`
- fast fallback / lightweight on-device:
  - `gemma4:e4b`

หมายเหตุ:

- หลีกเลี่ยง `:latest` ใน production-like flows เพื่อให้ reproducible
- ควรแยก env ระหว่าง text model และ vision model

ตัวแปรแวดล้อมที่อยากได้ในอนาคต:

- `OLLAMA_TEXT_MODEL`
- `OLLAMA_VISION_MODEL`
- `OLLAMA_FAST_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_TIMEOUT`

## Phased Roadmap

### Phase 1 — Harden Current Mapping Flow

สถานะ: implemented บางส่วนเมื่อ 2026-04-24

เป้าหมาย:

- ทำให้ manual mapping ปลอดภัยและ audit ได้ดีขึ้น

งานหลัก:

- [x] เพิ่ม backend validation ใน `/api/mapping/confirm`
- [x] กัน duplicate field usage / conflicting column assignments
- [x] เพิ่ม dry-run parse preview ก่อน save learning
- [x] แยกผลลัพธ์ `confirm for this run` ออกจาก `promote to shared variant`
- [x] จำกัดสิทธิ์การ promote shared learning แบบ opt-in + named reviewer
- [ ] เชื่อม variant lifecycle จริงใน Phase 2

ไฟล์หลัก:

- `routers/ingestion.py`
- `persistence/schemas.py`
- `utils/app_helpers.py`
- `frontend/src/components/steps/Step2Map.tsx`

### Phase 2 — Introduce Template Variants

สถานะ: backend persistence + gated upload/bulk suggestion wiring + frontend review UI implemented เมื่อ 2026-04-24

เป้าหมาย:

- รองรับธนาคารเดิมที่มีหลาย export formats อย่างเป็นระบบ

งานหลัก:

- [x] ออกแบบ schema / persistence สำหรับ variant
- [x] เก็บ ordered signature + set signature + layout metadata
- [x] เพิ่ม trust state: `candidate`, `verified`, `trusted`
- [x] รองรับ correction count / promotion rule แบบ backend service
- [x] เพิ่ม API สำหรับ list/promote variants
- [x] เชื่อม variants เข้ากับ upload/bulk suggestion path แบบ gated
- [x] เพิ่ม frontend admin/review UI สำหรับ variant promotion

หมายเหตุ:

- Upload/redetect ใช้ variant ได้เป็น suggestion-only เมื่อ bank detection stable และ mapping validate ผ่าน
- Bulk intake ใช้เฉพาะ trusted Excel variants เพราะเป็น flow ที่ไม่มี per-file analyst confirmation
- Bank Manager มี per-bank Template Variants panel สำหรับตรวจและโปรโมต `candidate -> verified -> trusted`
- ทุก variant match ยังส่ง `auto_pass_eligible=false`; ยังไม่ได้เปิด auto-pass จริง

ไฟล์หลัก:

- persistence models + migrations
- `core/mapping_memory.py`
- `core/bank_memory.py`
- ingestion / bulk processor call sites

### Phase 3 — LLM-Assisted Detect / Mapping

เป้าหมาย:

- ลดงาน manual เฉพาะเคส ambiguous

งานหลัก:

- เพิ่ม endpoint / service สำหรับ mapping-assist
- prompt ให้ส่งเฉพาะ safe structured context:
  - header candidates
  - sample rows
  - bank candidates
  - layout clues
- บังคับ structured JSON output
- แสดงเหตุผลใน UI

ไฟล์หลัก:

- `services/llm_service.py`
- `routers/llm.py` หรือ router ใหม่สำหรับ mapping-assist
- `frontend/src/components/steps/Step2Map.tsx`

### Phase 4 — Investigation Copilot

เป้าหมาย:

- ขยาย Local LLM ไปฝั่ง analyst workflow

งานหลัก:

- lock LLM scope ให้ผูกกับ evidence set / parser run
- ช่วยสรุปบัญชี
- อธิบาย alerts
- ร่างรายงาน
- review assistance
- ภายหลังย้าย classification path ให้ local-first

### Phase 5 — Auto-pass Rollout

เป้าหมาย:

- เปิดใช้แบบระวังและวัดผลได้

งานหลัก:

- เปิดเฉพาะ Excel trusted variants
- เพิ่ม metrics และ rollback conditions
- monitor correction rate

## Metrics

ควรวัดอย่างน้อย:

- bank detect accuracy
- required-field mapping accuracy
- average time to usable mapping
- analyst correction rate
- false promotion rate
- auto-pass rollback rate

## Suggested First Implementation Sprint

### Sprint Goal

ทำ `Phase 1` ให้เสร็จแบบใช้งานได้จริงก่อน

### Deliverables

- backend validation ของ mapping confirmation
- dry-run preview API / logic
- UI เตือน conflict ชัดขึ้น
- handoff/test coverage สำหรับ mapping validation

### Nice-to-have

- skeleton model for template variant persistence
- env split สำหรับ text/vision LLM models

## Session Starter Checklist

เปิด session ใหม่แล้วให้ทำตามนี้:

1. อ่าน `docs/HANDOFF.md`
2. อ่าน `docs/DECISIONS.md`
3. อ่านเอกสารนี้ `docs/LOCAL_LLM_MAPPING_ROADMAP.md`
4. ตรวจ `routers/ingestion.py`, `persistence/schemas.py`, `frontend/src/components/steps/Step2Map.tsx`
5. ออกแบบ validation rules สำหรับ `/api/mapping/confirm`
6. เขียน tests ก่อนหรือพร้อม implementation

## Explicit Non-goals For The First Sprint

- ยังไม่เปิด auto-pass จริง
- ยังไม่ให้ LLM save template เอง
- ยังไม่แก้ classification pipeline ให้ใช้ Ollama แทน OpenAI path
- ยังไม่ขยายไป PDF/image-heavy learning path เป็น priority หลัก
