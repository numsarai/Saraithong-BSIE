"""
generate_pptx.py — SPNI/BSIE Comprehensive Presentation
Proportional layout, consistent spacing, 22 slides.
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# ── Colors ──────────────────────────────────────────────────
NAVY    = RGBColor(0x1A, 0x36, 0x5D)
BLUE    = RGBColor(0x2B, 0x6C, 0xB0)
SKY     = RGBColor(0x63, 0xB3, 0xED)
GREEN   = RGBColor(0x38, 0xA1, 0x69)
DGREEN  = RGBColor(0x22, 0x54, 0x3D)
MINT    = RGBColor(0x48, 0xBB, 0x78)
RED     = RGBColor(0xE5, 0x3E, 0x3E)
DRED    = RGBColor(0xC5, 0x30, 0x30)
SALMON  = RGBColor(0xFC, 0x81, 0x81)
ORANGE  = RGBColor(0xDD, 0x6B, 0x20)
GOLD    = RGBColor(0xD6, 0x9E, 0x2E)
LGOLD   = RGBColor(0xEC, 0xC9, 0x4B)
PURPLE  = RGBColor(0x80, 0x5A, 0xD5)
LILAC   = RGBColor(0xD6, 0xBC, 0xFA)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
LGRAY   = RGBColor(0xF7, 0xFA, 0xFC)
MGRAY   = RGBColor(0xED, 0xF2, 0xF7)
DGRAY   = RGBColor(0x2D, 0x37, 0x48)
VDARK   = RGBColor(0x1A, 0x20, 0x2C)
TXT     = RGBColor(0x1A, 0x20, 0x2C)
TXTL    = RGBColor(0x4A, 0x55, 0x68)
SUBTLE  = RGBColor(0xA0, 0xAE, 0xC0)
CDARK   = RGBColor(0x1E, 0x3A, 0x5F)

# ── Layout constants (Widescreen 16:9) ──────────────────────
SW = Inches(13.333)
SH = Inches(7.5)
MX = Inches(0.6)          # horizontal margin
CW = SW - MX * 2          # content width ~12.13"
GAP = Inches(0.25)        # gap between cards
TITLE_Y  = Inches(0.25)
TITLE_H  = Inches(0.65)
BODY_TOP = Inches(1.05)   # content starts below title
BODY_H   = SH - BODY_TOP - Inches(0.3)  # available height

def _half():
    """Width of a half-column card."""
    return (CW - GAP) / 2

def _third():
    """Width of a third-column card."""
    return (CW - GAP * 2) / 3


# ── Drawing primitives ──────────────────────────────────────

def _bg(slide, color):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background()

def _rect(slide, l, t, w, h, color, border=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color
    if border:
        s.line.color.rgb = border; s.line.width = Pt(1.5)
    else:
        s.line.fill.background()
    return s

def _line(slide, l, t, w, h, color):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background()
    return s

def _txt(slide, l, t, w, h, text, sz=14, clr=TXT, bold=False, al=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = al
    r = p.add_run(); r.text = text
    r.font.size = Pt(sz); r.font.color.rgb = clr; r.font.bold = bold
    r.font.name = "Noto Sans Thai"
    return tb

def _title(slide, text, clr=NAVY):
    _txt(slide, MX, TITLE_Y, CW, TITLE_H, text, 28, clr, True, PP_ALIGN.CENTER)

def _sub(slide, text, clr=TXTL, y=None):
    yy = y or (TITLE_Y + Inches(0.55))
    _txt(slide, MX, yy, CW, Inches(0.35), text, 13, clr, False, PP_ALIGN.CENTER)

def _bullets(slide, l, t, w, h, items, sz=13, clr=TXT, bc=GREEN, sp=Pt(4)):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = sp; p.space_before = Pt(0)
        br = p.add_run(); br.text = "● "; br.font.size = Pt(sz - 2)
        br.font.color.rgb = bc; br.font.name = "Noto Sans Thai"
        parts = item.split("**")
        for j, part in enumerate(parts):
            if not part: continue
            r = p.add_run(); r.text = part; r.font.size = Pt(sz)
            r.font.color.rgb = clr; r.font.bold = (j % 2 == 1)
            r.font.name = "Noto Sans Thai"

def _card_title(slide, l, t, w, text, clr=NAVY):
    _txt(slide, l + Inches(0.2), t + Inches(0.12), w - Inches(0.4), Inches(0.35),
         text, 17, clr, True)


# ══════════════════════════════════════════════════════════════
def generate():
    prs = Presentation()
    prs.slide_width = SW; prs.slide_height = SH
    BL = prs.slide_layouts[6]

    def S(color=LGRAY):
        s = prs.slides.add_slide(BL); _bg(s, color); return s

    PAD = Inches(0.2)    # card internal padding
    hw = _half()          # half-width card
    tw = _third()         # third-width card

    # ════════════════════════════════════════════════════════════
    # 1. TITLE
    # ════════════════════════════════════════════════════════════
    s = S(NAVY)
    _txt(s, MX, Inches(0.8), CW, Inches(0.35),
         "สำนักงานตำรวจแห่งชาติ", 12, SUBTLE, False, PP_ALIGN.CENTER)
    _txt(s, MX, Inches(1.5), CW, Inches(0.9),
         "SPNI Platform", 52, WHITE, True, PP_ALIGN.CENTER)
    _txt(s, MX, Inches(2.5), CW, Inches(0.55),
         "Smart Police & National Intelligence", 24, SKY, False, PP_ALIGN.CENTER)
    _line(s, Inches(5.9), Inches(3.3), Inches(1.5), Pt(3), GOLD)
    _txt(s, MX, Inches(3.6), CW, Inches(0.45),
         "โมดูลแรก: BSIE v4.0 — Bank Statement Intelligence Engine", 20, WHITE, False, PP_ALIGN.CENTER)
    _txt(s, MX, Inches(4.2), CW, Inches(0.4),
         "ระบบวิเคราะห์ธุรกรรมทางการเงินอัจฉริยะ สำหรับงานสืบสวนสอบสวน", 16, RGBColor(0xBE,0xE3,0xF8), False, PP_ALIGN.CENTER)
    _txt(s, MX, Inches(5.5), CW, Inches(1.2),
         "เอกสารประกอบการนำเสนอเพื่อของบประมาณระดับประเทศ\n"
         "จัดทำโดย ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง\nเมษายน 2569",
         13, SUBTLE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 2. SPNI VISION
    # ════════════════════════════════════════════════════════════
    s = S(NAVY)
    _title(s, "SPNI Platform — ภาพรวม 4 โมดูล", WHITE)
    _sub(s, "แพลตฟอร์มรวมเครื่องมือสืบสวนสอบสวนสำหรับ สตช. ทั้งประเทศ", RGBColor(0xBE,0xE3,0xF8))

    mods = [
        ("โมดูล 1", "BSIE — การเงิน", "v4.0 พร้อมใช้ ★", MINT),
        ("โมดูล 2", "CDR — โทรศัพท์", "วางแผน", DGRAY),
        ("โมดูล 3", "Social Media Intel", "วางแผน", DGRAY),
        ("โมดูล 4", "CCTV — ภาพ/วีดีโอ", "วางแผน", DGRAY),
    ]
    mw = (CW - GAP * 3) / 4
    for i, (num, name, status, bg_c) in enumerate(mods):
        x = MX + i * (mw + GAP)
        bc = GOLD if i == 0 else RGBColor(0x4A,0x55,0x68)
        _rect(s, x, Inches(1.55), mw, Inches(1.6), bg_c, bc)
        _txt(s, x, Inches(1.6), mw, Inches(0.3), num, 10, SUBTLE, False, PP_ALIGN.CENTER)
        _txt(s, x, Inches(1.9), mw, Inches(0.4), name, 15, WHITE, True, PP_ALIGN.CENTER)
        _txt(s, x, Inches(2.35), mw, Inches(0.3), status, 11, GOLD if i==0 else SUBTLE, False, PP_ALIGN.CENTER)
        if i < 3:
            _txt(s, x + mw + Inches(0.02), Inches(2.0), Inches(0.2), Inches(0.3), "→", 16, SKY, False, PP_ALIGN.CENTER)

    # Shared layer
    _rect(s, MX, Inches(3.45), CW, Inches(1.6), CDARK)
    _txt(s, MX, Inches(3.5), CW, Inches(0.35), "Shared Intelligence Layer", 16, WHITE, True, PP_ALIGN.CENTER)
    tags = [("Entity Registry", GREEN), ("Link Analysis", BLUE), ("Case Mgmt", ORANGE),
            ("Local LLM AI", RED), ("Evidence Chain", PURPLE), ("Regulatory", GOLD)]
    tw_tag = (CW - Inches(0.6) - GAP * 5) / 6
    for i, (name, clr) in enumerate(tags):
        x = MX + Inches(0.3) + i * (tw_tag + GAP)
        _rect(s, x, Inches(4.0), tw_tag, Inches(0.45), clr)
        _txt(s, x, Inches(4.02), tw_tag, Inches(0.42), name, 10, WHITE, True, PP_ALIGN.CENTER)

    _txt(s, MX, Inches(4.65), CW, Inches(0.35),
         "ทุกโมดูลเชื่อมข้อมูลข้ามกัน — บุคคลเดียวกันพบข้ามบัญชี + CDR + Social + CCTV", 12, RGBColor(0xBE,0xE3,0xF8), False, PP_ALIGN.CENTER)

    # Infra
    _rect(s, MX, Inches(5.3), CW, Inches(0.55), DGRAY)
    _txt(s, MX, Inches(5.33), CW, Inches(0.5),
         "Infrastructure: On-Premise Server │ Local LLM (Ollama) │ PostgreSQL │ VPN/HTTPS │ ห้าม Cloud AI", 12, WHITE, False, PP_ALIGN.CENTER)

    _txt(s, MX, Inches(6.2), CW, Inches(0.7),
         "ทำไมเริ่มจาก BSIE?\n"
         "1) คดีการเงินมากที่สุด  2) ข้อมูลมีโครงสร้างชัดเจน  3) เห็นผลเร็ว — 3 วัน→30 นาที  4) พื้นฐานสำหรับโมดูลอื่น  5) ไม่มีเครื่องมือฟรีที่ดีในตลาด",
         11, SUBTLE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 3. PROBLEM
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "ปัญหาการสืบสวนทางการเงินในปัจจุบัน")

    ch = Inches(5.6)
    _rect(s, MX, BODY_TOP, hw, ch, WHITE, RED)
    _card_title(s, MX, BODY_TOP, hw, "ปัญหาที่พบ", RED)
    _bullets(s, MX+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, ch-Inches(0.6), [
        "วิเคราะห์ Statement **ด้วยมือ** ใช้เวลา **3-5 วัน**ต่อคดี",
        "ดูได้**ทีละบัญชี** ไม่เห็น**ภาพรวมเครือข่าย**",
        "ใช้ Excel ธรรมดา ไม่มีเครื่องมือ**วิเคราะห์เฉพาะทาง**",
        "i2 Analyst's Notebook ราคา **500,000+ บาท/license/ปี** ไม่รองรับไทย",
        "ไม่มีมาตรฐาน**รายงาน ปปง.** (STR/CTR)",
        "ไม่มีระบบ**แจ้งเตือนอัตโนมัติ** — พลาดได้ง่าย",
        "ข้อมูลกระจาย**หลาย Excel** ไม่เชื่อมโยงข้ามบัญชี",
        "**ไม่มีเครื่องมือฟรี**ที่ดีสำหรับตำรวจไทย",
    ], bc=RED)

    rx = MX + hw + GAP
    _rect(s, rx, BODY_TOP, hw, ch, WHITE, GREEN)
    _card_title(s, rx, BODY_TOP, hw, "BSIE แก้ได้", GREEN)
    _bullets(s, rx+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, ch-Inches(0.6), [
        "ประมวลผลอัตโนมัติ **ภายใน 30 นาที**",
        "เชื่อมโยงข้ามบัญชี **เห็นเครือข่าย**ทั้งหมด",
        "กราฟเครือข่าย Timeline **แจ้งเตือน 12 รูปแบบ**",
        "มี **mini i2 Analyst's Notebook** ในตัว — **ฟรี**",
        "สร้างรายงาน **PDF/Excel/STR/CTR** ตามมาตรฐาน",
        "**ตรวจจับ 5 รูปแบบฟอกเงิน** FATF อัตโนมัติ",
        "วิเคราะห์ทางสถิติ: **Z-score, IQR, Benford's Law**",
        "ฟรี — **ไม่มีค่า license** รองรับ**ทั้งประเทศ**",
    ])

    # ════════════════════════════════════════════════════════════
    # 4. ARCHITECTURE — System
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "สถาปัตยกรรมระบบ BSIE v4.0", WHITE)

    layer_h = Inches(1.05)
    layer_gap = Inches(0.15)
    y0 = BODY_TOP

    # Frontend
    _rect(s, MX, y0, CW, layer_h, RGBColor(0x20,0x40,0x70))
    _txt(s, MX+PAD, y0+Inches(0.05), Inches(1.5), Inches(0.3), "Frontend", 14, GOLD, True)
    fe = ["React 19", "TypeScript", "Vite", "Tailwind CSS", "Zustand", "Cytoscape.js", "Recharts", "react-i18next"]
    for i, name in enumerate(fe):
        x = MX + Inches(1.8) + i * Inches(1.3)
        _rect(s, x, y0+Inches(0.55), Inches(1.15), Inches(0.35), DGRAY)
        _txt(s, x, y0+Inches(0.56), Inches(1.15), Inches(0.33), name, 9, SKY, True, PP_ALIGN.CENTER)

    # Backend
    y1 = y0 + layer_h + layer_gap
    _rect(s, MX, y1, CW, layer_h, RGBColor(0x15,0x35,0x25))
    _txt(s, MX+PAD, y1+Inches(0.05), Inches(1.5), Inches(0.3), "Backend", 14, MINT, True)
    _txt(s, MX+Inches(1.8), y1+Inches(0.08), Inches(8), Inches(0.3),
         "Python 3.12 │ FastAPI │ 21 Routers │ 34 Services │ 120+ Endpoints", 12, WHITE)
    be = ["ingestion", "search", "graph", "alerts", "fund_flow", "analytics", "reports", "auth", "exports", "workspace"]
    for i, name in enumerate(be):
        x = MX + Inches(1.8) + i * Inches(1.03)
        _rect(s, x, y1+Inches(0.55), Inches(0.9), Inches(0.33), DGRAY)
        _txt(s, x, y1+Inches(0.56), Inches(0.9), Inches(0.31), name, 8, MINT, False, PP_ALIGN.CENTER)

    # Core + Services
    y2 = y1 + layer_h + layer_gap
    _rect(s, MX, y2, hw, layer_h, RGBColor(0x35,0x25,0x15))
    _txt(s, MX+PAD, y2+Inches(0.05), hw-PAD*2, Inches(0.3), "Processing Core — 30 modules", 13, GOLD, True)
    _txt(s, MX+PAD, y2+Inches(0.38), hw-PAD*2, Inches(0.6),
         "bank_detector, column_detector, nlp_engine, normalizer,\n"
         "classifier, link_builder, graph_rules, pdf_loader,\n"
         "image_loader (OCR), exporter, llm_agent ...", 10, WHITE)

    _rect(s, MX+hw+GAP, y2, hw, layer_h, RGBColor(0x25,0x15,0x35))
    _txt(s, MX+hw+GAP+PAD, y2+Inches(0.05), hw-PAD*2, Inches(0.3), "34 Services", 13, LILAC, True)
    _txt(s, MX+hw+GAP+PAD, y2+Inches(0.38), hw-PAD*2, Inches(0.6),
         "alert, anomaly_detection, sna, threat_hunting,\n"
         "fund_flow, auth, regulatory_export, report,\n"
         "insights, case_tapestry, job_queue, audit ...", 10, WHITE)

    # Database + AI
    y3 = y2 + layer_h + layer_gap
    _rect(s, MX, y3, hw, Inches(0.8), RGBColor(0x15,0x25,0x15))
    _txt(s, MX+PAD, y3+Inches(0.05), hw-PAD*2, Inches(0.3), "Database: SQLAlchemy 2 + SQLite WAL", 13, MINT, True)
    _txt(s, MX+PAD, y3+Inches(0.38), hw-PAD*2, Inches(0.35),
         "20 tables │ Alembic migrations │ Optimized pragmas │ → PostgreSQL (Phase 2)", 10, WHITE)

    _rect(s, MX+hw+GAP, y3, hw, Inches(0.8), RGBColor(0x25,0x15,0x15))
    _txt(s, MX+hw+GAP+PAD, y3+Inches(0.05), hw-PAD*2, Inches(0.3), "AI/ML: Local LLM + NLP", 13, SALMON, True)
    _txt(s, MX+hw+GAP+PAD, y3+Inches(0.38), hw-PAD*2, Inches(0.35),
         "EasyOCR (Thai+EN) │ NLP Engine (ชื่อ/เบอร์/บัตร ปชช./PromptPay) │ Ollama", 10, WHITE)

    # ════════════════════════════════════════════════════════════
    # 5. DATABASE ERD
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "ฐานข้อมูล — 20 Tables", WHITE)

    tables = [
        ("FileRecord", "ไฟล์อัพโหลด + SHA-256", GREEN),
        ("ParserRun", "ประวัติการประมวลผล", GREEN),
        ("Account", "บัญชีทุกแห่ง (normalized)", BLUE),
        ("Transaction", "ธุรกรรม 30+ fields", BLUE),
        ("StatementBatch", "ชุดรายการเดินบัญชี", GREEN),
        ("RawImportRow", "ข้อมูลดิบ forensic", GREEN),
        ("Entity", "บุคคล/นิติบุคคล", PURPLE),
        ("AccountEntityLink", "เชื่อม Account↔Entity", PURPLE),
        ("TransactionMatch", "จับคู่ข้ามบัญชี", ORANGE),
        ("Alert", "แจ้งเตือน + severity", RED),
        ("DuplicateGroup", "กลุ่มข้อมูลซ้ำ", ORANGE),
        ("ReviewDecision", "การตัดสินใจ analyst", GOLD),
        ("AuditLog", "Audit Trail ทุก action", GOLD),
        ("ExportJob", "งานส่งออกรายงาน", SKY),
        ("User", "ผู้ใช้ JWT + RBAC", SALMON),
        ("AdminSetting", "ตั้งค่า + Workspace", TXTL),
        ("GraphAnnotation", "บันทึกบน node", LILAC),
        ("CaseTag", "แท็กคดี", MINT),
        ("CaseTagLink", "เชื่อม tag↔วัตถุ", MINT),
        ("MappingProfile", "โปรไฟล์ mapping", GREEN),
    ]
    cw_db = (CW - GAP * 3) / 4
    for i, (name, desc, clr) in enumerate(tables):
        col, row = i % 4, i // 4
        x = MX + col * (cw_db + GAP)
        y = BODY_TOP + row * Inches(1.05)
        _rect(s, x, y, cw_db, Inches(0.85), DGRAY, clr)
        _txt(s, x + Inches(0.12), y + Inches(0.08), cw_db - Inches(0.24), Inches(0.3), name, 12, clr, True)
        _txt(s, x + Inches(0.12), y + Inches(0.42), cw_db - Inches(0.24), Inches(0.35), desc, 10, WHITE)

    _txt(s, MX, Inches(6.5), CW, Inches(0.3),
         "25+ Indexes │ Unique constraints │ Foreign keys │ JSON columns │ Alembic migrations",
         11, SUBTLE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 6. PIPELINE 14 STEPS
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "Processing Pipeline — 14 ขั้นตอน", WHITE)

    steps = [
        ("1", "Load File", "Excel/PDF/Image/OFX", GREEN),
        ("2", "Detect Bank", "8 ธนาคาร auto", GREEN),
        ("3", "Detect Cols", "Fuzzy 3-tier", BLUE),
        ("4", "Load Memory", "Profile ที่จำไว้", BLUE),
        ("5", "Apply Map", "แปลงคอลัมน์", SKY),
        ("6", "Normalize", "วันที่/เงิน/ทิศทาง", SKY),
        ("7", "Parse Acct", "แยกเลข normalize", ORANGE),
        ("8", "Extract Desc", "แยกรายละเอียด", ORANGE),
        ("9", "NLP Enrich", "ชื่อ/เบอร์/ID/PP", PURPLE),
        ("10", "Classify", "IN/OUT/TRANSFER", PURPLE),
        ("11", "Build Links", "from→to accounts", GOLD),
        ("12", "Overrides", "แก้ไขจาก analyst", GOLD),
        ("13", "Build Entity", "สร้าง Entity list", SALMON),
        ("14", "Export", "Account Package", SALMON),
    ]
    sw_step = (CW - GAP * 6) / 7
    for i, (num, name, desc, clr) in enumerate(steps):
        col, row = i % 7, i // 7
        x = MX + col * (sw_step + GAP)
        y = BODY_TOP + row * Inches(2.85)
        sh = Inches(2.5)
        _rect(s, x, y, sw_step, sh, DGRAY, clr)
        _txt(s, x, y+Inches(0.15), sw_step, Inches(0.5), num, 26, clr, True, PP_ALIGN.CENTER)
        _txt(s, x, y+Inches(0.7), sw_step, Inches(0.35), name, 12, WHITE, True, PP_ALIGN.CENTER)
        _txt(s, x+Inches(0.08), y+Inches(1.15), sw_step-Inches(0.16), Inches(1.0), desc, 10, RGBColor(0xBE,0xE3,0xF8), False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 7. DATA INTAKE
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "การนำเข้าข้อมูล — ครบทุกรูปแบบ")

    intake = [
        ("8 ธนาคารไทย Auto-detect", [
            "**SCB** — ไทยพาณิชย์", "**KBANK** — กสิกรไทย",
            "**BBL** — กรุงเทพ", "**KTB** — กรุงไทย",
            "**BAY** — กรุงศรี", "**TTB** — ทหารไทยธนชาต",
            "**GSB** — ออมสิน", "**BAAC** — ธ.ก.ส.",
        ]),
        ("รูปแบบไฟล์ + OCR", [
            "**Excel** (.xlsx / .xls) — ทุกธนาคาร",
            "**PDF** ข้อความ — pdfplumber extraction",
            "**PDF สแกน** — EasyOCR + table reconstruction",
            "**รูปภาพ** (JPG/PNG/BMP) — EasyOCR Thai+EN",
            "**OFX** — ธนาคารออนไลน์",
            "**SHA-256** ตรวจจับไฟล์ซ้ำอัตโนมัติ",
        ]),
        ("Smart Column Mapping", [
            "**3-tier Fuzzy** — exact → alias → fuzzy",
            "**Self-learning** — จำ profile ที่เคย mapping",
            "**Body keywords** — ตรวจจากเนื้อหาไฟล์",
            "**Re-process** — mapping ผิด? ทำใหม่ได้",
            "**NLP** — ชื่อไทย, เบอร์, บัตร ปชช., PromptPay",
        ]),
    ]
    for i, (t_, items) in enumerate(intake):
        x = MX + i * (tw + GAP)
        _rect(s, x, BODY_TOP, tw, Inches(5.8), WHITE)
        _card_title(s, x, BODY_TOP, tw, t_)
        _bullets(s, x+PAD, BODY_TOP+Inches(0.55), tw-PAD*2, Inches(5.0), items, sz=12)

    # ════════════════════════════════════════════════════════════
    # 8. LINK CHART
    # ════════════════════════════════════════════════════════════
    s = S(NAVY)
    _title(s, "กราฟเครือข่าย — mini i2 Analyst's Notebook", WHITE)
    _sub(s, "Link Chart 815 บรรทัด — Interactive Multi-hop Expand ไม่จำกัดความลึก", RGBColor(0xBE,0xE3,0xF8))

    ch = Inches(5.1)
    _rect(s, MX, Inches(1.3), hw, ch, CDARK)
    _card_title(s, MX, Inches(1.3), hw, "Multi-hop Link Chart", GOLD)
    _bullets(s, MX+PAD, Inches(1.85), hw-PAD*2, ch-Inches(0.7), [
        "กดขยายเครือข่าย**ทีละชั้น ไม่จำกัดความลึก**",
        "**5 Layout**: Circle, Spread, Compact, Hierarchy, Peacock",
        "**Conditional Formatting** — ขนาด node ตามยอดเงิน",
        "สี border ตาม**ระดับความเสี่ยง**จาก alert",
        "**Edge labels** แสดง/ซ่อนยอดเงินบน edge",
        "**Pin / Hide / Multi-select** จัดระเบียบกราฟ",
        "**Focus History** — ดูประวัติการสำรวจ node",
        "**Export PNG** สำหรับใช้ในรายงาน",
    ], clr=WHITE, bc=GOLD, sz=12)

    rx = MX + hw + GAP
    _rect(s, rx, Inches(1.3), hw, ch, CDARK)
    _card_title(s, rx, Inches(1.3), hw, "SNA + Path Tracing", GOLD)
    _bullets(s, rx+PAD, Inches(1.85), hw-PAD*2, ch-Inches(0.7), [
        "**Degree Centrality** — บัญชีเชื่อมต่อมากสุด",
        "**Betweenness** — บัญชี**ตัวกลาง** (broker)",
        "**Closeness** — เข้าถึงทุกจุดเร็วสุด",
        "**BFS Path Finder** — ตามเงิน A→B→C→D **4 ทอด**",
        "**Graph Annotations** — จดบันทึกบน node ได้",
        "**Tags**: ผู้ต้องสงสัย, พยาน, เหยื่อ, ตรวจสอบเพิ่ม",
        "**Workspace** — บันทึก/โหลด chart state",
        "**Entity Profile** — หน้ารวมข้อมูลบุคคล/บัญชี",
    ], clr=WHITE, bc=GOLD, sz=12)

    # ════════════════════════════════════════════════════════════
    # 9. VISUALIZATION
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "การแสดงผล — Timeline, Heatmap, Dashboard")

    viz = [
        ("Timeline Chart", BLUE, [
            "**Recharts** — Bar + Dot mode",
            "Granularity: **วัน / สัปดาห์ / เดือน**",
            "ดูรูปแบบธุรกรรมตามเวลา",
            "**ตรวจจับช่วงเวลาผิดปกติ**",
        ]),
        ("Time Wheel (Heatmap)", PURPLE, [
            "**Custom SVG** — Hour × Day",
            "24 ชม. × 7 วัน = **168 ช่อง**",
            "สีตามความถี่ธุรกรรม",
            "**ตรวจจับเวลาผิดปกติ** (ตี 2-5)",
        ]),
        ("Dashboard", GREEN, [
            "**สรุปภาพรวม** — สถิติ, เงินเข้า/ออก",
            "**Recent Activity** — ธุรกรรมล่าสุด",
            "**Top Accounts** — บัญชียอดสูงสุด",
            "**Code-split** — React.lazy + Suspense",
        ]),
    ]
    for i, (t_, clr, items) in enumerate(viz):
        x = MX + i * (tw + GAP)
        _rect(s, x, BODY_TOP, tw, Inches(4.5), WHITE, clr)
        _card_title(s, x, BODY_TOP, tw, t_, clr)
        _bullets(s, x+PAD, BODY_TOP+Inches(0.55), tw-PAD*2, Inches(3.5), items)

    # ════════════════════════════════════════════════════════════
    # 10. ALERTS
    # ════════════════════════════════════════════════════════════
    s = S(ORANGE)
    _title(s, "ระบบแจ้งเตือนอัตโนมัติ — 12 รูปแบบ", WHITE)

    alert_data = [
        ("7 กฎกราฟเครือข่าย", [
            "**Repeated Transfers** — คู่เดิม ≥3 ครั้ง",
            "**Fan-in** — เงินเข้าจาก ≥3 แหล่ง",
            "**Fan-out** — เงินออกไป ≥3 เป้า",
            "**Circular Paths** — เงินวน A⇄B",
            "**Pass-through** — รับแล้วโอนต่อทันที",
            "**High-degree Hub** — เชื่อม ≥6 บัญชี",
            "**Repeated Counterparty** — คนเดิมหลายวัน",
        ]),
        ("5 รูปแบบฟอกเงิน FATF", [
            "**Smurfing** — แบ่งรายการย่อย หลีกเลี่ยงเกณฑ์",
            "**Layering** — สร้างชั้นธุรกรรมซ้อนทับ",
            "**Rapid Movement** — เข้า-ออกภายใน 24 ชม.",
            "**Dormant Activation** — บัญชีนิ่ง→ใช้ทันที",
            "**Round-tripping** — เงินวนกลับแหล่งเดิม",
        ]),
        ("4 วิธีทางสถิติ", [
            "**Z-score** — เบี่ยงเบน >Nσ",
            "**IQR** — Q1-1.5×IQR ถึง Q3+1.5×IQR",
            "**Benford's Law** — หลักแรกผิดปกติ",
            "**Moving Average** — เบี่ยงจากค่าเฉลี่ย 30 รายการ",
        ]),
    ]
    for i, (t_, items) in enumerate(alert_data):
        x = MX + i * (tw + GAP)
        _rect(s, x, BODY_TOP, tw, Inches(5.6), RGBColor(0x9C,0x4E,0x18))
        _card_title(s, x, BODY_TOP, tw, t_, LGOLD)
        _bullets(s, x+PAD, BODY_TOP+Inches(0.55), tw-PAD*2, Inches(4.8), items, clr=WHITE, bc=LGOLD, sz=12, sp=Pt(3))

    # ════════════════════════════════════════════════════════════
    # 11. CROSS-ACCOUNT + REPORTS
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "การวิเคราะห์ข้ามบัญชี + Investigation Desk + รายงาน")

    _rect(s, MX, BODY_TOP, hw, Inches(2.7), WHITE, BLUE)
    _card_title(s, MX, BODY_TOP, hw, "Cross-Account Analysis", BLUE)
    _bullets(s, MX+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(2.0), [
        "**Fund Flow** — เงินเข้า/ออกของบัญชีใดก็ได้",
        "**Pairwise** — ธุรกรรมทั้งหมดระหว่าง 2 บัญชี",
        "**BFS Path Finder** — A→B→C→D สูงสุด **4 ทอด**",
        "**Bulk Cross-Match** — จับคู่ข้ามทุกบัญชีพร้อมกัน",
        "**Multi-period** — เปรียบเทียบ 2 ช่วงเวลา",
    ], sz=12)

    rx = MX + hw + GAP
    _rect(s, rx, BODY_TOP, hw, Inches(2.7), WHITE, PURPLE)
    _card_title(s, rx, BODY_TOP, hw, "Investigation Desk — 13 แท็บ", PURPLE)
    _bullets(s, rx+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(2.0), [
        "**Database** │ Files │ Parser Runs │ **Accounts** │ **Search**",
        "**Alerts** │ **Cross-Account** │ **Link Chart** │ **Timeline**",
        "Duplicates │ Matches │ **Audit** │ **Exports**",
    ], sz=12, bc=PURPLE)

    # Reports
    _rect(s, MX, BODY_TOP+Inches(2.95), CW, Inches(3.1), WHITE, GOLD)
    _card_title(s, MX, BODY_TOP+Inches(2.95), CW, "รายงานพร้อมใช้งาน — 6 รูปแบบ", GOLD)
    reports = [
        ("Excel (.xlsx)", "14+ ชีท, TH Sarabun New, สีตามประเภท, สูตร =SUM/=COUNTA, auto-filter"),
        ("PDF", "ปก + สถิติ + คู่สัญญา + alerts + ธุรกรรม + ช่องลงนาม"),
        ("i2 Chart (.anx)", "เปิดใน Analyst's Notebook ได้ทันที — XML format"),
        ("i2 Import (.csv+.ximp)", "CSV data 29 คอลัมน์ + XML spec สำหรับ import"),
        ("STR / CTR", "รูปแบบรายงาน ปปง. พร้อมส่ง — regulatory compliance"),
        ("CSV", "transactions, entities, links, reconciliation, graph data"),
    ]
    for i, (fmt, desc) in enumerate(reports):
        col, row = i % 2, i // 2
        x = MX + PAD + col * (CW / 2)
        y = BODY_TOP + Inches(3.55) + row * Inches(0.55)
        _txt(s, x, y, Inches(1.8), Inches(0.5), fmt, 12, NAVY, True)
        _txt(s, x + Inches(1.8), y, Inches(4.0), Inches(0.5), desc, 10, TXTL)

    # ════════════════════════════════════════════════════════════
    # 12. SECURITY
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "ความปลอดภัย, Chain of Custody, ภาษาไทย", WHITE)

    sec = [
        ("Authentication", SKY, [
            "**JWT** tokens + 3 ระดับ: Admin/Analyst/Viewer",
            "**PBKDF2-SHA256** 100,000 iterations",
            "**Rate Limiting** — 10 req/min login",
            "**Configurable** — BSIE_AUTH_REQUIRED env",
        ]),
        ("Security Headers", SALMON, [
            "**X-Frame-Options**: DENY",
            "**X-Content-Type-Options**: nosniff",
            "**Referrer-Policy**: no-referrer",
            "**Upload Allowlist** — .xlsx/.pdf/.csv/.png",
            "**Max Body Size**: 50 MB",
        ]),
        ("Chain of Custody", GOLD, [
            "**Audit Trail** — ใคร/ทำอะไร/เมื่อไหร่",
            "**Chain of Custody** — ประวัติครบถ้วน",
            "**/api/audit-trail/{type}/{id}**",
            "**SHA-256** file integrity verification",
            "**File Metadata** — forensic checks",
        ]),
    ]
    for i, (t_, clr, items) in enumerate(sec):
        x = MX + i * (tw + GAP)
        _rect(s, x, BODY_TOP, tw, Inches(4.3), DGRAY)
        _card_title(s, x, BODY_TOP, tw, t_, clr)
        _bullets(s, x+PAD, BODY_TOP+Inches(0.5), tw-PAD*2, Inches(3.5), items, sz=11, clr=WHITE, bc=clr, sp=Pt(2))

    # Thai bar
    _rect(s, MX, Inches(5.7), CW, Inches(0.8), DGRAY, GOLD)
    _txt(s, MX+PAD, Inches(5.75), CW-PAD*2, Inches(0.7),
         "ภาษาไทยเต็มระบบ: UI สลับ ไทย/อังกฤษ │ ~500 คีย์แปลภาษา │ TH Sarabun New ทุกรายงาน\n"
         "NLP ชื่อไทย/เบอร์/บัตร ปชช./PromptPay │ 244 ชุดทดสอบ (212 backend + 32 frontend)",
         11, WHITE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 13. LOCAL LLM
    # ════════════════════════════════════════════════════════════
    s = S(DRED)
    _title(s, "ทำไมต้อง Local LLM — ห้ามใช้ Cloud AI", WHITE)

    ch = Inches(5.3)
    _rect(s, MX, BODY_TOP, hw, ch, RGBColor(0x74,0x2A,0x2A))
    _card_title(s, MX, BODY_TOP, hw, "เหตุผลความจำเป็น", SALMON)
    _bullets(s, MX+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, ch-Inches(0.7), [
        "**ความลับทางราชการ** — ระดับ 'ลับ' / 'ลับมาก'",
        "**พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล** (PDPA)",
        "**Training Data Risk** — Cloud LLM อาจนำข้อมูลไปเรียนรู้",
        "**Chain of Custody** — หลักฐานต้องไม่ผ่านระบบภายนอก",
        "**ระเบียบ สตช.** — ข้อมูลอยู่ในโครงข่ายภายใน",
        "**ป้องกันรั่วไหล** — เลขบัญชี, ชื่อผู้ต้องสงสัย, เส้นทางเงิน",
    ], clr=WHITE, bc=SALMON, sz=13)

    rx = MX + hw + GAP
    _rect(s, rx, BODY_TOP, hw, ch, RGBColor(0x74,0x2A,0x2A))
    _card_title(s, rx, BODY_TOP, hw, "Local LLM ทำอะไรได้", SALMON)
    _bullets(s, rx+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(3.3), [
        "**สรุปคดีอัตโนมัติ** — พบเงินเข้า 15 บัญชี 3.2 ล.",
        "**ตอบคำถาม** — บัญชีนี้มีธุรกรรมเกิน 1 แสน?",
        "**จำแนกธุรกรรม** — ช่วย classify ที่ไม่มั่นใจ",
        "**ตรวจจับรูปแบบ** — structuring, smurfing?",
        "**ร่าง STR/CTR** narrative อัตโนมัติ",
    ], clr=WHITE, bc=SALMON, sz=13)
    _txt(s, rx+PAD, BODY_TOP+Inches(4.1), hw-PAD*2, Inches(1.0),
         "แนะนำ: Ollama + Llama 3.1 70B / Typhoon\n"
         "GPU: NVIDIA RTX 4090 (24GB) หรือ A6000 (48GB)\n"
         "ติดตั้งง่าย — API เหมือน OpenAI", 11, RGBColor(0xFE,0xBD,0xBD))

    # ════════════════════════════════════════════════════════════
    # 14. INFRASTRUCTURE
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "โครงสร้างพื้นฐาน — Phase 1 ถึง 4", WHITE)

    inf = [
        ("Phase 1: Standalone (ฟรี)", MINT,
         "PC/Mac พนักงานสอบสวน\n"
         "  └── BSIE (localhost:8757)\n"
         "        ├── FastAPI backend\n"
         "        ├── React frontend\n"
         "        └── SQLite database\n"
         "ไม่ต้องใช้ server ใดๆ"),
        ("Phase 2: สถานีตำรวจ", SKY,
         "Server จังหวัด\n"
         "  ├── BSIE + Nginx (HTTPS)\n"
         "  ├── PostgreSQL Database\n"
         "  ├── Local LLM (Ollama+GPU)\n"
         "  └── File Storage\n"
         "PC สอบสวน 1-30 → Browser → HTTPS"),
    ]
    for i, (t_, clr, desc) in enumerate(inf):
        x = MX + i * (hw + GAP)
        _rect(s, x, BODY_TOP, hw, Inches(2.6), DGRAY, clr)
        _card_title(s, x, BODY_TOP, hw, t_, clr)
        _txt(s, x+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(1.9), desc, 11, WHITE)

    _rect(s, MX, BODY_TOP+Inches(2.85), CW, Inches(3.0), DGRAY, GOLD)
    _card_title(s, MX, BODY_TOP+Inches(2.85), CW, "Phase 3-4: ระดับจังหวัด / ภาค / ประเทศ (On-Premise)", GOLD)
    _txt(s, MX+PAD, BODY_TOP+Inches(3.4), hw-PAD, Inches(2.2),
         "Data Center จังหวัด / ภาค\n"
         "  ├── Load Balancer (Nginx)\n"
         "  ├── BSIE Backend ×2-3\n"
         "  ├── PostgreSQL (primary+replica)\n"
         "  ├── Redis (cache + session)\n"
         "  ├── NAS/SAN (evidence)\n"
         "  ├── Monitoring (Prometheus+Grafana)\n"
         "  └── Backup server", 11, WHITE)
    _txt(s, MX+hw+GAP, BODY_TOP+Inches(3.4), hw-PAD, Inches(2.2),
         "Local LLM Cluster\n"
         "  ├── GPU Server ×1-2 per ภาค\n"
         "  ├── NVIDIA A6000 ×2 per server\n"
         "  └── Llama 3.1 70B + Typhoon\n\n"
         "เชื่อม VPN/HTTPS:\n"
         "  สถานี อ.เมือง → VPN\n"
         "  สถานี อ.เกาะสมุย → VPN\n"
         "  บก.จว. → VPN", 11, WHITE)

    # ════════════════════════════════════════════════════════════
    # 15. ROADMAP — Horizontal Timeline
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "Roadmap การพัฒนา SPNI Platform", WHITE)

    TL_Y = Inches(2.55)  # timeline center

    # Main horizontal axis
    _line(s, MX, TL_Y, CW, Pt(3), RGBColor(0x4A,0x55,0x68))

    # Year marks
    for label, x in [("พ.ศ. 2569", MX), ("2570", MX+Inches(3.9)),
                      ("2571", MX+Inches(7.8)), ("2572+", MX+Inches(11.2))]:
        _line(s, x, TL_Y-Inches(0.15), Pt(2), Inches(0.3), RGBColor(0x71,0x81,0x96))
        _txt(s, x-Inches(0.4), TL_Y-Inches(0.45), Inches(0.9), Inches(0.25),
             label, 10, SUBTLE, True, PP_ALIGN.CENTER)

    # Phase bars
    phases_tl = [
        ("Phase 1\nPilot", "เดือน 1-3", MX, Inches(2.3), GREEN, "ฟรี",
         ["BSIE v4.0 Pilot", "ทดลอง 5-10 คดีจริง", "เก็บ feedback"]),
        ("Phase 2\nจังหวัดนำร่อง", "เดือน 4-9", MX+Inches(2.5), Inches(2.8), BLUE, "~8 ล้าน",
         ["Server 5 จังหวัด", "PostgreSQL + Multi-user", "Local LLM + GPU", "อบรม 5 จังหวัด"]),
        ("Phase 3\nSPNI Foundation", "เดือน 10-21", MX+Inches(5.5), Inches(3.8), ORANGE, "~40 ล้าน",
         ["CDR Module (โมดูล 2)", "Shared Intelligence Layer", "Mobile App", "ขยาย 20 จังหวัด"]),
        ("Phase 4\nระดับประเทศ", "ปีที่ 3+", MX+Inches(9.5), Inches(2.63), RED, "~120 ล้าน",
         ["Social + CCTV Module", "77 จว. ทั้งประเทศ", "Data Center ×10 ภาค", "เชื่อม ปปง./DSI"]),
    ]
    for label, time, x, w, clr, budget, items in phases_tl:
        # Phase bar
        _rect(s, x, TL_Y - Inches(0.28), w, Inches(0.55), clr)
        _txt(s, x, TL_Y - Inches(0.28), w, Inches(0.32), label.split('\n')[0], 11, WHITE, True, PP_ALIGN.CENTER)
        if '\n' in label:
            _txt(s, x, TL_Y - Inches(0.02), w, Inches(0.25), label.split('\n')[1], 9, WHITE, False, PP_ALIGN.CENTER)

        # Diamond milestone
        dm = Inches(0.15)
        d = s.shapes.add_shape(MSO_SHAPE.DIAMOND, x - dm/2, TL_Y - dm/2, dm, dm)
        d.fill.solid(); d.fill.fore_color.rgb = clr; d.line.fill.background()

        # Budget badge below timeline
        bw = min(w, Inches(1.6))
        _rect(s, x + (w-bw)/2, TL_Y + Inches(0.2), bw, Inches(0.35), DGRAY, clr)
        _txt(s, x + (w-bw)/2, TL_Y + Inches(0.22), bw, Inches(0.3),
             budget, 11, clr, True, PP_ALIGN.CENTER)

        # Time label
        _txt(s, x, TL_Y + Inches(0.6), w, Inches(0.2), time, 9, SUBTLE, False, PP_ALIGN.CENTER)

        # Deliverables above
        card_h = Inches(0.22 * len(items) + 0.15)
        card_y = TL_Y - Inches(0.4) - card_h
        _rect(s, x, card_y, w, card_h, DGRAY)
        for j, item in enumerate(items):
            _txt(s, x + Inches(0.1), card_y + Inches(0.08 + j * 0.22),
                 w - Inches(0.2), Inches(0.2), "● " + item, 9, WHITE)

    # Grand total bar
    _rect(s, MX, Inches(6.2), CW, Inches(0.55), DGRAY, GOLD)
    _txt(s, MX+PAD, Inches(6.23), Inches(4), Inches(0.5), "งบประมาณรวม 3 ปี", 15, WHITE, True)
    _txt(s, Inches(5), Inches(6.23), CW - Inches(4.5), Inches(0.5),
         "~170 ล้านบาท │ ฟรี → 8 ล้าน → 40 ล้าน → 120 ล้าน", 14, GOLD, True, PP_ALIGN.RIGHT)

    _txt(s, MX, Inches(6.9), CW, Inches(0.3),
         "Phase 1 เริ่มได้ทันที (ฟรี)  →  Phase 2 ของบหลัง pilot สำเร็จ  →  Phase 3-4 ขยายตามผลลัพธ์จริง",
         11, SUBTLE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 16. BUDGET NATIONAL
    # ════════════════════════════════════════════════════════════
    s = S(GOLD)
    _title(s, "งบประมาณระดับประเทศ — SPNI Platform", VDARK)

    budget_phases = [
        ("Phase 1: Pilot (3 เดือน)", [
            ("ใช้เครื่อง PC ที่มีอยู่ + ซอฟต์แวร์ BSIE v4.0", "ฟรี"),
        ], "ฟรี", GREEN),
        ("Phase 2: จังหวัดนำร่อง 5 จังหวัด (6 เดือน)", [
            ("Application Server ×5 (CPU 8-core, 32GB, 1TB SSD)", "1,500,000 ฿"),
            ("GPU Server สำหรับ Local LLM ×5 (RTX 4090/A6000)", "5,000,000 ฿"),
            ("Network / UPS / อุปกรณ์ ×5 จังหวัด", "500,000 ฿"),
            ("PostgreSQL Migration + พัฒนาเพิ่มเติม", "500,000 ฿"),
            ("อบรมพนักงานสอบสวน 5 จังหวัด", "300,000 ฿"),
        ], "~8 ล้าน", BLUE),
        ("Phase 3: SPNI Foundation + ขยาย 20 จังหวัด (12 เดือน)", [
            ("CDR Analysis Module (โมดูล 2)", "8,000,000 ฿"),
            ("Server + GPU ×20 จังหวัด", "20,000,000 ฿"),
            ("Shared Intelligence Layer + Mobile App", "7,000,000 ฿"),
            ("ทีมพัฒนา 5-8 คน × 12 เดือน", "5,000,000 ฿"),
        ], "~40 ล้าน", ORANGE),
        ("Phase 4: ทั้งประเทศ 77 จังหวัด + 10 ภาค (ปีที่ 2-3)", [
            ("Social Media + CCTV Module (โมดูล 3-4)", "30,000,000 ฿"),
            ("Data Center ระดับภาค ×10 + GPU Cluster", "40,000,000 ฿"),
            ("Deploy 77 จังหวัด — server + network", "30,000,000 ฿"),
            ("ทีมพัฒนา + DevOps 15 คน + อบรมทั่วประเทศ", "20,000,000 ฿"),
        ], "~120 ล้าน", RED),
    ]
    y = BODY_TOP - Inches(0.1)
    for phase_name, items, total, clr in budget_phases:
        h = Inches(0.28 * max(len(items), 1) + 0.35)
        _rect(s, MX, y, CW - Inches(2.7), h, RGBColor(0xFF,0xF8,0xE8))
        _txt(s, MX+PAD, y+Inches(0.04), Inches(7), Inches(0.28), phase_name, 12, clr, True)
        for j, (item, cost) in enumerate(items):
            _txt(s, MX+Inches(0.4), y+Inches(0.3+j*0.28), Inches(5.5), Inches(0.25), item, 10, TXT)
            _txt(s, MX+Inches(6.0), y+Inches(0.3+j*0.28), Inches(3.0), Inches(0.25), cost, 10, TXTL, False, PP_ALIGN.RIGHT)
        # Badge
        _rect(s, CW - Inches(2.0), y+Inches(0.08), Inches(2.3), Inches(0.4), clr)
        _txt(s, CW - Inches(2.0), y+Inches(0.08), Inches(2.3), Inches(0.4), total, 14, WHITE, True, PP_ALIGN.CENTER)
        y += h + Inches(0.08)

    _rect(s, MX, y+Inches(0.05), CW, Inches(0.55), VDARK)
    _txt(s, MX+PAD, y+Inches(0.08), Inches(4), Inches(0.45), "รวมทั้งโครงการ 3 ปี", 16, WHITE, True)
    _txt(s, Inches(5.5), y+Inches(0.08), CW-Inches(5.5), Inches(0.45), "~170 ล้านบาท", 22, GOLD, True, PP_ALIGN.RIGHT)

    # ════════════════════════════════════════════════════════════
    # 17. BUDGET HIGHLIGHTS
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "จุดเด่นของงบประมาณ SPNI")

    highlights = [
        ("ไม่มีค่า license รายปี", "ซอฟต์แวร์ทั้งหมดพัฒนาเอง + Open Source — จ่ายครั้งเดียว ใช้ตลอด\nเปรียบเทียบ: i2 = 500,000 ฿/คน/ปี × 1,484 สถานี = 742 ล้าน/ปี", GREEN),
        ("ขยายได้ไม่จำกัด", "เพิ่มสถานีใหม่ = แค่เพิ่ม server ไม่ต้องจ่าย license เพิ่ม\nรองรับ 1,484 สถานี ~15,000-20,000 พนักงานสอบสวนทั่วประเทศ", BLUE),
        ("Customizable เต็มที่", "มีโค้ดทั้งหมด — แก้ไข ปรับแต่ง เพิ่มฟีเจอร์ ได้เอง\nไม่ต้องพึ่งบริษัทต่างชาติ — เป็นสมบัติของ สตช.", ORANGE),
        ("Data Sovereignty", "ข้อมูลทั้งหมดอยู่ใน On-Premise Server ของ สตช.\nไม่มีข้อมูลคดีออกนอกประเทศ — Local LLM เท่านั้น", RED),
    ]
    for i, (t_, desc, clr) in enumerate(highlights):
        y = BODY_TOP + i * Inches(1.4)
        _line(s, MX, y, Inches(0.12), Inches(1.2), clr)
        _rect(s, MX + Inches(0.2), y, CW - Inches(0.2), Inches(1.2), WHITE)
        _txt(s, MX + Inches(0.4), y + Inches(0.08), CW - Inches(0.8), Inches(0.35), t_, 17, clr, True)
        _txt(s, MX + Inches(0.4), y + Inches(0.48), CW - Inches(0.8), Inches(0.65), desc, 12, TXTL)

    # ════════════════════════════════════════════════════════════
    # 18. COMPARISON
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "เปรียบเทียบกับซอฟต์แวร์ทางการค้า")

    rows = [
        ("คุณสมบัติ", "BSIE (SPNI)", "i2 Analyst's NB", "Cellebrite Fin."),
        ("ราคา", "ฟรี", "500,000 ฿/คน/ปี", "300,000 ฿/คน/ปี"),
        ("1,484 สถานี/ปี", "ค่า server เท่านั้น", "742+ ล้าน/ปี", "445+ ล้าน/ปี"),
        ("ภาษาไทย", "✓ เต็มระบบ", "✗", "✗"),
        ("ธนาคารไทย 8 แห่ง", "✓ Auto-detect", "✗ setup เอง", "~ บางส่วน"),
        ("กราฟเครือข่าย", "✓ mini i2 (5 layout)", "✓ เต็มรูปแบบ", "✓"),
        ("PDF/OCR ภาษาไทย", "✓ EasyOCR", "✗", "~"),
        ("รายงาน ปปง.", "✓ STR/CTR", "✗", "~"),
        ("PromptPay", "✓", "✗", "✗"),
        ("Threat Hunting FATF", "✓ 5 รูปแบบ", "✗", "~"),
        ("Anomaly Detection", "✓ 4 วิธี", "~ บางส่วน", "~"),
        ("Local LLM AI", "✓ Ollama", "✗", "✗"),
        ("Customizable", "✓ มีโค้ดทั้งหมด", "✗ Closed", "✗ Closed"),
        ("Data Sovereignty", "✓ On-Premise 100%", "~ ขึ้นกับ deploy", "~"),
    ]
    col_ws = [Inches(3.2), Inches(3.0), Inches(3.0), Inches(3.0)]
    col_xs = [MX]
    for w in col_ws[:-1]:
        col_xs.append(col_xs[-1] + w + Inches(0.02))

    rh = Inches(0.38)
    for i, row in enumerate(rows):
        y = BODY_TOP + i * rh
        is_hdr = (i == 0)
        for j, cell in enumerate(row):
            bg_c = NAVY if is_hdr else (WHITE if i % 2 == 1 else MGRAY)
            tc = WHITE if is_hdr else TXT
            if j == 1 and not is_hdr and ("✓" in cell or cell == "ฟรี"):
                tc = GREEN
            elif not is_hdr and "✗" in cell:
                tc = RED
            elif not is_hdr and cell.startswith("~"):
                tc = GOLD
            _rect(s, col_xs[j], y, col_ws[j], rh, bg_c)
            al = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            bld = is_hdr or (j == 0)
            _txt(s, col_xs[j]+Inches(0.08), y+Inches(0.02), col_ws[j]-Inches(0.16), rh-Inches(0.04),
                 cell, 11 if not is_hdr else 12, tc, bld, al)

    # ════════════════════════════════════════════════════════════
    # 19. PROJECT STATS
    # ════════════════════════════════════════════════════════════
    s = S(VDARK)
    _title(s, "ขนาดโปรเจค BSIE v4.0 — ตัวเลข", WHITE)

    stats = [
        ("161", "Python Files", GREEN), ("41", "React/TS Files", SKY),
        ("~41,000", "Lines of Code", GOLD), ("120+", "API Endpoints", BLUE),
        ("21", "API Routers", MINT), ("34", "Services", LILAC),
        ("30", "Core Modules", ORANGE), ("20", "DB Tables", SKY),
        ("244", "Automated Tests", GREEN), ("500+", "i18n Keys", GOLD),
        ("8", "ธนาคารไทย", RED), ("14", "Pipeline Steps", PURPLE),
        ("12", "Alert Patterns", ORANGE), ("5", "FATF Models", RED),
        ("4", "Anomaly Methods", LILAC), ("13", "Investigation Tabs", BLUE),
    ]
    sw_stat = (CW - GAP * 3) / 4
    sh_stat = Inches(1.15)
    for i, (num, label, clr) in enumerate(stats):
        col, row = i % 4, i // 4
        x = MX + col * (sw_stat + GAP)
        y = BODY_TOP + row * (sh_stat + Inches(0.15))
        _rect(s, x, y, sw_stat, sh_stat, DGRAY)
        _txt(s, x, y+Inches(0.08), sw_stat, Inches(0.5), num, 28, clr, True, PP_ALIGN.CENTER)
        _txt(s, x, y+Inches(0.65), sw_stat, Inches(0.35), label, 12, WHITE, False, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 20. ROI
    # ════════════════════════════════════════════════════════════
    s = S(GREEN)
    _title(s, "ROI — ผลตอบแทนการลงทุน", WHITE)

    roi = [
        ("เวลาวิเคราะห์", "จาก 3-5 วัน → 30 นาที ต่อคดี", 0.95, SALMON),
        ("ค่า license", "ประหยัด 742+ ล้านบาท/ปี (vs i2 1,484 สถานี)", 1.0, GOLD),
        ("ข้อผิดพลาด", "ลดข้อผิดพลาดจากวิเคราะห์ด้วยมือ — ลดอุทธรณ์", 0.75, SKY),
        ("ตรวจจับเร็ว", "ป้องกันความเสียหายล่วงหน้า — ฟอกเงิน, ฉ้อโกง", 0.85, MINT),
        ("ครอบคลุม", "1,484 สถานีตำรวจ — 77 จังหวัดทั่วประเทศ", 0.80, LILAC),
    ]
    for i, (label, desc, pct, clr) in enumerate(roi):
        y = BODY_TOP + i * Inches(1.05)
        _txt(s, MX, y, Inches(2), Inches(0.4), label, 15, WHITE, True)
        _rect(s, MX+Inches(2.2), y+Inches(0.04), CW-Inches(2.2), Inches(0.42), DGREEN)
        _rect(s, MX+Inches(2.2), y+Inches(0.04), (CW-Inches(2.2))*pct, Inches(0.42), clr)
        _txt(s, MX+Inches(2.4), y+Inches(0.04), CW-Inches(2.6), Inches(0.42), desc, 12, VDARK, True)

    _rect(s, MX, Inches(6.3), CW, Inches(0.6), DGREEN)
    _txt(s, MX, Inches(6.33), CW, Inches(0.55),
         "คืนทุนใน 1 ปี — ค่า license i2 ปีเดียว > งบ SPNI ทั้ง 3 ปี", 17, WHITE, True, PP_ALIGN.CENTER)

    # ════════════════════════════════════════════════════════════
    # 21. TEAM + USERS
    # ════════════════════════════════════════════════════════════
    s = S(LGRAY)
    _title(s, "ทีมพัฒนา + ประมาณการผู้ใช้งาน")

    _rect(s, MX, BODY_TOP, hw, Inches(2.3), WHITE, GREEN)
    _card_title(s, MX, BODY_TOP, hw, "Phase 1-2: ทำได้คนเดียว + AI", GREEN)
    _bullets(s, MX+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(1.5), [
        "ผู้พัฒนาปัจจุบัน (ร.ต.อ.ณัฐวุฒิ) + **Claude AI**",
        "ผลงาน: **41,000 บรรทัด**, 244 tests, 120+ API",
        "เพียงพอสำหรับ pilot + จังหวัดนำร่อง",
    ], sz=12)

    rx = MX + hw + GAP
    _rect(s, rx, BODY_TOP, hw, Inches(2.3), WHITE, ORANGE)
    _card_title(s, rx, BODY_TOP, hw, "Phase 3-4: ต้องการทีม 8-12 คน", ORANGE)
    _bullets(s, rx+PAD, BODY_TOP+Inches(0.5), hw-PAD*2, Inches(1.5), [
        "Backend Dev **2-3** │ Frontend Dev **1-2**",
        "DevOps **1-2** │ AI/ML Engineer **1**",
        "QA **1-2** │ Project Manager **1**",
    ], sz=12, bc=ORANGE)

    # User estimation
    _rect(s, MX, BODY_TOP+Inches(2.6), CW, Inches(3.2), WHITE, BLUE)
    _card_title(s, MX, BODY_TOP+Inches(2.6), CW, "ประมาณการผู้ใช้งาน — จากจังหวัดสู่ทั้งประเทศ", BLUE)

    u_rows = [
        ("ระดับ", "ผู้ใช้พร้อมกัน", "ธุรกรรม/เดือน", "Storage/ปี"),
        ("Phase 1 (pilot)", "1-3 คน", "10,000", "1 GB"),
        ("Phase 2 (5 จังหวัด)", "50-150 คน", "500,000", "50 GB"),
        ("Phase 3 (20 จังหวัด)", "200-600 คน", "2,000,000", "200 GB"),
        ("Phase 4 (ทั้งประเทศ)", "2,000-5,000 คน", "10,000,000+", "1+ TB"),
    ]
    ucw = (CW - Inches(0.6)) / 4
    for i, row in enumerate(u_rows):
        y = BODY_TOP + Inches(3.2) + i * Inches(0.45)
        for j, cell in enumerate(row):
            x = MX + Inches(0.3) + j * ucw
            bg_c = NAVY if i == 0 else (WHITE if i % 2 == 1 else MGRAY)
            tc = WHITE if i == 0 else TXT
            _rect(s, x, y, ucw, Inches(0.42), bg_c)
            al = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            _txt(s, x+Inches(0.08), y+Inches(0.03), ucw-Inches(0.16), Inches(0.35),
                 cell, 11 if i > 0 else 12, tc, (i==0 or j==0), al)

    # ════════════════════════════════════════════════════════════
    # 22. CLOSING
    # ════════════════════════════════════════════════════════════
    s = S(NAVY)
    _txt(s, MX, Inches(0.4), CW, Inches(0.7), "สรุปและขั้นตอนถัดไป", 34, WHITE, True, PP_ALIGN.CENTER)
    _line(s, Inches(5.9), Inches(1.2), Inches(1.5), Pt(3), GOLD)

    closing = [
        ("1.", "BSIE v4.0 พร้อมใช้วันนี้ — ไม่ต้องรองบประมาณ", MINT),
        ("2.", "ทดลอง Pilot กับคดีจริง 5-10 คดี (ฟรี)", SKY),
        ("3.", "เก็บ feedback จากพนักงานสอบสวน", GOLD),
        ("4.", "เสนองบ Phase 2: ~8 ล้านบาท (5 จังหวัดนำร่อง)", SALMON),
        ("5.", "ขยายสู่ SPNI Platform ทั้งประเทศ — 77 จังหวัด 1,484 สถานี", LILAC),
    ]
    for i, (num, text, clr) in enumerate(closing):
        y = Inches(1.6) + i * Inches(0.8)
        _txt(s, Inches(3.2), y, Inches(0.6), Inches(0.55), num, 24, clr, True)
        _txt(s, Inches(3.8), y + Inches(0.05), Inches(7), Inches(0.5), text, 18, WHITE)

    _rect(s, MX, Inches(5.7), CW, Inches(0.7), CDARK)
    _txt(s, MX, Inches(5.73), CW, Inches(0.65),
         "งบ SPNI ทั้ง 3 ปี (~170 ล้าน)  <  ค่า license i2 ปีเดียว (742+ ล้าน)  →  คืนทุนทันที",
         15, GOLD, True, PP_ALIGN.CENTER)

    _txt(s, MX, Inches(6.7), CW, Inches(0.35),
         "ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง │ โทร: 096-776-8757 │ BSIE v4.0 — Bank Statement Intelligence Engine",
         11, SUBTLE, False, PP_ALIGN.CENTER)

    # ── Save ──
    out = Path(__file__).parent.parent / "docs" / "SPNI_BSIE_Presentation.pptx"
    prs.save(str(out))
    print(f"✅ Saved: {out}")
    print(f"   {len(prs.slides)} slides")
    return out


if __name__ == "__main__":
    generate()
