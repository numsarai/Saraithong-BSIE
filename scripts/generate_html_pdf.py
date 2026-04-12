"""
generate_html_pdf.py — SPNI/BSIE Comprehensive Presentation
Generates:
  1. docs/presentation.html — Interactive slide deck (arrows + swipe)
  2. docs/SPNI_BSIE_Presentation.pdf — Print-ready PDF (A4 landscape, weasyprint)

Run:  python scripts/generate_html_pdf.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
HTML_OUT = DOCS / "presentation.html"
PDF_OUT = DOCS / "SPNI_BSIE_Presentation.pdf"


# ══════════════════════════════════════════════════════════════
#  SLIDE CONTENT — 22 slides
# ══════════════════════════════════════════════════════════════

def _slides_html() -> str:
    """Return concatenated HTML for all 22 slides."""
    parts: list[str] = []

    # ── 1. TITLE ──────────────────────────────────────────────
    parts.append(textwrap.dedent("""\
    <section class="slide slide-dark">
      <div class="slide-inner title-slide">
        <p class="small-label" style="color:#a0aec0">สำนักงานตำรวจแห่งชาติ</p>
        <h1 class="mega">SPNI Platform</h1>
        <p class="subtitle" style="color:#63b3ed">Smart Police &amp; National Intelligence</p>
        <div class="gold-line"></div>
        <p class="subtitle-sm">โมดูลแรก: BSIE v4.0 — Bank Statement Intelligence Engine</p>
        <p class="desc-light">ระบบวิเคราะห์ธุรกรรมทางการเงินอัจฉริยะ สำหรับงานสืบสวนสอบสวน</p>
        <div style="margin-top:2.5rem">
          <p class="meta">เอกสารประกอบการนำเสนอเพื่อของบประมาณระดับประเทศ</p>
          <p class="meta">จัดทำโดย ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง</p>
          <p class="meta">เมษายน 2569</p>
        </div>
      </div>
    </section>
    """))

    # ── 2. SPNI VISION ────────────────────────────────────────
    modules_html = ""
    mods = [
        ("โมดูล 1", "BSIE — การเงิน", "v4.0 พร้อมใช้ ★", True),
        ("โมดูล 2", "CDR — โทรศัพท์", "วางแผน", False),
        ("โมดูล 3", "Social Media Intel", "วางแผน", False),
        ("โมดูล 4", "CCTV — ภาพ/วีดีโอ", "วางแผน", False),
    ]
    for num, name, status, active in mods:
        cls = "mod-active" if active else "mod-pending"
        modules_html += f"""
        <div class="mod-card {cls}">
          <span class="mod-num">{num}</span>
          <span class="mod-name">{name}</span>
          <span class="mod-status {'gold' if active else ''}">{status}</span>
        </div>"""

    shared_tags = ""
    tags = [("Entity Registry", "#38a169"), ("Link Analysis", "#2b6cb0"),
            ("Case Mgmt", "#dd6b20"), ("Local LLM AI", "#e53e3e"),
            ("Evidence Chain", "#805ad5"), ("Regulatory", "#d69e2e")]
    for t, c in tags:
        shared_tags += f'<span class="tag" style="background:{c}">{t}</span>'

    parts.append(f"""
    <section class="slide slide-dark">
      <div class="slide-inner">
        <h2 class="slide-title white">SPNI Platform — ภาพรวม 4 โมดูล</h2>
        <p class="slide-sub light-blue">แพลตฟอร์มรวมเครื่องมือสืบสวนสอบสวนสำหรับ สตช. ทั้งประเทศ</p>
        <div class="mod-row">{modules_html}</div>
        <div class="shared-layer">
          <h3 class="layer-title">Shared Intelligence Layer</h3>
          <div class="tag-row">{shared_tags}</div>
          <p class="layer-desc">ทุกโมดูลเชื่อมข้อมูลข้ามกัน — บุคคลเดียวกันพบข้ามบัญชี + CDR + Social + CCTV</p>
        </div>
        <div class="infra-bar">Infrastructure: On-Premise Server │ Local LLM (Ollama) │ PostgreSQL │ VPN/HTTPS │ ห้าม Cloud AI</div>
        <p class="note-sm" style="margin-top:0.8rem">ทำไมเริ่มจาก BSIE?&nbsp; 1) คดีการเงินมากที่สุด&nbsp; 2) ข้อมูลมีโครงสร้างชัดเจน&nbsp; 3) เห็นผลเร็ว — 3 วัน→30 นาที&nbsp; 4) พื้นฐานสำหรับโมดูลอื่น&nbsp; 5) ไม่มีเครื่องมือฟรีที่ดีในตลาด</p>
      </div>
    </section>
    """)

    # ── 3. PROBLEM ─────────────────────────────────────────────
    problems = [
        "วิเคราะห์ Statement <b>ด้วยมือ</b> ใช้เวลา <b>3-5 วัน</b>ต่อคดี",
        "ดูได้<b>ทีละบัญชี</b> ไม่เห็น<b>ภาพรวมเครือข่าย</b>",
        "ใช้ Excel ธรรมดา ไม่มีเครื่องมือ<b>วิเคราะห์เฉพาะทาง</b>",
        "i2 Analyst's Notebook ราคา <b>500,000+ บาท/license/ปี</b> ไม่รองรับไทย",
        "ไม่มีมาตรฐาน<b>รายงาน ปปง.</b> (STR/CTR)",
        "ไม่มีระบบ<b>แจ้งเตือนอัตโนมัติ</b> — พลาดได้ง่าย",
        "ข้อมูลกระจาย<b>หลาย Excel</b> ไม่เชื่อมโยงข้ามบัญชี",
        "<b>ไม่มีเครื่องมือฟรี</b>ที่ดีสำหรับตำรวจไทย",
    ]
    solutions = [
        "ประมวลผลอัตโนมัติ <b>ภายใน 30 นาที</b>",
        "เชื่อมโยงข้ามบัญชี <b>เห็นเครือข่าย</b>ทั้งหมด",
        "กราฟเครือข่าย Timeline <b>แจ้งเตือน 12 รูปแบบ</b>",
        "มี <b>mini i2 Analyst's Notebook</b> ในตัว — <b>ฟรี</b>",
        "สร้างรายงาน <b>PDF/Excel/STR/CTR</b> ตามมาตรฐาน",
        "<b>ตรวจจับ 5 รูปแบบฟอกเงิน</b> FATF อัตโนมัติ",
        "วิเคราะห์ทางสถิติ: <b>Z-score, IQR, Benford's Law</b>",
        "ฟรี — <b>ไม่มีค่า license</b> รองรับ<b>ทั้งประเทศ</b>",
    ]
    prob_li = "\n".join(f'<li class="red-bullet">{p}</li>' for p in problems)
    sol_li = "\n".join(f'<li class="green-bullet">{s}</li>' for s in solutions)
    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">ปัญหาการสืบสวนทางการเงินในปัจจุบัน</h2>
        <div class="two-col">
          <div class="card border-red">
            <h3 class="card-title red">ปัญหาที่พบ</h3>
            <ul class="bullet-list">{prob_li}</ul>
          </div>
          <div class="card border-green">
            <h3 class="card-title green">BSIE แก้ได้</h3>
            <ul class="bullet-list">{sol_li}</ul>
          </div>
        </div>
      </div>
    </section>
    """)

    # ── 4. ARCHITECTURE ────────────────────────────────────────
    fe_tags = ["React 19", "TypeScript", "Vite", "Tailwind CSS",
               "Zustand", "Cytoscape.js", "Recharts", "react-i18next"]
    fe_html = "".join(f'<span class="tech-tag sky">{t}</span>' for t in fe_tags)

    be_names = ["ingestion", "search", "graph", "alerts", "fund_flow",
                "analytics", "reports", "auth", "exports", "workspace"]
    be_html = "".join(f'<span class="tech-tag mint">{n}</span>' for n in be_names)

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">สถาปัตยกรรมระบบ BSIE v4.0</h2>
        <div class="arch-layer" style="background:#204070">
          <span class="layer-label gold">Frontend</span>
          <div class="tech-row">{fe_html}</div>
        </div>
        <div class="arch-layer" style="background:#153525">
          <span class="layer-label mint">Backend</span>
          <p class="layer-info">Python 3.12 │ FastAPI │ 21 Routers │ 34 Services │ 120+ Endpoints</p>
          <div class="tech-row">{be_html}</div>
        </div>
        <div class="arch-split">
          <div class="arch-layer half" style="background:#352515">
            <span class="layer-label gold">Processing Core — 30 modules</span>
            <p class="arch-desc">bank_detector, column_detector, nlp_engine, normalizer, classifier, link_builder, graph_rules, pdf_loader, image_loader (OCR), exporter, llm_agent ...</p>
          </div>
          <div class="arch-layer half" style="background:#251535">
            <span class="layer-label lilac">34 Services</span>
            <p class="arch-desc">alert, anomaly_detection, sna, threat_hunting, fund_flow, auth, regulatory_export, report, insights, case_tapestry, job_queue, audit ...</p>
          </div>
        </div>
        <div class="arch-split">
          <div class="arch-layer half" style="background:#152515">
            <span class="layer-label mint">Database: SQLAlchemy 2 + SQLite WAL</span>
            <p class="arch-desc">20 tables │ Alembic migrations │ Optimized pragmas │ → PostgreSQL (Phase 2)</p>
          </div>
          <div class="arch-layer half" style="background:#251515">
            <span class="layer-label salmon">AI/ML: Local LLM + NLP</span>
            <p class="arch-desc">EasyOCR (Thai+EN) │ NLP Engine (ชื่อ/เบอร์/บัตร ปชช./PromptPay) │ Ollama</p>
          </div>
        </div>
      </div>
    </section>
    """)

    # ── 5. DATABASE ERD ────────────────────────────────────────
    tables = [
        ("FileRecord", "ไฟล์อัพโหลด + SHA-256", "#38a169"),
        ("ParserRun", "ประวัติการประมวลผล", "#38a169"),
        ("Account", "บัญชีทุกแห่ง (normalized)", "#2b6cb0"),
        ("Transaction", "ธุรกรรม 30+ fields", "#2b6cb0"),
        ("StatementBatch", "ชุดรายการเดินบัญชี", "#38a169"),
        ("RawImportRow", "ข้อมูลดิบ forensic", "#38a169"),
        ("Entity", "บุคคล/นิติบุคคล", "#805ad5"),
        ("AccountEntityLink", "เชื่อม Account↔Entity", "#805ad5"),
        ("TransactionMatch", "จับคู่ข้ามบัญชี", "#dd6b20"),
        ("Alert", "แจ้งเตือน + severity", "#e53e3e"),
        ("DuplicateGroup", "กลุ่มข้อมูลซ้ำ", "#dd6b20"),
        ("ReviewDecision", "การตัดสินใจ analyst", "#d69e2e"),
        ("AuditLog", "Audit Trail ทุก action", "#d69e2e"),
        ("ExportJob", "งานส่งออกรายงาน", "#63b3ed"),
        ("User", "ผู้ใช้ JWT + RBAC", "#fc8181"),
        ("AdminSetting", "ตั้งค่า + Workspace", "#4a5568"),
        ("GraphAnnotation", "บันทึกบน node", "#d6bcfa"),
        ("CaseTag", "แท็กคดี", "#48bb78"),
        ("CaseTagLink", "เชื่อม tag↔วัตถุ", "#48bb78"),
        ("MappingProfile", "โปรไฟล์ mapping", "#38a169"),
    ]
    tbl_html = ""
    for name, desc, clr in tables:
        tbl_html += f"""
        <div class="db-card" style="border-color:{clr}">
          <span class="db-name" style="color:{clr}">{name}</span>
          <span class="db-desc">{desc}</span>
        </div>"""

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">ฐานข้อมูล — 20 Tables</h2>
        <div class="db-grid">{tbl_html}</div>
        <p class="note-sm white" style="margin-top:0.5rem">25+ Indexes │ Unique constraints │ Foreign keys │ JSON columns │ Alembic migrations</p>
      </div>
    </section>
    """)

    # ── 6. PIPELINE 14 STEPS ──────────────────────────────────
    steps = [
        ("1", "Load File", "Excel/PDF/Image/OFX", "#38a169"),
        ("2", "Detect Bank", "8 ธนาคาร auto", "#38a169"),
        ("3", "Detect Cols", "Fuzzy 3-tier", "#2b6cb0"),
        ("4", "Load Memory", "Profile ที่จำไว้", "#2b6cb0"),
        ("5", "Apply Map", "แปลงคอลัมน์", "#63b3ed"),
        ("6", "Normalize", "วันที่/เงิน/ทิศทาง", "#63b3ed"),
        ("7", "Parse Acct", "แยกเลข normalize", "#dd6b20"),
        ("8", "Extract Desc", "แยกรายละเอียด", "#dd6b20"),
        ("9", "NLP Enrich", "ชื่อ/เบอร์/ID/PP", "#805ad5"),
        ("10", "Classify", "IN/OUT/TRANSFER", "#805ad5"),
        ("11", "Build Links", "from→to accounts", "#d69e2e"),
        ("12", "Overrides", "แก้ไขจาก analyst", "#d69e2e"),
        ("13", "Build Entity", "สร้าง Entity list", "#fc8181"),
        ("14", "Export", "Account Package", "#fc8181"),
    ]
    steps_html = ""
    for num, name, desc, clr in steps:
        steps_html += f"""
        <div class="step-card" style="border-color:{clr}">
          <span class="step-num" style="color:{clr}">{num}</span>
          <span class="step-name">{name}</span>
          <span class="step-desc">{desc}</span>
        </div>"""

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">Processing Pipeline — 14 ขั้นตอน</h2>
        <div class="step-grid">{steps_html}</div>
      </div>
    </section>
    """)

    # ── 7. DATA INTAKE ─────────────────────────────────────────
    intake_cols = [
        ("8 ธนาคารไทย Auto-detect", [
            "<b>SCB</b> — ไทยพาณิชย์", "<b>KBANK</b> — กสิกรไทย",
            "<b>BBL</b> — กรุงเทพ", "<b>KTB</b> — กรุงไทย",
            "<b>BAY</b> — กรุงศรี", "<b>TTB</b> — ทหารไทยธนชาต",
            "<b>GSB</b> — ออมสิน", "<b>BAAC</b> — ธ.ก.ส.",
        ]),
        ("รูปแบบไฟล์ + OCR", [
            "<b>Excel</b> (.xlsx / .xls) — ทุกธนาคาร",
            "<b>PDF</b> ข้อความ — pdfplumber extraction",
            "<b>PDF สแกน</b> — EasyOCR + table reconstruction",
            "<b>รูปภาพ</b> (JPG/PNG/BMP) — EasyOCR Thai+EN",
            "<b>OFX</b> — ธนาคารออนไลน์",
            "<b>SHA-256</b> ตรวจจับไฟล์ซ้ำอัตโนมัติ",
        ]),
        ("Smart Column Mapping", [
            "<b>3-tier Fuzzy</b> — exact → alias → fuzzy",
            "<b>Self-learning</b> — จำ profile ที่เคย mapping",
            "<b>Body keywords</b> — ตรวจจากเนื้อหาไฟล์",
            "<b>Re-process</b> — mapping ผิด? ทำใหม่ได้",
            "<b>NLP</b> — ชื่อไทย, เบอร์, บัตร ปชช., PromptPay",
        ]),
    ]
    intake_html = ""
    for title, items in intake_cols:
        li = "\n".join(f"<li>{it}</li>" for it in items)
        intake_html += f"""
        <div class="card">
          <h3 class="card-title navy">{title}</h3>
          <ul class="bullet-list green-bullet">{li}</ul>
        </div>"""

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">การนำเข้าข้อมูล — ครบทุกรูปแบบ</h2>
        <div class="three-col">{intake_html}</div>
      </div>
    </section>
    """)

    # ── 8. LINK CHART ──────────────────────────────────────────
    lc_left = [
        "กดขยายเครือข่าย<b>ทีละชั้น ไม่จำกัดความลึก</b>",
        "<b>5 Layout</b>: Circle, Spread, Compact, Hierarchy, Peacock",
        "<b>Conditional Formatting</b> — ขนาด node ตามยอดเงิน",
        "สี border ตาม<b>ระดับความเสี่ยง</b>จาก alert",
        "<b>Edge labels</b> แสดง/ซ่อนยอดเงินบน edge",
        "<b>Pin / Hide / Multi-select</b> จัดระเบียบกราฟ",
        "<b>Focus History</b> — ดูประวัติการสำรวจ node",
        "<b>Export PNG</b> สำหรับใช้ในรายงาน",
    ]
    lc_right = [
        "<b>Degree Centrality</b> — บัญชีเชื่อมต่อมากสุด",
        "<b>Betweenness</b> — บัญชี<b>ตัวกลาง</b> (broker)",
        "<b>Closeness</b> — เข้าถึงทุกจุดเร็วสุด",
        "<b>BFS Path Finder</b> — ตามเงิน A→B→C→D <b>4 ทอด</b>",
        "<b>Graph Annotations</b> — จดบันทึกบน node ได้",
        "<b>Tags</b>: ผู้ต้องสงสัย, พยาน, เหยื่อ, ตรวจสอบเพิ่ม",
        "<b>Workspace</b> — บันทึก/โหลด chart state",
        "<b>Entity Profile</b> — หน้ารวมข้อมูลบุคคล/บัญชี",
    ]
    lc_l = "\n".join(f'<li class="gold-bullet">{x}</li>' for x in lc_left)
    lc_r = "\n".join(f'<li class="gold-bullet">{x}</li>' for x in lc_right)

    parts.append(f"""
    <section class="slide slide-dark">
      <div class="slide-inner">
        <h2 class="slide-title white">กราฟเครือข่าย — mini i2 Analyst's Notebook</h2>
        <p class="slide-sub light-blue">Link Chart 815 บรรทัด — Interactive Multi-hop Expand ไม่จำกัดความลึก</p>
        <div class="two-col">
          <div class="card card-dark border-gold">
            <h3 class="card-title gold">Multi-hop Link Chart</h3>
            <ul class="bullet-list white-text">{lc_l}</ul>
          </div>
          <div class="card card-dark border-gold">
            <h3 class="card-title gold">SNA + Path Tracing</h3>
            <ul class="bullet-list white-text">{lc_r}</ul>
          </div>
        </div>
      </div>
    </section>
    """)

    # ── 9. VISUALIZATION ───────────────────────────────────────
    viz_data = [
        ("Timeline Chart", "#2b6cb0", [
            "<b>Recharts</b> — Bar + Dot mode",
            "Granularity: <b>วัน / สัปดาห์ / เดือน</b>",
            "ดูรูปแบบธุรกรรมตามเวลา",
            "<b>ตรวจจับช่วงเวลาผิดปกติ</b>",
        ]),
        ("Time Wheel (Heatmap)", "#805ad5", [
            "<b>Custom SVG</b> — Hour x Day",
            "24 ชม. x 7 วัน = <b>168 ช่อง</b>",
            "สีตามความถี่ธุรกรรม",
            "<b>ตรวจจับเวลาผิดปกติ</b> (ตี 2-5)",
        ]),
        ("Dashboard", "#38a169", [
            "<b>สรุปภาพรวม</b> — สถิติ, เงินเข้า/ออก",
            "<b>Recent Activity</b> — ธุรกรรมล่าสุด",
            "<b>Top Accounts</b> — บัญชียอดสูงสุด",
            "<b>Code-split</b> — React.lazy + Suspense",
        ]),
    ]
    viz_html = ""
    for title, clr, items in viz_data:
        li = "\n".join(f"<li>{it}</li>" for it in items)
        viz_html += f"""
        <div class="card" style="border-top:4px solid {clr}">
          <h3 class="card-title" style="color:{clr}">{title}</h3>
          <ul class="bullet-list green-bullet">{li}</ul>
        </div>"""

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">การแสดงผล — Timeline, Heatmap, Dashboard</h2>
        <div class="three-col">{viz_html}</div>
      </div>
    </section>
    """)

    # ── 10. ALERTS ─────────────────────────────────────────────
    alert_data = [
        ("7 กฎกราฟเครือข่าย", [
            "<b>Repeated Transfers</b> — คู่เดิม ≥3 ครั้ง",
            "<b>Fan-in</b> — เงินเข้าจาก ≥3 แหล่ง",
            "<b>Fan-out</b> — เงินออกไป ≥3 เป้า",
            "<b>Circular Paths</b> — เงินวน A⇄B",
            "<b>Pass-through</b> — รับแล้วโอนต่อทันที",
            "<b>High-degree Hub</b> — เชื่อม ≥6 บัญชี",
            "<b>Repeated Counterparty</b> — คนเดิมหลายวัน",
        ]),
        ("5 รูปแบบฟอกเงิน FATF", [
            "<b>Smurfing</b> — แบ่งรายการย่อย หลีกเลี่ยงเกณฑ์",
            "<b>Layering</b> — สร้างชั้นธุรกรรมซ้อนทับ",
            "<b>Rapid Movement</b> — เข้า-ออกภายใน 24 ชม.",
            "<b>Dormant Activation</b> — บัญชีนิ่ง→ใช้ทันที",
            "<b>Round-tripping</b> — เงินวนกลับแหล่งเดิม",
        ]),
        ("4 วิธีทางสถิติ", [
            "<b>Z-score</b> — เบี่ยงเบน &gt;Nσ",
            "<b>IQR</b> — Q1-1.5xIQR ถึง Q3+1.5xIQR",
            "<b>Benford's Law</b> — หลักแรกผิดปกติ",
            "<b>Moving Average</b> — เบี่ยงจากค่าเฉลี่ย 30 รายการ",
        ]),
    ]
    alert_html = ""
    for title, items in alert_data:
        li = "\n".join(f'<li class="gold-bullet">{it}</li>' for it in items)
        alert_html += f"""
        <div class="card card-orange">
          <h3 class="card-title gold-light">{title}</h3>
          <ul class="bullet-list white-text">{li}</ul>
        </div>"""

    parts.append(f"""
    <section class="slide slide-orange">
      <div class="slide-inner">
        <h2 class="slide-title white">ระบบแจ้งเตือนอัตโนมัติ — 12 รูปแบบ</h2>
        <div class="three-col">{alert_html}</div>
      </div>
    </section>
    """)

    # ── 11. CROSS-ACCOUNT + REPORTS ────────────────────────────
    cross_items = [
        "<b>Fund Flow</b> — เงินเข้า/ออกของบัญชีใดก็ได้",
        "<b>Pairwise</b> — ธุรกรรมทั้งหมดระหว่าง 2 บัญชี",
        "<b>BFS Path Finder</b> — A→B→C→D สูงสุด <b>4 ทอด</b>",
        "<b>Bulk Cross-Match</b> — จับคู่ข้ามทุกบัญชีพร้อมกัน",
        "<b>Multi-period</b> — เปรียบเทียบ 2 ช่วงเวลา",
    ]
    desk_items = [
        "<b>Database</b> │ Files │ Parser Runs │ <b>Accounts</b> │ <b>Search</b>",
        "<b>Alerts</b> │ <b>Cross-Account</b> │ <b>Link Chart</b> │ <b>Timeline</b>",
        "Duplicates │ Matches │ <b>Audit</b> │ <b>Exports</b>",
    ]
    reports = [
        ("Excel (.xlsx)", "14+ ชีท, TH Sarabun New, สีตามประเภท, สูตร =SUM/=COUNTA, auto-filter"),
        ("PDF", "ปก + สถิติ + คู่สัญญา + alerts + ธุรกรรม + ช่องลงนาม"),
        ("i2 Chart (.anx)", "เปิดใน Analyst's Notebook ได้ทันที — XML format"),
        ("i2 Import (.csv+.ximp)", "CSV data 29 คอลัมน์ + XML spec สำหรับ import"),
        ("STR / CTR", "รูปแบบรายงาน ปปง. พร้อมส่ง — regulatory compliance"),
        ("CSV", "transactions, entities, links, reconciliation, graph data"),
    ]
    cross_li = "\n".join(f"<li>{x}</li>" for x in cross_items)
    desk_li = "\n".join(f'<li class="purple-bullet">{x}</li>' for x in desk_items)
    rpt_html = ""
    for fmt, desc in reports:
        rpt_html += f'<div class="report-row"><span class="report-fmt">{fmt}</span><span class="report-desc">{desc}</span></div>'

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">การวิเคราะห์ข้ามบัญชี + Investigation Desk + รายงาน</h2>
        <div class="two-col" style="margin-bottom:0.8rem">
          <div class="card border-blue">
            <h3 class="card-title blue">Cross-Account Analysis</h3>
            <ul class="bullet-list green-bullet">{cross_li}</ul>
          </div>
          <div class="card border-purple">
            <h3 class="card-title purple">Investigation Desk — 13 แท็บ</h3>
            <ul class="bullet-list">{desk_li}</ul>
          </div>
        </div>
        <div class="card border-gold full-width">
          <h3 class="card-title gold">รายงานพร้อมใช้งาน — 6 รูปแบบ</h3>
          <div class="report-grid">{rpt_html}</div>
        </div>
      </div>
    </section>
    """)

    # ── 12. SECURITY ───────────────────────────────────────────
    sec_data = [
        ("Authentication", "#63b3ed", [
            "<b>JWT</b> tokens + 3 ระดับ: Admin/Analyst/Viewer",
            "<b>PBKDF2-SHA256</b> 100,000 iterations",
            "<b>Rate Limiting</b> — 10 req/min login",
            "<b>Configurable</b> — BSIE_AUTH_REQUIRED env",
        ]),
        ("Security Headers", "#fc8181", [
            "<b>X-Frame-Options</b>: DENY",
            "<b>X-Content-Type-Options</b>: nosniff",
            "<b>Referrer-Policy</b>: no-referrer",
            "<b>Upload Allowlist</b> — .xlsx/.pdf/.csv/.png",
            "<b>Max Body Size</b>: 50 MB",
        ]),
        ("Chain of Custody", "#d69e2e", [
            "<b>Audit Trail</b> — ใคร/ทำอะไร/เมื่อไหร่",
            "<b>Chain of Custody</b> — ประวัติครบถ้วน",
            "<b>/api/audit-trail/{type}/{id}</b>",
            "<b>SHA-256</b> file integrity verification",
            "<b>File Metadata</b> — forensic checks",
        ]),
    ]
    sec_html = ""
    for title, clr, items in sec_data:
        li = "\n".join(f"<li>{it}</li>" for it in items)
        sec_html += f"""
        <div class="card card-dark">
          <h3 class="card-title" style="color:{clr}">{title}</h3>
          <ul class="bullet-list white-text" style="--bullet-color:{clr}">{li}</ul>
        </div>"""

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">ความปลอดภัย, Chain of Custody, ภาษาไทย</h2>
        <div class="three-col">{sec_html}</div>
        <div class="thai-bar">
          <p>ภาษาไทยเต็มระบบ: UI สลับ ไทย/อังกฤษ │ ~500 คีย์แปลภาษา │ TH Sarabun New ทุกรายงาน</p>
          <p>NLP ชื่อไทย/เบอร์/บัตร ปชช./PromptPay │ 244 ชุดทดสอบ (212 backend + 32 frontend)</p>
        </div>
      </div>
    </section>
    """)

    # ── 13. LOCAL LLM ──────────────────────────────────────────
    llm_left = [
        "<b>ความลับทางราชการ</b> — ระดับ 'ลับ' / 'ลับมาก'",
        "<b>พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล</b> (PDPA)",
        "<b>Training Data Risk</b> — Cloud LLM อาจนำข้อมูลไปเรียนรู้",
        "<b>Chain of Custody</b> — หลักฐานต้องไม่ผ่านระบบภายนอก",
        "<b>ระเบียบ สตช.</b> — ข้อมูลอยู่ในโครงข่ายภายใน",
        "<b>ป้องกันรั่วไหล</b> — เลขบัญชี, ชื่อผู้ต้องสงสัย, เส้นทางเงิน",
    ]
    llm_right = [
        "<b>สรุปคดีอัตโนมัติ</b> — พบเงินเข้า 15 บัญชี 3.2 ล.",
        "<b>ตอบคำถาม</b> — บัญชีนี้มีธุรกรรมเกิน 1 แสน?",
        "<b>จำแนกธุรกรรม</b> — ช่วย classify ที่ไม่มั่นใจ",
        "<b>ตรวจจับรูปแบบ</b> — structuring, smurfing?",
        "<b>ร่าง STR/CTR</b> narrative อัตโนมัติ",
    ]
    ll_l = "\n".join(f'<li class="salmon-bullet">{x}</li>' for x in llm_left)
    ll_r = "\n".join(f'<li class="salmon-bullet">{x}</li>' for x in llm_right)

    parts.append(f"""
    <section class="slide slide-red">
      <div class="slide-inner">
        <h2 class="slide-title white">ทำไมต้อง Local LLM — ห้ามใช้ Cloud AI</h2>
        <div class="two-col">
          <div class="card card-dred">
            <h3 class="card-title salmon">เหตุผลความจำเป็น</h3>
            <ul class="bullet-list white-text">{ll_l}</ul>
          </div>
          <div class="card card-dred">
            <h3 class="card-title salmon">Local LLM ทำอะไรได้</h3>
            <ul class="bullet-list white-text">{ll_r}</ul>
            <p class="note-pink">แนะนำ: Ollama + Llama 3.1 70B / Typhoon<br>GPU: NVIDIA RTX 4090 (24GB) หรือ A6000 (48GB)<br>ติดตั้งง่าย — API เหมือน OpenAI</p>
          </div>
        </div>
      </div>
    </section>
    """)

    # ── 14. INFRASTRUCTURE ─────────────────────────────────────
    parts.append("""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">โครงสร้างพื้นฐาน — Phase 1 ถึง 4</h2>
        <div class="two-col" style="margin-bottom:0.8rem">
          <div class="card card-dark border-mint">
            <h3 class="card-title mint">Phase 1: Standalone (ฟรี)</h3>
            <pre class="infra-tree">PC/Mac พนักงานสอบสวน
  └── BSIE (localhost:8757)
        ├── FastAPI backend
        ├── React frontend
        └── SQLite database
