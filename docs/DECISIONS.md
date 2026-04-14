# Decision Log

> บันทึกการตัดสินใจทางเทคนิคที่สำคัญ
> ป้องกัน agent ตัวถัดไปตัดสินใจซ้ำหรือขัดแย้ง

## Format

```
### DEC-NNN: Title
- **Date:** YYYY-MM-DD
- **Status:** accepted / superseded / deprecated
- **Context:** ทำไมต้องตัดสินใจเรื่องนี้
- **Decision:** เลือกอะไร
- **Alternatives:** ทางเลือกอื่นที่พิจารณาแล้วไม่เลือก
- **Consequences:** ผลกระทบที่ต้องรู้
```

---

### DEC-003: AccountFlowGraph ใช้ in-memory aggregation แทน CSV fetch
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** AccountFlowGraph เดิมใช้ `fetchAggregatedEdges()` async fetch CSV จาก `/api/download/{account}/processed/aggregated_edges.csv` แล้ว fallback เป็น `aggregateFromRows()` — ซับซ้อนและ CSV ไม่มีข้อมูลเวลาสำหรับ hour filter
- **Decision:** ลบ async CSV fetch ทั้งหมด ใช้ `useMemo(() => aggregateFromRows(rows, account))` ตรง ๆ
- **Alternatives:** ปรับ CSV ให้มี datetime column — เพิ่มงาน pipeline, ไม่คุ้ม
- **Consequences:** ไม่ต้อง async state management, ลดโค้ด ~90 บรรทัด, hour filter ทำงานได้ถูกต้องเสมอ

### DEC-002: SPNI integration ใช้ dedicated router ไม่ใช่ existing endpoints
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** SPNI ต้องการข้อมูล accounts + transactions + entities ในครั้งเดียว แต่ BSIE endpoints ปัจจุบันกระจายอยู่ใน 5+ routers
- **Decision:** สร้าง `routers/spni.py` + `services/spni_service.py` แยกต่างหาก กับ endpoint `/api/spni/export` ที่รวมข้อมูลทั้ง 3 ประเภท
- **Alternatives:** (1) ให้ SPNI เรียกหลาย endpoints — ซับซ้อนฝั่ง adapter, consistency risk (2) เพิ่ม query param `format=spni` ใน existing endpoints — pollutes existing API
- **Consequences:** SPNI adapter เรียกแค่ endpoint เดียว, BSIE API surface เพิ่ม 4 endpoints, ต้อง maintain ทั้ง router เดิม + SPNI router

### DEC-001: ลบ .csv ออกจาก upload allowlist
- **Date:** 2026-04-14
- **Status:** accepted
- **Context:** CSV ไม่มี structure เพียงพอให้ bank_detector ทำงาน — ไม่มี headers, keywords, sheet structure ที่จะ auto-detect bank ได้
- **Decision:** ลบ `.csv` จาก `ALLOWED_EXTENSIONS` ใน `routers/ingestion.py`
- **Alternatives:** เพิ่ม CSV parser ที่ต้องให้ user ระบุ bank เอง — เพิ่มงาน UX, ไม่มี use case จริง
- **Consequences:** User ต้องแปลง CSV เป็น Excel ก่อน upload