ไม่ต้องใช้ server ใดๆ</pre>
          </div>
          <div class="card card-dark border-sky">
            <h3 class="card-title sky">Phase 2: สถานีตำรวจ</h3>
            <pre class="infra-tree">Server จังหวัด
  ├── BSIE + Nginx (HTTPS)
  ├── PostgreSQL Database
  ├── Local LLM (Ollama+GPU)
  └── File Storage
PC สอบสวน 1-30 → Browser → HTTPS</pre>
          </div>
        </div>
        <div class="card card-dark border-gold full-width">
          <h3 class="card-title gold">Phase 3-4: ระดับจังหวัด / ภาค / ประเทศ (On-Premise)</h3>
          <div class="two-col">
            <pre class="infra-tree">Data Center จังหวัด / ภาค
  ├── Load Balancer (Nginx)
  ├── BSIE Backend x2-3
  ├── PostgreSQL (primary+replica)
  ├── Redis (cache + session)
  ├── NAS/SAN (evidence)
  ├── Monitoring (Prometheus+Grafana)
  └── Backup server</pre>
            <pre class="infra-tree">Local LLM Cluster
  ├── GPU Server x1-2 per ภาค
  ├── NVIDIA A6000 x2 per server
  └── Llama 3.1 70B + Typhoon

เชื่อม VPN/HTTPS:
  สถานี อ.เมือง → VPN
  สถานี อ.เกาะสมุย → VPN
  บก.จว. → VPN</pre>
          </div>
        </div>
      </div>
    </section>
    """)

    # ── 15. ROADMAP HORIZONTAL ─────────────────────────────────
    phases_road = [
        ("Phase 1", "Pilot", "เดือน 1-3", "#38a169", "ฟรี",
         ["BSIE v4.0 Pilot", "ทดลอง 5-10 คดีจริง", "เก็บ feedback"]),
        ("Phase 2", "จังหวัดนำร่อง", "เดือน 4-9", "#2b6cb0", "~8 ล้าน",
         ["Server 5 จังหวัด", "PostgreSQL + Multi-user", "Local LLM + GPU", "อบรม 5 จังหวัด"]),
        ("Phase 3", "SPNI Foundation", "เดือน 10-21", "#dd6b20", "~40 ล้าน",
         ["CDR Module (โมดูล 2)", "Shared Intelligence Layer", "Mobile App", "ขยาย 20 จังหวัด"]),
        ("Phase 4", "ระดับประเทศ", "ปีที่ 3+", "#e53e3e", "~120 ล้าน",
         ["Social + CCTV Module", "77 จว. ทั้งประเทศ", "Data Center x10 ภาค", "เชื่อม ปปง./DSI"]),
    ]
    road_html = ""
    for p_name, p_sub, p_time, clr, budget, deliverables in phases_road:
        d_html = "\n".join(f"<li>{d}</li>" for d in deliverables)
        road_html += f"""
        <div class="road-phase">
          <div class="road-deliverables"><ul>{d_html}</ul></div>
          <div class="road-bar" style="background:{clr}">
            <span class="road-name">{p_name}</span>
            <span class="road-sub">{p_sub}</span>
          </div>
          <div class="road-diamond" style="background:{clr}"></div>
          <div class="road-badge" style="border-color:{clr};color:{clr}">{budget}</div>
          <div class="road-time">{p_time}</div>
        </div>"""

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">Roadmap การพัฒนา SPNI Platform</h2>
        <div class="road-year-marks">
          <span>พ.ศ. 2569</span><span>2570</span><span>2571</span><span>2572+</span>
        </div>
        <div class="road-timeline">
          <div class="road-axis"></div>
          <div class="road-phases">{road_html}</div>
        </div>
        <div class="road-total">
          <span class="road-total-label">งบประมาณรวม 3 ปี</span>
          <span class="road-total-val">~170 ล้านบาท │ ฟรี → 8 ล้าน → 40 ล้าน → 120 ล้าน</span>
        </div>
        <p class="note-sm white" style="margin-top:0.5rem">Phase 1 เริ่มได้ทันที (ฟรี) → Phase 2 ของบหลัง pilot สำเร็จ → Phase 3-4 ขยายตามผลลัพธ์จริง</p>
      </div>
    </section>
    """)

    # ── 16. BUDGET NATIONAL ────────────────────────────────────
    budget_phases = [
        ("Phase 1: Pilot (3 เดือน)", [
            ("ใช้เครื่อง PC ที่มีอยู่ + ซอฟต์แวร์ BSIE v4.0", "ฟรี"),
        ], "ฟรี", "#38a169"),
        ("Phase 2: จังหวัดนำร่อง 5 จังหวัด (6 เดือน)", [
            ("Application Server x5 (CPU 8-core, 32GB, 1TB SSD)", "1,500,000 ฿"),
            ("GPU Server สำหรับ Local LLM x5 (RTX 4090/A6000)", "5,000,000 ฿"),
            ("Network / UPS / อุปกรณ์ x5 จังหวัด", "500,000 ฿"),
            ("PostgreSQL Migration + พัฒนาเพิ่มเติม", "500,000 ฿"),
            ("อบรมพนักงานสอบสวน 5 จังหวัด", "300,000 ฿"),
        ], "~8 ล้าน", "#2b6cb0"),
        ("Phase 3: SPNI Foundation + ขยาย 20 จังหวัด (12 เดือน)", [
            ("CDR Analysis Module (โมดูล 2)", "8,000,000 ฿"),
            ("Server + GPU x20 จังหวัด", "20,000,000 ฿"),
            ("Shared Intelligence Layer + Mobile App", "7,000,000 ฿"),
            ("ทีมพัฒนา 5-8 คน x 12 เดือน", "5,000,000 ฿"),
        ], "~40 ล้าน", "#dd6b20"),
        ("Phase 4: ทั้งประเทศ 77 จังหวัด + 10 ภาค (ปีที่ 2-3)", [
            ("Social Media + CCTV Module (โมดูล 3-4)", "30,000,000 ฿"),
            ("Data Center ระดับภาค x10 + GPU Cluster", "40,000,000 ฿"),
            ("Deploy 77 จังหวัด — server + network", "30,000,000 ฿"),
            ("ทีมพัฒนา + DevOps 15 คน + อบรมทั่วประเทศ", "20,000,000 ฿"),
        ], "~120 ล้าน", "#e53e3e"),
    ]
    budget_html = ""
    for phase_name, items, total, clr in budget_phases:
        rows = ""
        for item, cost in items:
            rows += f'<div class="budget-item"><span class="budget-desc">{item}</span><span class="budget-cost">{cost}</span></div>'
        budget_html += f"""
        <div class="budget-phase">
          <div class="budget-header">
            <span class="budget-phase-name" style="color:{clr}">{phase_name}</span>
            <span class="budget-total-badge" style="background:{clr}">{total}</span>
          </div>
          {rows}
        </div>"""

    parts.append(f"""
    <section class="slide slide-gold">
      <div class="slide-inner">
        <h2 class="slide-title dark">งบประมาณระดับประเทศ — SPNI Platform</h2>
        <div class="budget-list">{budget_html}</div>
        <div class="budget-grand">
          <span class="budget-grand-label">รวมทั้งโครงการ 3 ปี</span>
          <span class="budget-grand-val">~170 ล้านบาท</span>
        </div>
      </div>
    </section>
    """)

    # ── 17. BUDGET HIGHLIGHTS ──────────────────────────────────
    highlights = [
        ("ไม่มีค่า license รายปี", "ซอฟต์แวร์ทั้งหมดพัฒนาเอง + Open Source — จ่ายครั้งเดียว ใช้ตลอด<br>เปรียบเทียบ: i2 = 500,000 ฿/คน/ปี x 1,484 สถานี = 742 ล้าน/ปี", "#38a169"),
        ("ขยายได้ไม่จำกัด", "เพิ่มสถานีใหม่ = แค่เพิ่ม server ไม่ต้องจ่าย license เพิ่ม<br>รองรับ 1,484 สถานี ~15,000-20,000 พนักงานสอบสวนทั่วประเทศ", "#2b6cb0"),
        ("Customizable เต็มที่", "มีโค้ดทั้งหมด — แก้ไข ปรับแต่ง เพิ่มฟีเจอร์ ได้เอง<br>ไม่ต้องพึ่งบริษัทต่างชาติ — เป็นสมบัติของ สตช.", "#dd6b20"),
        ("Data Sovereignty", "ข้อมูลทั้งหมดอยู่ใน On-Premise Server ของ สตช.<br>ไม่มีข้อมูลคดีออกนอกประเทศ — Local LLM เท่านั้น", "#e53e3e"),
    ]
    hl_html = ""
    for title, desc, clr in highlights:
        hl_html += f"""
        <div class="highlight-card">
          <div class="highlight-bar" style="background:{clr}"></div>
          <div class="highlight-body">
            <h3 class="highlight-title" style="color:{clr}">{title}</h3>
            <p class="highlight-desc">{desc}</p>
          </div>
        </div>"""

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">จุดเด่นของงบประมาณ SPNI</h2>
        <div class="highlights-list">{hl_html}</div>
      </div>
    </section>
    """)

    # ── 18. COMPARISON ─────────────────────────────────────────
    comp_rows = [
        ("คุณสมบัติ", "BSIE (SPNI)", "i2 Analyst's NB", "Cellebrite Fin."),
        ("ราคา", "ฟรี", "500,000 ฿/คน/ปี", "300,000 ฿/คน/ปี"),
        ("1,484 สถานี/ปี", "ค่า server เท่านั้น", "742+ ล้าน/ปี", "445+ ล้าน/ปี"),
        ("ภาษาไทย", "V เต็มระบบ", "X", "X"),
        ("ธนาคารไทย 8 แห่ง", "V Auto-detect", "X setup เอง", "~ บางส่วน"),
        ("กราฟเครือข่าย", "V mini i2 (5 layout)", "V เต็มรูปแบบ", "V"),
        ("PDF/OCR ภาษาไทย", "V EasyOCR", "X", "~"),
        ("รายงาน ปปง.", "V STR/CTR", "X", "~"),
        ("PromptPay", "V", "X", "X"),
        ("Threat Hunting FATF", "V 5 รูปแบบ", "X", "~"),
        ("Anomaly Detection", "V 4 วิธี", "~ บางส่วน", "~"),
        ("Local LLM AI", "V Ollama", "X", "X"),
        ("Customizable", "V มีโค้ดทั้งหมด", "X Closed", "X Closed"),
        ("Data Sovereignty", "V On-Premise 100%", "~ ขึ้นกับ deploy", "~"),
    ]
    thead = "<tr>"
    for h in comp_rows[0]:
        thead += f"<th>{h}</th>"
    thead += "</tr>"
    tbody = ""
    for row in comp_rows[1:]:
        tbody += "<tr>"
        for j, cell in enumerate(row):
            cls = ""
            display = cell
            if j == 1 and (cell.startswith("V") or cell == "ฟรี"):
                cls = ' class="comp-green"'
                display = cell.replace("V ", "&#10003; ").replace("V", "&#10003;")
            elif cell.startswith("X"):
                cls = ' class="comp-red"'
                display = cell.replace("X ", "&#10007; ").replace("X", "&#10007;")
            elif cell.startswith("~"):
                cls = ' class="comp-gold"'
            elif j == 0:
                cls = ' class="comp-label"'
            tbody += f"<td{cls}>{display}</td>"
        tbody += "</tr>"

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">เปรียบเทียบกับซอฟต์แวร์ทางการค้า</h2>
        <div class="comp-table-wrap">
          <table class="comp-table">
            <thead>{thead}</thead>
            <tbody>{tbody}</tbody>
          </table>
        </div>
      </div>
    </section>
    """)

    # ── 19. PROJECT STATS ──────────────────────────────────────
    stats = [
        ("161", "Python Files", "#38a169"), ("41", "React/TS Files", "#63b3ed"),
        ("~41,000", "Lines of Code", "#d69e2e"), ("120+", "API Endpoints", "#2b6cb0"),
        ("21", "API Routers", "#48bb78"), ("34", "Services", "#d6bcfa"),
        ("30", "Core Modules", "#dd6b20"), ("20", "DB Tables", "#63b3ed"),
        ("244", "Automated Tests", "#38a169"), ("500+", "i18n Keys", "#d69e2e"),
        ("8", "ธนาคารไทย", "#e53e3e"), ("14", "Pipeline Steps", "#805ad5"),
        ("12", "Alert Patterns", "#dd6b20"), ("5", "FATF Models", "#e53e3e"),
        ("4", "Anomaly Methods", "#d6bcfa"), ("13", "Investigation Tabs", "#2b6cb0"),
    ]
    stat_html = ""
    for num, label, clr in stats:
        stat_html += f"""
        <div class="stat-card">
          <span class="stat-num" style="color:{clr}">{num}</span>
          <span class="stat-label">{label}</span>
        </div>"""

    parts.append(f"""
    <section class="slide slide-vdark">
      <div class="slide-inner">
        <h2 class="slide-title white">ขนาดโปรเจค BSIE v4.0 — ตัวเลข</h2>
        <div class="stat-grid">{stat_html}</div>
      </div>
    </section>
    """)

    # ── 20. ROI ────────────────────────────────────────────────
    roi_data = [
        ("เวลาวิเคราะห์", "จาก 3-5 วัน → 30 นาที ต่อคดี", 95, "#fc8181"),
        ("ค่า license", "ประหยัด 742+ ล้านบาท/ปี (vs i2 1,484 สถานี)", 100, "#d69e2e"),
        ("ข้อผิดพลาด", "ลดข้อผิดพลาดจากวิเคราะห์ด้วยมือ — ลดอุทธรณ์", 75, "#63b3ed"),
        ("ตรวจจับเร็ว", "ป้องกันความเสียหายล่วงหน้า — ฟอกเงิน, ฉ้อโกง", 85, "#48bb78"),
        ("ครอบคลุม", "1,484 สถานีตำรวจ — 77 จังหวัดทั่วประเทศ", 80, "#d6bcfa"),
    ]
    roi_html = ""
    for label, desc, pct, clr in roi_data:
        roi_html += f"""
        <div class="roi-row">
          <span class="roi-label">{label}</span>
          <div class="roi-bar-bg">
            <div class="roi-bar-fill" style="width:{pct}%;background:{clr}"></div>
            <span class="roi-bar-text">{desc}</span>
          </div>
        </div>"""

    parts.append(f"""
    <section class="slide slide-green">
      <div class="slide-inner">
        <h2 class="slide-title white">ROI — ผลตอบแทนการลงทุน</h2>
        <div class="roi-list">{roi_html}</div>
        <div class="roi-bottom">คืนทุนใน 1 ปี — ค่า license i2 ปีเดียว &gt; งบ SPNI ทั้ง 3 ปี</div>
      </div>
    </section>
    """)

    # ── 21. TEAM + USERS ───────────────────────────────────────
    team_l = [
        "ผู้พัฒนาปัจจุบัน (ร.ต.อ.ณัฐวุฒิ) + <b>Claude AI</b>",
        "ผลงาน: <b>41,000 บรรทัด</b>, 244 tests, 120+ API",
        "เพียงพอสำหรับ pilot + จังหวัดนำร่อง",
    ]
    team_r = [
        "Backend Dev <b>2-3</b> │ Frontend Dev <b>1-2</b>",
        "DevOps <b>1-2</b> │ AI/ML Engineer <b>1</b>",
        "QA <b>1-2</b> │ Project Manager <b>1</b>",
    ]
    tl_li = "\n".join(f"<li>{x}</li>" for x in team_l)
    tr_li = "\n".join(f'<li class="orange-bullet">{x}</li>' for x in team_r)
    u_rows = [
        ("ระดับ", "ผู้ใช้พร้อมกัน", "ธุรกรรม/เดือน", "Storage/ปี"),
        ("Phase 1 (pilot)", "1-3 คน", "10,000", "1 GB"),
        ("Phase 2 (5 จังหวัด)", "50-150 คน", "500,000", "50 GB"),
        ("Phase 3 (20 จังหวัด)", "200-600 คน", "2,000,000", "200 GB"),
        ("Phase 4 (ทั้งประเทศ)", "2,000-5,000 คน", "10,000,000+", "1+ TB"),
    ]
    u_head = "<tr>" + "".join(f"<th>{h}</th>" for h in u_rows[0]) + "</tr>"
    u_body = ""
    for row in u_rows[1:]:
        u_body += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"

    parts.append(f"""
    <section class="slide">
      <div class="slide-inner">
        <h2 class="slide-title">ทีมพัฒนา + ประมาณการผู้ใช้งาน</h2>
        <div class="two-col" style="margin-bottom:0.8rem">
          <div class="card border-green">
            <h3 class="card-title green">Phase 1-2: ทำได้คนเดียว + AI</h3>
            <ul class="bullet-list green-bullet">{tl_li}</ul>
          </div>
          <div class="card border-orange">
            <h3 class="card-title orange">Phase 3-4: ต้องการทีม 8-12 คน</h3>
            <ul class="bullet-list">{tr_li}</ul>
          </div>
        </div>
        <div class="card border-blue full-width">
          <h3 class="card-title blue">ประมาณการผู้ใช้งาน — จากจังหวัดสู่ทั้งประเทศ</h3>
          <table class="user-table">
            <thead>{u_head}</thead>
            <tbody>{u_body}</tbody>
          </table>
        </div>
      </div>
    </section>
    """)

    # ── 22. CLOSING ────────────────────────────────────────────
    closing_steps = [
        ("1.", "BSIE v4.0 พร้อมใช้วันนี้ — ไม่ต้องรองบประมาณ", "#48bb78"),
        ("2.", "ทดลอง Pilot กับคดีจริง 5-10 คดี (ฟรี)", "#63b3ed"),
        ("3.", "เก็บ feedback จากพนักงานสอบสวน", "#d69e2e"),
        ("4.", "เสนองบ Phase 2: ~8 ล้านบาท (5 จังหวัดนำร่อง)", "#fc8181"),
        ("5.", "ขยายสู่ SPNI Platform ทั้งประเทศ — 77 จังหวัด 1,484 สถานี", "#d6bcfa"),
    ]
    close_html = ""
    for num, text, clr in closing_steps:
        close_html += f"""
        <div class="close-step">
          <span class="close-num" style="color:{clr}">{num}</span>
          <span class="close-text">{text}</span>
        </div>"""

    parts.append(f"""
    <section class="slide slide-dark">
      <div class="slide-inner closing-slide">
        <h2 class="slide-title white mega-close">สรุปและขั้นตอนถัดไป</h2>
        <div class="gold-line"></div>
        <div class="close-steps">{close_html}</div>
        <div class="close-highlight">งบ SPNI ทั้ง 3 ปี (~170 ล้าน) &lt; ค่า license i2 ปีเดียว (742+ ล้าน) → คืนทุนทันที</div>
        <p class="close-contact">ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง │ โทร: 096-776-8757 │ BSIE v4.0 — Bank Statement Intelligence Engine</p>
      </div>
    </section>
    """)

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
#  CSS — shared between screen and print
# ══════════════════════════════════════════════════════════════

CSS = r"""
/* ── Reset + Base ──────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;scroll-behavior:smooth}
body{
  font-family:'Noto Sans Thai','Noto Sans',sans-serif;
  background:#0d1117;color:#1a202c;
  -webkit-font-smoothing:antialiased;
  overflow:hidden;
}

/* ── Slide container ───────────────────────────────────── */
.slides-wrapper{
  position:relative;width:100vw;height:100vh;overflow:hidden;
}
section.slide{
  position:absolute;top:0;left:0;
  width:100vw;height:100vh;
  display:none;overflow:hidden;
}
section.slide.active{display:flex;align-items:stretch}

.slide-inner{
  width:100%;height:100%;
  padding:40px 48px;
  display:flex;flex-direction:column;
  overflow-y:auto;
}

/* ── Backgrounds ───────────────────────────────────────── */
.slide{background:#f7fafc}
.slide-dark{background:#1a365d}
.slide-vdark{background:#1a202c}
.slide-orange{background:#dd6b20}
.slide-red{background:#c53030}
.slide-green{background:#38a169}
.slide-gold{background:#d69e2e}

/* ── Typography ────────────────────────────────────────── */
.slide-title{font-size:1.6rem;font-weight:700;margin-bottom:0.3rem;color:#1a365d;text-align:center}
.slide-title.white{color:#fff}
.slide-title.dark{color:#1a202c}
.slide-sub{font-size:0.85rem;text-align:center;margin-bottom:0.6rem;color:#4a5568}
.slide-sub.light-blue{color:#bee3f8}
.mega{font-size:3rem;font-weight:800;color:#fff;text-align:center;margin:0.3rem 0}
.mega-close{font-size:2rem;margin-bottom:0.3rem}
.subtitle{font-size:1.3rem;text-align:center;margin-bottom:0.2rem}
.subtitle-sm{font-size:1.05rem;color:#fff;text-align:center;margin-top:0.6rem}
.desc-light{font-size:0.9rem;color:#bee3f8;text-align:center;margin-top:0.2rem}
.meta{font-size:0.78rem;color:#a0aec0;text-align:center;line-height:1.6}
.small-label{font-size:0.75rem;text-align:center;margin-bottom:0.2rem}

/* ── Title slide ───────────────────────────────────────── */
.title-slide{justify-content:center;align-items:center;text-align:center}
.gold-line{width:100px;height:3px;background:#d69e2e;margin:0.8rem auto}

/* ── Cards & Layouts ───────────────────────────────────── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:0.7rem;flex:1;min-height:0}
.three-col{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.7rem;flex:1;min-height:0}
.card{background:#fff;border-radius:8px;padding:0.7rem 0.8rem;overflow:hidden}
.card-dark{background:#2d3748}
.card-dred{background:#742a2a}
.card-orange{background:#9c4e18}
.full-width{grid-column:1/-1}
.card-title{font-size:0.95rem;font-weight:700;margin-bottom:0.4rem}
.card-title.navy{color:#1a365d} .card-title.red{color:#e53e3e}
.card-title.green{color:#38a169} .card-title.blue{color:#2b6cb0}
.card-title.purple{color:#805ad5} .card-title.gold{color:#d69e2e}
.card-title.orange{color:#dd6b20} .card-title.salmon{color:#fc8181}
.card-title.gold-light{color:#ecc94b} .card-title.mint{color:#48bb78}
.card-title.sky{color:#63b3ed}

/* borders */
.border-red{border-left:4px solid #e53e3e}
.border-green{border-left:4px solid #38a169}
.border-blue{border-left:4px solid #2b6cb0}
.border-purple{border-left:4px solid #805ad5}
.border-gold{border-left:4px solid #d69e2e}
.border-orange{border-left:4px solid #dd6b20}
.border-mint{border-left:4px solid #48bb78}
.border-sky{border-left:4px solid #63b3ed}

/* ── Bullet lists ──────────────────────────────────────── */
.bullet-list{list-style:none;padding:0;font-size:0.78rem;line-height:1.55}
.bullet-list li{padding-left:1.1em;position:relative;margin-bottom:0.2rem}
.bullet-list li::before{content:'●';position:absolute;left:0;font-size:0.6em;top:0.35em;color:#38a169}
.bullet-list .red-bullet::before{color:#e53e3e}
.bullet-list .green-bullet::before{color:#38a169}
.bullet-list .gold-bullet::before{color:#ecc94b}
.bullet-list .purple-bullet::before{color:#805ad5}
.bullet-list .salmon-bullet::before{color:#fc8181}
.bullet-list .orange-bullet::before{color:#dd6b20}
.green-bullet li::before{color:#38a169}
.white-text{color:#fff}
.white-text li::before{color:var(--bullet-color,#d69e2e)}

/* ── Module row (slide 2) ──────────────────────────────── */
.mod-row{display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin:0.6rem 0}
.mod-card{background:#2d3748;border-radius:8px;padding:0.5rem;text-align:center;border:2px solid #4a5568}
.mod-active{background:#48bb78;border-color:#d69e2e}
.mod-num{display:block;font-size:0.65rem;color:#a0aec0}
.mod-name{display:block;font-size:0.85rem;font-weight:700;color:#fff;margin:0.15rem 0}
.mod-status{display:block;font-size:0.7rem;color:#a0aec0}
.mod-status.gold{color:#d69e2e}
.shared-layer{background:#1e3a5f;border-radius:8px;padding:0.6rem;text-align:center;margin:0.5rem 0}
.layer-title{color:#fff;font-size:0.95rem;margin-bottom:0.4rem}
.tag-row{display:flex;flex-wrap:wrap;gap:0.35rem;justify-content:center;margin-bottom:0.4rem}
.tag{padding:0.2rem 0.6rem;border-radius:4px;color:#fff;font-size:0.7rem;font-weight:600}
.layer-desc{font-size:0.72rem;color:#bee3f8;margin-top:0.3rem}
.infra-bar{background:#2d3748;border-radius:6px;padding:0.4rem;text-align:center;font-size:0.72rem;color:#fff;margin-top:0.3rem}
.note-sm{font-size:0.68rem;color:#a0aec0;text-align:center}
.note-sm.white{color:rgba(255,255,255,0.7)}
.note-pink{font-size:0.72rem;color:#febdbd;margin-top:0.6rem;line-height:1.5}

/* ── Architecture (slide 4) ────────────────────────────── */
.arch-layer{border-radius:8px;padding:0.5rem 0.7rem;margin-bottom:0.4rem}
.arch-layer.half{flex:1}
.arch-split{display:flex;gap:0.5rem;margin-bottom:0.4rem}
.layer-label{font-weight:700;font-size:0.8rem;display:block;margin-bottom:0.2rem}
.layer-label.gold{color:#d69e2e} .layer-label.mint{color:#48bb78}
.layer-label.lilac{color:#d6bcfa} .layer-label.salmon{color:#fc8181}
.layer-info{font-size:0.72rem;color:#fff;margin-bottom:0.3rem}
.tech-row{display:flex;flex-wrap:wrap;gap:0.3rem}
.tech-tag{padding:0.15rem 0.5rem;border-radius:4px;font-size:0.65rem;font-weight:600;background:#2d3748}
.tech-tag.sky{color:#63b3ed} .tech-tag.mint{color:#48bb78}
.arch-desc{font-size:0.68rem;color:#fff;line-height:1.5}

/* ── DB grid (slide 5) ─────────────────────────────────── */
.db-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:0.4rem;flex:1}
.db-card{background:#2d3748;border-radius:6px;padding:0.4rem 0.5rem;border-left:3px solid}
.db-name{display:block;font-size:0.75rem;font-weight:700}
.db-desc{display:block;font-size:0.62rem;color:#fff;margin-top:0.1rem}

/* ── Pipeline steps (slide 6) ──────────────────────────── */
.step-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:0.35rem;flex:1}
.step-card{background:#2d3748;border-radius:8px;padding:0.5rem;text-align:center;border-top:3px solid;display:flex;flex-direction:column;justify-content:center}
.step-num{font-size:1.5rem;font-weight:800}
.step-name{font-size:0.72rem;font-weight:700;color:#fff;margin:0.2rem 0}
.step-desc{font-size:0.6rem;color:#bee3f8}

/* ── Reports (slide 11) ────────────────────────────────── */
.report-grid{display:grid;grid-template-columns:1fr 1fr;gap:0.3rem 1.5rem}
.report-row{display:flex;gap:0.5rem;font-size:0.72rem;padding:0.15rem 0}
.report-fmt{font-weight:700;color:#1a365d;min-width:9rem}
.report-desc{color:#4a5568}

/* ── Security Thai bar (slide 12) ──────────────────────── */
.thai-bar{background:#2d3748;border:1px solid #d69e2e;border-radius:8px;padding:0.5rem;text-align:center;margin-top:0.5rem}
.thai-bar p{font-size:0.72rem;color:#fff;line-height:1.5}

/* ── Infrastructure (slide 14) ─────────────────────────── */
.infra-tree{font-family:'SF Mono','Fira Code',monospace;font-size:0.68rem;color:#fff;line-height:1.6;white-space:pre;background:transparent;border:none;padding:0.3rem}

/* ── Roadmap (slide 15) ────────────────────────────────── */
.road-year-marks{display:flex;justify-content:space-between;padding:0 2rem;margin-bottom:0.3rem}
.road-year-marks span{font-size:0.7rem;color:#a0aec0;font-weight:700}
.road-timeline{position:relative;padding:5rem 0 3rem;min-height:15rem}
.road-axis{position:absolute;top:50%;left:2rem;right:2rem;height:3px;background:#4a5568;transform:translateY(-50%)}
.road-phases{display:grid;grid-template-columns:repeat(4,1fr);gap:0.4rem;position:relative;z-index:1}
.road-phase{display:flex;flex-direction:column;align-items:center;text-align:center}
.road-deliverables{margin-bottom:0.3rem}
.road-deliverables ul{list-style:none;font-size:0.6rem;color:#fff;line-height:1.4;background:#2d3748;border-radius:6px;padding:0.3rem 0.5rem;text-align:left}
.road-deliverables li::before{content:'● ';font-size:0.5rem}
.road-bar{border-radius:6px;padding:0.25rem 0.4rem;min-width:100%;margin-bottom:0.2rem}
.road-name{display:block;font-size:0.72rem;font-weight:700;color:#fff}
.road-sub{display:block;font-size:0.58rem;color:rgba(255,255,255,0.8)}
.road-diamond{width:12px;height:12px;transform:rotate(45deg);margin:0.15rem 0}
.road-badge{border:2px solid;border-radius:6px;padding:0.1rem 0.5rem;font-size:0.7rem;font-weight:700;background:#2d3748}
.road-time{font-size:0.6rem;color:#a0aec0;margin-top:0.15rem}
.road-total{display:flex;justify-content:space-between;align-items:center;background:#2d3748;border:2px solid #d69e2e;border-radius:8px;padding:0.4rem 0.8rem;margin-top:0.5rem}
.road-total-label{font-size:0.9rem;font-weight:700;color:#fff}
.road-total-val{font-size:0.85rem;font-weight:700;color:#d69e2e}

/* ── Budget (slide 16) ─────────────────────────────────── */
.budget-list{flex:1;display:flex;flex-direction:column;gap:0.4rem}
.budget-phase{background:#fff8e8;border-radius:8px;padding:0.5rem 0.7rem}
.budget-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem}
.budget-phase-name{font-size:0.8rem;font-weight:700}
.budget-total-badge{padding:0.2rem 0.7rem;border-radius:6px;font-size:0.85rem;font-weight:700;color:#fff}
.budget-item{display:flex;justify-content:space-between;font-size:0.7rem;padding:0.1rem 0.3rem;color:#1a202c}
.budget-cost{color:#4a5568}
.budget-grand{display:flex;justify-content:space-between;align-items:center;background:#1a202c;border-radius:8px;padding:0.5rem 0.8rem;margin-top:0.4rem}
.budget-grand-label{font-size:1rem;font-weight:700;color:#fff}
.budget-grand-val{font-size:1.3rem;font-weight:800;color:#d69e2e}

/* ── Highlights (slide 17) ─────────────────────────────── */
.highlights-list{display:flex;flex-direction:column;gap:0.6rem;flex:1}
.highlight-card{display:flex;border-radius:8px;overflow:hidden;background:#fff}
.highlight-bar{width:6px;flex-shrink:0}
.highlight-body{padding:0.5rem 0.8rem}
.highlight-title{font-size:1rem;font-weight:700;margin-bottom:0.2rem}
.highlight-desc{font-size:0.78rem;color:#4a5568;line-height:1.5}

/* ── Comparison table (slide 18) ───────────────────────── */
.comp-table-wrap{flex:1;overflow:auto}
.comp-table{width:100%;border-collapse:collapse;font-size:0.72rem}
.comp-table th{background:#1a365d;color:#fff;padding:0.35rem 0.4rem;text-align:center;font-weight:700}
.comp-table th:first-child{text-align:left}
.comp-table td{padding:0.3rem 0.4rem;text-align:center;border-bottom:1px solid #e2e8f0}
.comp-table tr:nth-child(even){background:#edf2f7}
.comp-label{font-weight:700;text-align:left!important}
.comp-green{color:#38a169;font-weight:600}
.comp-red{color:#e53e3e}
.comp-gold{color:#b7791f}

/* ── Stats (slide 19) ──────────────────────────────────── */
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;flex:1}
.stat-card{background:#2d3748;border-radius:8px;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:0.6rem}
.stat-num{font-size:1.7rem;font-weight:800}
.stat-label{font-size:0.72rem;color:#fff;margin-top:0.2rem}

/* ── ROI (slide 20) ────────────────────────────────────── */
.roi-list{display:flex;flex-direction:column;gap:0.6rem;flex:1;justify-content:center}
.roi-row{display:flex;align-items:center;gap:0.6rem}
.roi-label{min-width:7rem;font-size:0.9rem;font-weight:700;color:#fff;text-align:right}
.roi-bar-bg{flex:1;background:#22543d;border-radius:6px;height:2rem;position:relative;overflow:hidden}
.roi-bar-fill{height:100%;border-radius:6px;transition:width 0.8s}
.roi-bar-text{position:absolute;top:50%;left:0.6rem;transform:translateY(-50%);font-size:0.72rem;font-weight:600;color:#1a202c;white-space:nowrap}
.roi-bottom{background:#22543d;border-radius:8px;padding:0.5rem;text-align:center;font-size:1rem;font-weight:700;color:#fff;margin-top:0.5rem}

/* ── User table (slide 21) ─────────────────────────────── */
.user-table{width:100%;border-collapse:collapse;font-size:0.75rem;margin-top:0.3rem}
.user-table th{background:#1a365d;color:#fff;padding:0.3rem;text-align:center}
.user-table th:first-child{text-align:left}
.user-table td{padding:0.3rem;text-align:center;border-bottom:1px solid #e2e8f0}
.user-table td:first-child{font-weight:700;text-align:left}
.user-table tr:nth-child(even){background:#edf2f7}

/* ── Closing (slide 22) ───────────────────────────────── */
.closing-slide{justify-content:center;align-items:center;text-align:center}
.close-steps{display:flex;flex-direction:column;gap:0.5rem;margin:1rem 0;text-align:left;max-width:42rem;width:100%}
.close-step{display:flex;align-items:center;gap:0.6rem}
.close-num{font-size:1.4rem;font-weight:800;min-width:2rem;text-align:right}
.close-text{font-size:1rem;color:#fff}
.close-highlight{background:#1e3a5f;border-radius:8px;padding:0.5rem 1rem;font-size:0.9rem;font-weight:700;color:#d69e2e;margin:0.5rem 0}
.close-contact{font-size:0.72rem;color:#a0aec0;margin-top:0.5rem}

/* ── Progress bar ──────────────────────────────────────── */
#progress{position:fixed;top:0;left:0;height:3px;background:#d69e2e;z-index:100;transition:width 0.3s}

/* ── Slide counter ─────────────────────────────────────── */
#counter{position:fixed;bottom:12px;right:20px;font-size:0.75rem;color:rgba(255,255,255,0.6);z-index:100;user-select:none}

/* ── Nav buttons ───────────────────────────────────────── */
.nav-btn{
  position:fixed;top:50%;transform:translateY(-50%);
  z-index:100;background:rgba(0,0,0,0.3);color:#fff;
  border:none;padding:0.7rem 0.5rem;cursor:pointer;
  font-size:1.2rem;border-radius:6px;opacity:0.5;transition:opacity 0.2s;
}
.nav-btn:hover{opacity:1}
#prev-btn{left:8px}
#next-btn{right:8px}

/* ── Mobile responsive ─────────────────────────────────── */
@media(max-width:1024px){
  .slide-inner{padding:24px 28px}
  .three-col{grid-template-columns:1fr 1fr}
  .db-grid{grid-template-columns:repeat(3,1fr)}
  .step-grid{grid-template-columns:repeat(4,1fr)}
  .stat-grid{grid-template-columns:repeat(3,1fr)}
  .mod-row{grid-template-columns:repeat(2,1fr)}
  .road-phases{grid-template-columns:repeat(2,1fr)}
  .comp-table{font-size:0.65rem}
}
@media(max-width:640px){
  .slide-inner{padding:16px 18px}
  .two-col,.three-col{grid-template-columns:1fr}
  .db-grid{grid-template-columns:repeat(2,1fr)}
  .step-grid{grid-template-columns:repeat(3,1fr)}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
  .arch-split{flex-direction:column}
  .mod-row{grid-template-columns:1fr 1fr}
  .road-phases{grid-template-columns:1fr 1fr}
  .mega{font-size:2rem}
  .slide-title{font-size:1.2rem}
  .nav-btn{padding:0.4rem 0.3rem;font-size:1rem}
  body{overflow-y:auto}
  section.slide{position:relative;height:auto;min-height:100vh;display:flex!important}
  .slides-wrapper{height:auto;overflow:auto}
  #progress,#counter,.nav-btn{display:none}
}

/* ── Print / PDF ───────────────────────────────────────── */
@media print{
  body{overflow:visible;background:#fff}
  .slides-wrapper{height:auto;overflow:visible}
  section.slide{
    position:relative!important;display:flex!important;
    width:297mm;height:210mm;
    page-break-after:always;page-break-inside:avoid;
    -webkit-print-color-adjust:exact;print-color-adjust:exact;
  }
  section.slide:last-child{page-break-after:auto}
  .slide-inner{overflow:hidden}
  #progress,#counter,.nav-btn{display:none}
}
@page{size:A4 landscape;margin:0}
"""


# ══════════════════════════════════════════════════════════════
#  JavaScript — navigation, keyboard, swipe
# ══════════════════════════════════════════════════════════════

JS = r"""
(function(){
  const slides = document.querySelectorAll('.slide');
  const total = slides.length;
  let current = 0;

  const progress = document.getElementById('progress');
  const counter = document.getElementById('counter');

  function show(n){
    if(n<0||n>=total)return;
    slides[current].classList.remove('active');
    current = n;
    slides[current].classList.add('active');
    progress.style.width = ((current+1)/total*100)+'%';
    counter.textContent = (current+1)+' / '+total;
  }

  function next(){show(current+1)}
  function prev(){show(current-1)}

  // Keyboard
  document.addEventListener('keydown',function(e){
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown')next();
    else if(e.key==='ArrowLeft'||e.key==='PageUp')prev();
    else if(e.key==='Home')show(0);
    else if(e.key==='End')show(total-1);
    else if(e.key==='f'||e.key==='F'){
      if(!document.fullscreenElement)document.documentElement.requestFullscreen();
      else document.exitFullscreen();
    }
  });

  // Nav buttons
  document.getElementById('prev-btn').onclick = prev;
  document.getElementById('next-btn').onclick = next;

  // Touch swipe (distinguish from scroll)
  let startX=0, startY=0, startTime=0;
  document.addEventListener('touchstart',function(e){
    startX=e.changedTouches[0].clientX;
    startY=e.changedTouches[0].clientY;
    startTime=Date.now();
  },{passive:true});
  document.addEventListener('touchend',function(e){
    const dx=e.changedTouches[0].clientX-startX;
    const dy=e.changedTouches[0].clientY-startY;
    const dt=Date.now()-startTime;
    if(dt>500)return; // too slow
    if(Math.abs(dx)>Math.abs(dy)*1.5 && Math.abs(dx)>50){
      if(dx<0)next(); else prev();
    }
  },{passive:true});

  // Init
  show(0);
})();
"""


# ══════════════════════════════════════════════════════════════
#  HTML assembly
# ══════════════════════════════════════════════════════════════

def build_html() -> str:
    slides = _slides_html()
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SPNI Platform — BSIE v4.0 Presentation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div id="progress"></div>
<div class="slides-wrapper">
{slides}
</div>
<button class="nav-btn" id="prev-btn" aria-label="Previous">&#9664;</button>
<button class="nav-btn" id="next-btn" aria-label="Next">&#9654;</button>
<div id="counter"></div>
<script>{JS}</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════
#  PDF generation via weasyprint
# ══════════════════════════════════════════════════════════════

def generate_pdf(html_path: Path, pdf_path: Path) -> None:
    from weasyprint import HTML  # type: ignore[import-untyped]
    print("  Generating PDF (this may take a moment)...")
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    print(f"  PDF saved: {pdf_path}")


# ══════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════

def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    # 1. Generate HTML
    html_content = build_html()
    HTML_OUT.write_text(html_content, encoding="utf-8")
    print(f"HTML saved: {HTML_OUT}")

    # 2. Generate PDF
    generate_pdf(HTML_OUT, PDF_OUT)

    print(f"\nDone! Files created:")
    print(f"  1. {HTML_OUT}")
    print(f"  2. {PDF_OUT}")


if __name__ == "__main__":
    main()
