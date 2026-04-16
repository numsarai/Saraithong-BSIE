"""
generate_pdf.py — SPNI/BSIE Presentation PDF (A4 Landscape)
Uses fpdf2 + TH Sarabun New. 22 pages matching PPTX content.
"""

from pathlib import Path
from fpdf import FPDF

BASE = Path(__file__).parent.parent
FONT_DIR = BASE / "static" / "fonts"
FONT_REG = str(FONT_DIR / "THSarabunNew.ttf")
FONT_BOLD = str(FONT_DIR / "THSarabunNew Bold.ttf")

# -- Colors --
NAVY   = (26, 54, 93)
BLUE   = (43, 108, 176)
SKY    = (99, 179, 237)
GREEN  = (56, 161, 105)
DGREEN = (34, 84, 61)
MINT   = (72, 187, 120)
RED    = (229, 62, 62)
DRED   = (197, 48, 48)
SALMON = (252, 129, 129)
ORANGE = (221, 107, 32)
GOLD   = (214, 158, 46)
LGOLD  = (236, 201, 75)
PURPLE = (128, 90, 213)
LILAC  = (214, 188, 250)
WHITE  = (255, 255, 255)
LGRAY  = (247, 250, 252)
MGRAY  = (237, 242, 247)
DGRAY  = (45, 55, 72)
VDARK  = (26, 32, 44)
TXT    = (26, 32, 44)
TXTL   = (74, 85, 104)
SUBTLE = (160, 174, 192)

# A4 Landscape
PW = 297  # mm
PH = 210  # mm
MX = 12   # margin
CW = PW - MX * 2  # content width


class SlidePDF(FPDF):
    def __init__(self):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.add_font('th', '', FONT_REG)
        self.add_font('th', 'B', FONT_BOLD)
        self.set_auto_page_break(auto=False)

    def new_slide(self, bg=LGRAY):
        self.add_page()
        self.set_fill_color(*bg)
        self.rect(0, 0, PW, PH, 'F')

    def slide_title(self, text, color=NAVY):
        self.set_font('th', 'B', 22)
        self.set_text_color(*color)
        self.set_xy(MX, 6)
        self.cell(CW, 12, text, align='C')

    def subtitle(self, text, color=TXTL, y=18):
        self.set_font('th', '', 12)
        self.set_text_color(*color)
        self.set_xy(MX, y)
        self.cell(CW, 6, text, align='C')

    def card(self, x, y, w, h, fill=WHITE, border_color=None):
        self.set_fill_color(*fill)
        self.rect(x, y, w, h, 'F')
        if border_color:
            self.set_draw_color(*border_color)
            self.set_line_width(0.5)
            self.rect(x, y, w, h, 'D')

    def card_title(self, x, y, w, text, color=NAVY, size=14):
        self.set_font('th', 'B', size)
        self.set_text_color(*color)
        self.set_xy(x + 3, y + 2)
        self.cell(w - 6, 7, text)

    def bullet_list(self, x, y, w, items, size=11, color=TXT, bc=GREEN, lh=6):
        yy = y
        for item in items:
            if yy > PH - 10:
                break
            self.set_font('th', '', size - 1)
            self.set_text_color(*bc)
            self.set_xy(x, yy)
            self.cell(4, lh, '>')
            # parse **bold**
            parts = item.split('**')
            self.set_xy(x + 5, yy)
            for j, part in enumerate(parts):
                if not part:
                    continue
                self.set_font('th', 'B' if j % 2 == 1 else '', size)
                self.set_text_color(*color)
                self.cell(self.get_string_width(part), lh, part)
            yy += lh
        return yy

    def text_block(self, x, y, w, text, size=11, color=TXT, bold=False, align='L'):
        self.set_font('th', 'B' if bold else '', size)
        self.set_text_color(*color)
        self.set_xy(x, y)
        self.multi_cell(w, 5, text, align=align)


def generate():
    pdf = SlidePDF()
    hw = (CW - 4) / 2
    tw = (CW - 8) / 3

    # ════════════ 1. TITLE ════════════
    pdf.new_slide(NAVY)
    pdf.text_block(MX, 20, CW, 'สำนักงานตำรวจแห่งชาติ', 12, SUBTLE, align='C')
    pdf.text_block(MX, 35, CW, 'SPNI Platform', 40, WHITE, True, 'C')
    pdf.text_block(MX, 60, CW, 'Smart Police & National Intelligence', 20, SKY, align='C')
    pdf.set_fill_color(*GOLD)
    pdf.rect(PW/2-15, 80, 30, 1, 'F')
    pdf.text_block(MX, 88, CW, 'โมดูลแรก: BSIE v4.1 — Bank Statement Intelligence Engine', 16, WHITE, align='C')
    pdf.text_block(MX, 100, CW, 'ระบบวิเคราะห์ธุรกรรมทางการเงินอัจฉริยะ สำหรับงานสืบสวนสอบสวน', 14, (190,227,248), align='C')
    pdf.text_block(MX, 140, CW, 'เอกสารประกอบการนำเสนอเพื่อของบประมาณระดับประเทศ\nจัดทำโดย ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง\nเมษายน 2569', 12, SUBTLE, align='C')

    # ════════════ 2. SPNI VISION ════════════
    pdf.new_slide(NAVY)
    pdf.slide_title('SPNI Platform — ภาพรวม 4 โมดูล', WHITE)
    pdf.subtitle('แพลตฟอร์มรวมเครื่องมือสืบสวนสอบสวนสำหรับ สตช. ทั้งประเทศ', (190,227,248))

    mods = [('โมดูล 1', 'BSIE — การเงิน', 'v4.1 *', MINT),
            ('โมดูล 2', 'CDR — โทรศัพท์', 'วางแผน', DGRAY),
            ('โมดูล 3', 'Social Media', 'วางแผน', DGRAY),
            ('โมดูล 4', 'CCTV ภาพ/วีดีโอ', 'วางแผน', DGRAY)]
    mw = (CW - 12) / 4
    for i, (num, name, status, bg) in enumerate(mods):
        x = MX + i * (mw + 4)
        pdf.card(x, 30, mw, 28, bg)
        pdf.text_block(x, 31, mw, num, 9, SUBTLE, align='C')
        pdf.text_block(x, 37, mw, name, 13, WHITE, True, 'C')
        pdf.text_block(x, 48, mw, status, 10, GOLD if i==0 else SUBTLE, align='C')

    pdf.card(MX, 65, CW, 25, (30,58,95))
    pdf.text_block(MX, 66, CW, 'Shared Intelligence Layer', 13, WHITE, True, 'C')
    tags = ['Entity Registry', 'Link Analysis', 'Case Mgmt', 'Local LLM AI', 'Evidence Chain', 'Regulatory']
    tw_t = (CW - 24) / 6
    for i, tag in enumerate(tags):
        x = MX + 4 + i * (tw_t + 4)
        colors = [GREEN, BLUE, ORANGE, RED, PURPLE, GOLD]
        pdf.card(x, 76, tw_t, 8, colors[i])
        pdf.text_block(x, 76.5, tw_t, tag, 9, WHITE, True, 'C')

    pdf.card(MX, 95, CW, 10, DGRAY)
    pdf.text_block(MX, 96, CW, 'Infrastructure: On-Premise Server | Local LLM (Ollama) | PostgreSQL | VPN/HTTPS | ห้าม Cloud AI', 10, WHITE, align='C')

    pdf.text_block(MX, 115, CW,
        'ทำไมเริ่มจาก BSIE?  1) คดีการเงินมากที่สุด  2) ข้อมูลมีโครงสร้างชัดเจน  3) เห็นผลเร็ว — 3 วัน->30 นาที  4) พื้นฐานสำหรับโมดูลอื่น', 10, SUBTLE, align='C')

    # ════════════ 3. PROBLEM ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('ปัญหาการสืบสวนทางการเงินในปัจจุบัน')

    pdf.card(MX, 24, hw, 160, WHITE, RED)
    pdf.card_title(MX, 24, hw, 'ปัญหาที่พบ', RED)
    pdf.bullet_list(MX+3, 35, hw-6, [
        'วิเคราะห์ Statement **ด้วยมือ** ใช้เวลา **3-5 วัน**ต่อคดี',
        'ดูได้**ทีละบัญชี** ไม่เห็น**ภาพรวมเครือข่าย**',
        'ใช้ Excel ธรรมดา ไม่มีเครื่องมือ**วิเคราะห์เฉพาะทาง**',
        'i2 ราคา **500,000+ บาท/license/ปี** ไม่รองรับไทย',
        'ไม่มีมาตรฐาน**รายงาน ปปง.** (STR/CTR)',
        'ไม่มีระบบ**แจ้งเตือนอัตโนมัติ** — พลาดได้ง่าย',
        'ข้อมูลกระจาย**หลาย Excel** ไม่เชื่อมโยง',
        '**ไม่มีเครื่องมือฟรี**ที่ดีสำหรับตำรวจไทย',
    ], bc=RED)

    rx = MX + hw + 4
    pdf.card(rx, 24, hw, 160, WHITE, GREEN)
    pdf.card_title(rx, 24, hw, 'BSIE แก้ได้', GREEN)
    pdf.bullet_list(rx+3, 35, hw-6, [
        'ประมวลผลอัตโนมัติ **ภายใน 30 นาที**',
        'เชื่อมโยงข้ามบัญชี **เห็นเครือข่าย**ทั้งหมด',
        'กราฟเครือข่าย Timeline **แจ้งเตือน 12 รูปแบบ**',
        'มี **mini i2** ในตัว — **ฟรี**',
        'สร้างรายงาน **PDF/Excel/STR/CTR** ตามมาตรฐาน',
        '**ตรวจจับ 5 รูปแบบฟอกเงิน** FATF อัตโนมัติ',
        'วิเคราะห์สถิติ: **Z-score, IQR, Benford**',
        'ฟรี — **ไม่มีค่า license** รองรับ**ทั้งประเทศ**',
    ])

    # ════════════ 4. ARCHITECTURE ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('สถาปัตยกรรมระบบ BSIE v4.1', WHITE)

    pdf.card(MX, 24, CW, 22, (32,64,112))
    pdf.card_title(MX, 24, CW, 'Frontend', GOLD, 12)
    pdf.text_block(MX+30, 25.5, CW-35, 'React 19 | TypeScript | Vite | Tailwind CSS | Zustand | Cytoscape.js | Recharts | react-i18next', 10, SKY)

    pdf.card(MX, 50, CW, 22, (21,53,37))
    pdf.card_title(MX, 50, CW, 'Backend', MINT, 12)
    pdf.text_block(MX+30, 51.5, CW-35, 'Python 3.12 | FastAPI | 21 Routers | 34 Services | 120+ Endpoints', 10, WHITE)

    pdf.card(MX, 76, hw, 22, (53,37,21))
    pdf.card_title(MX, 76, hw, 'Processing Core — 30 modules', GOLD, 11)
    pdf.text_block(MX+3, 86, hw-6, 'bank_detector, column_detector, nlp_engine, normalizer, classifier, link_builder, graph_rules, pdf_loader, image_loader (OCR), exporter, llm_agent...', 9, WHITE)

    pdf.card(rx, 76, hw, 22, (37,21,53))
    pdf.card_title(rx, 76, hw, '34 Services', LILAC, 11)
    pdf.text_block(rx+3, 86, hw-6, 'alert, anomaly_detection, sna, threat_hunting, fund_flow, auth, regulatory_export, report, insights, case_tapestry, job_queue, audit...', 9, WHITE)

    pdf.card(MX, 102, hw, 16, (21,37,21))
    pdf.card_title(MX, 102, hw, 'Database: SQLAlchemy 2 + SQLite WAL', MINT, 11)
    pdf.text_block(MX+3, 111, hw-6, '20 tables | Alembic migrations | Optimized pragmas | -> PostgreSQL (Phase 2)', 9, WHITE)

    pdf.card(rx, 102, hw, 16, (37,21,21))
    pdf.card_title(rx, 102, hw, 'AI/ML: Local LLM + NLP', SALMON, 11)
    pdf.text_block(rx+3, 111, hw-6, 'EasyOCR (Thai+EN) | NLP (ชื่อ/เบอร์/บัตร ปชช./PromptPay) | Ollama', 9, WHITE)

    # ════════════ 5. DATABASE ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('ฐานข้อมูล — 20 Tables', WHITE)

    tables = [
        ('FileRecord', 'ไฟล์อัพโหลด + SHA-256', GREEN),
        ('ParserRun', 'ประวัติการประมวลผล', GREEN),
        ('Account', 'บัญชี (normalized)', BLUE),
        ('Transaction', 'ธุรกรรม 30+ fields', BLUE),
        ('StatementBatch', 'ชุดรายการเดินบัญชี', GREEN),
        ('RawImportRow', 'ข้อมูลดิบ forensic', GREEN),
        ('Entity', 'บุคคล/นิติบุคคล', PURPLE),
        ('AccountEntityLink', 'เชื่อม Acct<->Entity', PURPLE),
        ('TransactionMatch', 'จับคู่ข้ามบัญชี', ORANGE),
        ('Alert', 'แจ้งเตือน + severity', RED),
        ('DuplicateGroup', 'กลุ่มข้อมูลซ้ำ', ORANGE),
        ('ReviewDecision', 'การตัดสินใจ analyst', GOLD),
        ('AuditLog', 'Audit Trail', GOLD),
        ('ExportJob', 'งานส่งออก', SKY),
        ('User', 'ผู้ใช้ JWT+RBAC', SALMON),
        ('AdminSetting', 'ตั้งค่า+Workspace', TXTL),
        ('GraphAnnotation', 'บันทึกบน node', LILAC),
        ('CaseTag', 'แท็กคดี', MINT),
        ('CaseTagLink', 'เชื่อม tag<->วัตถุ', MINT),
        ('MappingProfile', 'โปรไฟล์ mapping', GREEN),
    ]
    cw_d = (CW - 12) / 4
    for i, (name, desc, clr) in enumerate(tables):
        col, row = i % 4, i // 4
        x = MX + col * (cw_d + 4)
        y = 24 + row * 18
        pdf.card(x, y, cw_d, 16, DGRAY, clr)
        pdf.set_font('th', 'B', 10); pdf.set_text_color(*clr)
        pdf.set_xy(x+2, y+1); pdf.cell(cw_d-4, 6, name)
        pdf.set_font('th', '', 9); pdf.set_text_color(*WHITE)
        pdf.set_xy(x+2, y+8); pdf.cell(cw_d-4, 6, desc)

    # ════════════ 6. PIPELINE ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('Processing Pipeline — 14 ขั้นตอน', WHITE)

    steps = [
        ('1','Load File','Excel/PDF/Image/OFX',GREEN),('2','Detect Bank','8 ธนาคาร auto',GREEN),
        ('3','Detect Cols','Fuzzy 3-tier',BLUE),('4','Load Memory','Profile ที่จำไว้',BLUE),
        ('5','Apply Map','แปลงคอลัมน์',SKY),('6','Normalize','วันที่/เงิน/ทิศทาง',SKY),
        ('7','Parse Acct','แยกเลข normalize',ORANGE),('8','Extract Desc','แยกรายละเอียด',ORANGE),
        ('9','NLP Enrich','ชื่อ/เบอร์/ID/PP',PURPLE),('10','Classify','IN/OUT/TRANSFER',PURPLE),
        ('11','Build Links','from->to accounts',GOLD),('12','Overrides','แก้ไขจาก analyst',GOLD),
        ('13','Build Entity','สร้าง Entity list',SALMON),('14','Export','Account Package',SALMON),
    ]
    sw = (CW - 24) / 7
    for i, (num, name, desc, clr) in enumerate(steps):
        col, row = i % 7, i // 7
        x = MX + col * (sw + 4)
        y = 24 + row * 50
        pdf.card(x, y, sw, 44, DGRAY, clr)
        pdf.text_block(x, y+3, sw, num, 20, clr, True, 'C')
        pdf.text_block(x, y+16, sw, name, 10, WHITE, True, 'C')
        pdf.text_block(x+2, y+26, sw-4, desc, 9, (190,227,248), align='C')

    # ════════════ 7. DATA INTAKE ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('การนำเข้าข้อมูล — ครบทุกรูปแบบ')

    intake = [
        ('8 ธนาคารไทย Auto-detect', [
            '**SCB** — ไทยพาณิชย์','**KBANK** — กสิกรไทย',
            '**BBL** — กรุงเทพ','**KTB** — กรุงไทย',
            '**BAY** — กรุงศรี','**TTB** — ทหารไทยธนชาต',
            '**GSB** — ออมสิน','**BAAC** — ธ.ก.ส.',
        ]),
        ('รูปแบบไฟล์ + OCR', [
            '**Excel** (.xlsx/.xls)','**PDF** ข้อความ — pdfplumber',
            '**PDF สแกน** — EasyOCR','**รูปภาพ** JPG/PNG/BMP',
            '**OFX** — ธนาคารออนไลน์','**SHA-256** ตรวจจับซ้ำ',
        ]),
        ('Smart Column Mapping', [
            '**3-tier Fuzzy** exact->alias->fuzzy',
            '**Self-learning** จำ profile','**Body keywords** ตรวจเนื้อหา',
            '**Re-process** mapping ผิด?ทำใหม่','**NLP** ชื่อ/เบอร์/บัตร/PromptPay',
        ]),
    ]
    for i, (t_, items) in enumerate(intake):
        x = MX + i * (tw + 4)
        pdf.card(x, 24, tw, 165, WHITE)
        pdf.card_title(x, 24, tw, t_)
        pdf.bullet_list(x+3, 35, tw-6, items, size=10, lh=5.5)

    # ════════════ 8. LINK CHART ════════════
    pdf.new_slide(NAVY)
    pdf.slide_title('กราฟเครือข่าย — mini i2 Analyst\'s Notebook', WHITE)

    pdf.card(MX, 24, hw, 155, (30,58,95))
    pdf.card_title(MX, 24, hw, 'Multi-hop Link Chart', GOLD, 13)
    pdf.bullet_list(MX+3, 35, hw-6, [
        'กดขยายเครือข่าย**ทีละชั้น ไม่จำกัดความลึก**',
        '**5 Layout**: Circle, Spread, Compact, Hierarchy, Peacock',
        '**Conditional Formatting** — ขนาด node ตามยอดเงิน',
        'สี border ตาม**ระดับความเสี่ยง**จาก alert',
        '**Edge labels** แสดง/ซ่อนยอดเงิน',
        '**Pin / Hide / Multi-select** จัดระเบียบ',
        '**Focus History** — ดูประวัติการสำรวจ',
        '**Export PNG** สำหรับรายงาน',
    ], color=WHITE, bc=GOLD, size=10)

    pdf.card(rx, 24, hw, 155, (30,58,95))
    pdf.card_title(rx, 24, hw, 'SNA + Path Tracing', GOLD, 13)
    pdf.bullet_list(rx+3, 35, hw-6, [
        '**Degree Centrality** — บัญชีเชื่อมต่อมากสุด',
        '**Betweenness** — บัญชี**ตัวกลาง** (broker)',
        '**Closeness** — เข้าถึงทุกจุดเร็วสุด',
        '**BFS Path Finder** — ตามเงิน A->B->C->D **4 ทอด**',
        '**Graph Annotations** — จดบันทึกบน node',
        '**Tags**: ผู้ต้องสงสัย, พยาน, เหยื่อ',
        '**Workspace** — บันทึก/โหลด chart state',
        '**Entity Profile** — หน้ารวมข้อมูล',
    ], color=WHITE, bc=GOLD, size=10)

    # ════════════ 9. VISUALIZATION ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('การแสดงผล — Timeline, Heatmap, Dashboard')
    for i, (t_, clr, items) in enumerate([
        ('Timeline Chart', BLUE, ['**Recharts** Bar + Dot','Granularity: **วัน/สัปดาห์/เดือน**','ดูรูปแบบตามเวลา','**ตรวจจับช่วงเวลาผิดปกติ**']),
        ('Time Wheel Heatmap', PURPLE, ['**Custom SVG** Hour×Day','24 ชม. × 7 วัน = **168 ช่อง**','สีตามความถี่','**ตรวจจับเวลาผิดปกติ**']),
        ('Dashboard', GREEN, ['**สรุปภาพรวม** สถิติ เงินเข้า/ออก','**Recent Activity**','**Top Accounts**','**Code-split** React.lazy']),
    ]):
        x = MX + i * (tw + 4)
        pdf.card(x, 24, tw, 80, WHITE, clr)
        pdf.card_title(x, 24, tw, t_, clr, 13)
        pdf.bullet_list(x+3, 35, tw-6, items, size=10)

    # ════════════ 10. ALERTS ════════════
    pdf.new_slide(ORANGE)
    pdf.slide_title('ระบบแจ้งเตือนอัตโนมัติ — 12 รูปแบบ', WHITE)
    for i, (t_, items) in enumerate([
        ('7 กฎกราฟเครือข่าย', ['**Repeated Transfers** คู่เดิม ≥3','**Fan-in** เงินเข้า ≥3 แหล่ง','**Fan-out** เงินออก ≥3 เป้า','**Circular** วงจรเงิน A<>B','**Pass-through** รับแล้วโอนต่อ','**Hub** เชื่อม ≥6 บัญชี','**Repeated CP** คนเดิมหลายวัน']),
        ('5 รูปแบบฟอกเงิน FATF', ['**Smurfing** แบ่งรายการย่อย','**Layering** สร้างชั้นซ้อน','**Rapid Movement** เข้า-ออก 24 ชม.','**Dormant Activation** นิ่ง->ใช้','**Round-tripping** วนกลับ']),
        ('4 วิธีทางสถิติ', ['**Z-score** เบี่ยงเบน >Ns','**IQR** นอก Q1-1.5×IQR','**Benford** หลักแรกผิดปกติ','**Moving Average** เบี่ยงจาก 30 รายการ']),
    ]):
        x = MX + i * (tw + 4)
        pdf.card(x, 24, tw, 155, (156,78,24))
        pdf.card_title(x, 24, tw, t_, LGOLD, 12)
        pdf.bullet_list(x+3, 35, tw-6, items, color=WHITE, bc=LGOLD, size=10, lh=5.5)

    # ════════════ 11. CROSS-ACCOUNT + REPORTS ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('การวิเคราะห์ข้ามบัญชี + Investigation Desk + รายงาน')
    pdf.card(MX, 24, hw, 50, WHITE, BLUE)
    pdf.card_title(MX, 24, hw, 'Cross-Account Analysis', BLUE, 13)
    pdf.bullet_list(MX+3, 35, hw-6, ['**Fund Flow** ดูเงินเข้า/ออก','**Pairwise** ธุรกรรมระหว่าง 2 บัญชี','**BFS** ตามเงิน A->B->C->D 4 ทอด','**Bulk Cross-Match** จับคู่ข้ามทุกบัญชี','**Multi-period** เปรียบเทียบ 2 ช่วงเวลา'], size=10)

    pdf.card(rx, 24, hw, 50, WHITE, PURPLE)
    pdf.card_title(rx, 24, hw, 'Investigation Desk — 13 แท็บ', PURPLE, 13)
    pdf.bullet_list(rx+3, 35, hw-6, ['Database | Files | Parser Runs | **Accounts** | **Search**','**Alerts** | **Cross-Account** | **Link Chart** | **Timeline**','Duplicates | Matches | **Audit** | **Exports**'], size=10, bc=PURPLE)

    pdf.card(MX, 80, CW, 85, WHITE, GOLD)
    pdf.card_title(MX, 80, CW, 'รายงาน 6 รูปแบบ', GOLD, 13)
    for i, (fmt, desc) in enumerate([
        ('Excel (.xlsx)', '14+ ชีท, TH Sarabun New, สี, สูตร, auto-filter'),
        ('PDF', 'ปก + สถิติ + คู่สัญญา + alerts + ช่องลงนาม'),
        ('i2 Chart (.anx)', 'เปิดใน Analyst\'s Notebook ทันที'),
        ('i2 Import', 'CSV 29 col + XML spec สำหรับ import'),
        ('STR / CTR', 'รายงาน ปปง. พร้อมส่ง'),
        ('CSV', 'transactions, entities, links, graph data'),
    ]):
        col, row = i % 2, i // 2
        x = MX + 3 + col * (CW / 2)
        y = 93 + row * 9
        pdf.set_font('th', 'B', 10); pdf.set_text_color(*NAVY)
        pdf.set_xy(x, y); pdf.cell(30, 6, fmt)
        pdf.set_font('th', '', 9); pdf.set_text_color(*TXTL)
        pdf.set_xy(x + 30, y); pdf.cell(100, 6, desc)

    # ════════════ 12. SECURITY ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('ความปลอดภัย, Chain of Custody, ภาษาไทย', WHITE)
    for i, (t_, clr, items) in enumerate([
        ('Authentication', SKY, ['**JWT** + 3 ระดับ: Admin/Analyst/Viewer','**PBKDF2-SHA256** 100K iterations','**Rate Limiting** 10 req/min','**Configurable** env var']),
        ('Security Headers', SALMON, ['**X-Frame-Options** DENY','**X-Content-Type-Options** nosniff','**Upload Allowlist** .xlsx/.pdf/.csv/.png','**Max Body Size** 50 MB']),
        ('Chain of Custody', GOLD, ['**Audit Trail** ใคร/ทำอะไร/เมื่อไหร่','**Chain of Custody** ครบถ้วน','**/api/audit-trail/{type}/{id}**','**SHA-256** file integrity']),
    ]):
        x = MX + i * (tw + 4)
        pdf.card(x, 24, tw, 75, DGRAY)
        pdf.card_title(x, 24, tw, t_, clr, 12)
        pdf.bullet_list(x+3, 35, tw-6, items, color=WHITE, bc=clr, size=10, lh=5.5)

    pdf.card(MX, 105, CW, 16, DGRAY, GOLD)
    pdf.text_block(MX, 107, CW, 'ภาษาไทยเต็มระบบ: UI ไทย/EN | ~500 i18n keys | TH Sarabun New | NLP ชื่อ/เบอร์/บัตร ปชช. | 244 tests', 10, WHITE, align='C')

    # ════════════ 13. LOCAL LLM ════════════
    pdf.new_slide(DRED)
    pdf.slide_title('ทำไมต้อง Local LLM — ห้ามใช้ Cloud AI', WHITE)
    pdf.card(MX, 24, hw, 140, (116,42,42))
    pdf.card_title(MX, 24, hw, 'เหตุผลความจำเป็น', SALMON, 13)
    pdf.bullet_list(MX+3, 35, hw-6, ['**ความลับทางราชการ** ระดับ \'ลับ\'/\'ลับมาก\'','**PDPA** ข้อมูลอ่อนไหว','**Training Data Risk** Cloud LLM อาจนำไปเรียนรู้','**Chain of Custody** หลักฐานต้องไม่ผ่านภายนอก','**ระเบียบ สตช.** อยู่ในโครงข่ายภายใน','**ป้องกันรั่วไหล** เลขบัญชี ชื่อ เส้นทางเงิน'], color=WHITE, bc=SALMON, size=10)

    pdf.card(rx, 24, hw, 140, (116,42,42))
    pdf.card_title(rx, 24, hw, 'Local LLM ทำอะไรได้', SALMON, 13)
    pdf.bullet_list(rx+3, 35, hw-6, ['**สรุปคดีอัตโนมัติ**','**ตอบคำถาม** เกี่ยวกับคดี','**จำแนกธุรกรรม**','**ตรวจจับรูปแบบ** ฟอกเงิน','**ร่าง STR/CTR** narrative'], color=WHITE, bc=SALMON, size=10)
    pdf.text_block(rx+3, 80, hw-6, 'แนะนำ: Ollama + Llama 3.1 70B / Typhoon\nGPU: NVIDIA RTX 4090 (24GB) / A6000 (48GB)', 9, (254,189,189))

    # ════════════ 14. INFRASTRUCTURE ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('โครงสร้างพื้นฐาน — Phase 1 ถึง 4', WHITE)
    pdf.card(MX, 24, hw, 46, DGRAY, MINT)
    pdf.card_title(MX, 24, hw, 'Phase 1: Standalone (ฟรี)', MINT, 12)
    pdf.text_block(MX+3, 35, hw-6, 'PC/Mac -> BSIE (localhost:8757)\nFastAPI + React + SQLite\nไม่ต้องใช้ server', 9, WHITE)
    pdf.card(rx, 24, hw, 46, DGRAY, SKY)
    pdf.card_title(rx, 24, hw, 'Phase 2: สถานีตำรวจ', SKY, 12)
    pdf.text_block(rx+3, 35, hw-6, 'Server จังหวัด + Nginx HTTPS\nPostgreSQL + Local LLM + GPU\nPC สอบสวน 1-30 -> Browser', 9, WHITE)

    pdf.card(MX, 76, CW, 75, DGRAY, GOLD)
    pdf.card_title(MX, 76, CW, 'Phase 3-4: ระดับจังหวัด / ภาค / ประเทศ (On-Premise)', GOLD, 12)
    pdf.text_block(MX+3, 88, hw-3, 'Data Center จังหวัด / ภาค\n  |---- Load Balancer (Nginx)\n  |---- BSIE Backend ×2-3\n  |---- PostgreSQL primary+replica\n  |---- Redis cache | NAS/SAN\n  |---- Monitoring (Prometheus+Grafana)\n  `---- Backup server', 9, WHITE)
    pdf.text_block(rx, 88, hw-3, 'Local LLM Cluster\n  |---- GPU Server ×1-2 per ภาค\n  |---- NVIDIA A6000 ×2\n  `---- Llama 3.1 70B + Typhoon\n\nเชื่อม VPN/HTTPS:\n  สถานี อ.เมือง -> VPN\n  บก.จว. -> VPN', 9, WHITE)

    # ════════════ 15. ROADMAP HORIZONTAL ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('Roadmap การพัฒนา SPNI Platform', WHITE)

    tl_y = 55
    pdf.set_fill_color(74, 85, 104)
    pdf.rect(MX, tl_y, CW, 0.8, 'F')  # timeline axis

    # Year marks
    for label, x in [('พ.ศ.2569', MX), ('2570', MX+CW*0.33), ('2571', MX+CW*0.66), ('2572+', MX+CW*0.9)]:
        pdf.set_fill_color(74, 85, 104); pdf.rect(x, tl_y-3, 0.4, 6, 'F')
        pdf.set_font('th', 'B', 8); pdf.set_text_color(*SUBTLE)
        pdf.set_xy(x-8, tl_y-9); pdf.cell(16, 5, label, align='C')

    phases_tl = [
        ('Phase 1 Pilot', 'เดือน 1-3', MX, CW*0.18, GREEN, 'ฟรี',
         ['BSIE v4.1 Pilot', 'ทดลอง 5-10 คดี', 'เก็บ feedback']),
        ('Phase 2 จังหวัด', 'เดือน 4-9', MX+CW*0.20, CW*0.22, BLUE, '~8 ล้าน',
         ['Server 5 จว.', 'PostgreSQL+LLM', 'อบรม 5 จังหวัด']),
        ('Phase 3 SPNI', 'เดือน 10-21', MX+CW*0.44, CW*0.30, ORANGE, '~40 ล้าน',
         ['CDR Module', 'Shared Layer', 'Mobile App', 'ขยาย 20 จว.']),
        ('Phase 4 ประเทศ', 'ปีที่ 3+', MX+CW*0.76, CW*0.24, RED, '~120 ล้าน',
         ['Social+CCTV', '77 จว. ทั้งประเทศ', 'Data Center ×10']),
    ]
    for label, time, x, w, clr, budget, items in phases_tl:
        # Phase bar
        pdf.card(x, tl_y - 7, w, 14, clr)
        pdf.text_block(x, tl_y - 7, w, label, 9, WHITE, True, 'C')
        pdf.text_block(x, tl_y + 1, w, time, 7, WHITE, align='C')

        # Budget badge
        bw = min(w, 28)
        pdf.card(x + (w - bw) / 2, tl_y + 10, bw, 8, DGRAY, clr)
        pdf.text_block(x + (w - bw) / 2, tl_y + 10, bw, budget, 9, clr, True, 'C')

        # Deliverables above
        ch_ = len(items) * 5 + 3
        cy = tl_y - 10 - ch_
        pdf.card(x, cy, w, ch_, DGRAY)
        for j, item in enumerate(items):
            pdf.set_font('th', '', 8); pdf.set_text_color(*WHITE)
            pdf.set_xy(x + 2, cy + 1 + j * 5); pdf.cell(w - 4, 5, '> ' + item)

    # Grand total
    pdf.card(MX, 145, CW, 12, DGRAY, GOLD)
    pdf.set_font('th', 'B', 12); pdf.set_text_color(*WHITE)
    pdf.set_xy(MX + 3, 147); pdf.cell(60, 7, 'งบประมาณรวม 3 ปี')
    pdf.set_text_color(*GOLD)
    pdf.set_xy(MX + 100, 147); pdf.cell(CW - 106, 7, '~170 ล้านบาท | ฟรี -> 8 ล้าน -> 40 ล้าน -> 120 ล้าน', align='R')

    pdf.text_block(MX, 162, CW, 'Phase 1 เริ่มได้ทันที (ฟรี) -> Phase 2 ของบหลัง pilot สำเร็จ -> Phase 3-4 ขยายตามผลลัพธ์จริง', 9, SUBTLE, align='C')

    # ════════════ 16. BUDGET ════════════
    pdf.new_slide(GOLD)
    pdf.slide_title('งบประมาณระดับประเทศ — SPNI Platform', VDARK)

    budget = [
        ('Phase 1: Pilot (3 เดือน)', [('ใช้ PC ที่มี + BSIE v4.1','ฟรี')], 'ฟรี', GREEN),
        ('Phase 2: 5 จังหวัดนำร่อง (6 เดือน)', [
            ('App Server ×5','1,500,000 ฿'),('GPU Server LLM ×5','5,000,000 ฿'),
            ('Network/UPS ×5','500,000 ฿'),('PostgreSQL+พัฒนา','500,000 ฿'),('อบรม','300,000 ฿')
        ], '~8 ล้าน', BLUE),
        ('Phase 3: SPNI + 20 จังหวัด (12 เดือน)', [
            ('CDR Module','8,000,000 ฿'),('Server+GPU ×20','20,000,000 ฿'),
            ('Shared Layer+Mobile','7,000,000 ฿'),('ทีม 5-8 คน×12 เดือน','5,000,000 ฿')
        ], '~40 ล้าน', ORANGE),
        ('Phase 4: 77 จังหวัด + 10 ภาค (ปีที่ 2-3)', [
            ('Social+CCTV Module','30,000,000 ฿'),('Data Center ×10+GPU','40,000,000 ฿'),
            ('Deploy 77 จว.','30,000,000 ฿'),('ทีม 15 คน+อบรม','20,000,000 ฿')
        ], '~120 ล้าน', RED),
    ]
    y = 24
    for phase, items, total, clr in budget:
        h = max(len(items), 1) * 5.5 + 7
        pdf.card(MX, y, CW - 45, h, (255,248,232))
        pdf.set_font('th', 'B', 10); pdf.set_text_color(*clr)
        pdf.set_xy(MX + 2, y + 1); pdf.cell(100, 5, phase)
        for j, (item, cost) in enumerate(items):
            pdf.set_font('th', '', 9); pdf.set_text_color(*TXT)
            pdf.set_xy(MX + 5, y + 7 + j * 5.5); pdf.cell(100, 5, item)
            pdf.set_text_color(*TXTL)
            pdf.set_xy(MX + 130, y + 7 + j * 5.5); pdf.cell(70, 5, cost, align='R')
        pdf.card(CW - 28, y + 2, 38, 8, clr)
        pdf.text_block(CW - 28, y + 2, 38, total, 11, WHITE, True, 'C')
        y += h + 2

    pdf.card(MX, y + 2, CW, 10, VDARK)
    pdf.set_font('th', 'B', 13); pdf.set_text_color(*WHITE)
    pdf.set_xy(MX + 3, y + 3); pdf.cell(60, 7, 'รวมทั้งโครงการ 3 ปี')
    pdf.set_text_color(*GOLD)
    pdf.set_xy(MX + 100, y + 3); pdf.cell(CW - 106, 7, '~170 ล้านบาท', align='R')

    # ════════════ 17. BUDGET HIGHLIGHTS ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('จุดเด่นของงบประมาณ SPNI')
    for i, (t_, desc, clr) in enumerate([
        ('ไม่มีค่า license รายปี','จ่ายครั้งเดียว ใช้ตลอด | i2 = 500,000 ฿/คน/ปี × 1,484 สถานี = 742 ล้าน/ปี',GREEN),
        ('ขยายได้ไม่จำกัด','เพิ่มสถานี = แค่เพิ่ม server | 1,484 สถานี ~15,000-20,000 พนักงานสอบสวน',BLUE),
        ('Customizable เต็มที่','มีโค้ดทั้งหมด — ไม่ต้องพึ่งบริษัทต่างชาติ — เป็นสมบัติ สตช.',ORANGE),
        ('Data Sovereignty','On-Premise 100% | ไม่มีข้อมูลคดีออกนอกประเทศ | Local LLM เท่านั้น',RED),
    ]):
        y = 24 + i * 26
        pdf.set_fill_color(*clr); pdf.rect(MX, y, 2, 22, 'F')
        pdf.card(MX + 3, y, CW - 3, 22, WHITE)
        pdf.set_font('th', 'B', 13); pdf.set_text_color(*clr)
        pdf.set_xy(MX + 6, y + 2); pdf.cell(CW - 12, 7, t_)
        pdf.set_font('th', '', 10); pdf.set_text_color(*TXTL)
        pdf.set_xy(MX + 6, y + 11); pdf.cell(CW - 12, 7, desc)

    # ════════════ 18. COMPARISON ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('เปรียบเทียบกับซอฟต์แวร์ทางการค้า')
    rows = [
        ('คุณสมบัติ','BSIE (SPNI)','i2 Analyst\'s NB','Cellebrite'),
        ('ราคา','ฟรี','500,000 ฿/คน/ปี','300,000 ฿/คน/ปี'),
        ('1,484 สถานี/ปี','ค่า server เท่านั้น','742+ ล้าน/ปี','445+ ล้าน/ปี'),
        ('ภาษาไทย','[Y] เต็มระบบ','[X]','[X]'),
        ('ธนาคารไทย 8 แห่ง','[Y] Auto-detect','[X] setup เอง','~ บางส่วน'),
        ('กราฟเครือข่าย','[Y] mini i2','[Y] เต็มรูปแบบ','[Y]'),
        ('PDF/OCR ไทย','[Y] EasyOCR','[X]','~'),
        ('รายงาน ปปง.','[Y] STR/CTR','[X]','~'),
        ('PromptPay','[Y]','[X]','[X]'),
        ('FATF Threat','[Y] 5 รูปแบบ','[X]','~'),
        ('Anomaly Detection','[Y] 4 วิธี','~','~'),
        ('Local LLM','[Y] Ollama','[X]','[X]'),
        ('Customizable','[Y] มีโค้ดทั้งหมด','[X] Closed','[X] Closed'),
        ('Data Sovereignty','[Y] On-Premise 100%','~','~'),
    ]
    cw_c = [70, 55, 55, 55]
    cx = [MX + 10]
    for w in cw_c[:-1]: cx.append(cx[-1] + w + 2)
    rh = 9
    for i, row in enumerate(rows):
        y = 24 + i * rh
        is_hdr = (i == 0)
        for j, cell in enumerate(row):
            bg = NAVY if is_hdr else (WHITE if i % 2 == 1 else MGRAY)
            pdf.set_fill_color(*bg)
            pdf.rect(cx[j], y, cw_c[j], rh, 'F')
            tc = WHITE if is_hdr else TXT
            if j == 1 and not is_hdr and ('[Y]' in cell or cell == 'ฟรี'): tc = GREEN
            elif not is_hdr and '[X]' in cell: tc = RED
            elif not is_hdr and cell.startswith('~'): tc = GOLD
            pdf.set_font('th', 'B' if (is_hdr or j==0) else '', 9)
            pdf.set_text_color(*tc)
            al = 'L' if j == 0 else 'C'
            pdf.set_xy(cx[j] + 2, y + 1); pdf.cell(cw_c[j] - 4, rh - 2, cell, align=al)

    # ════════════ 19. PROJECT STATS ════════════
    pdf.new_slide(VDARK)
    pdf.slide_title('ขนาดโปรเจค BSIE v4.1 — ตัวเลข', WHITE)
    stats = [
        ('161','Python Files',GREEN),('41','React/TS Files',SKY),
        ('~41,000','Lines of Code',GOLD),('120+','API Endpoints',BLUE),
        ('21','API Routers',MINT),('34','Services',LILAC),
        ('30','Core Modules',ORANGE),('20','DB Tables',SKY),
        ('244','Automated Tests',GREEN),('500+','i18n Keys',GOLD),
        ('8','ธนาคารไทย',RED),('14','Pipeline Steps',PURPLE),
        ('12','Alert Patterns',ORANGE),('5','FATF Models',RED),
        ('4','Anomaly Methods',LILAC),('13','Investigation Tabs',BLUE),
    ]
    sw = (CW - 12) / 4
    for i, (num, label, clr) in enumerate(stats):
        col, row = i % 4, i // 4
        x = MX + col * (sw + 4)
        y = 24 + row * 22
        pdf.card(x, y, sw, 20, DGRAY)
        pdf.text_block(x, y + 2, sw, num, 18, clr, True, 'C')
        pdf.text_block(x, y + 13, sw, label, 9, WHITE, align='C')

    # ════════════ 20. ROI ════════════
    pdf.new_slide(GREEN)
    pdf.slide_title('ROI — ผลตอบแทนการลงทุน', WHITE)
    for i, (label, desc, pct, clr) in enumerate([
        ('เวลาวิเคราะห์','จาก 3-5 วัน -> 30 นาที ต่อคดี',0.95,SALMON),
        ('ค่า license','ประหยัด 742+ ล้านบาท/ปี (vs i2)',1.0,GOLD),
        ('ข้อผิดพลาด','ลดข้อผิดพลาด — ลดอุทธรณ์',0.75,SKY),
        ('ตรวจจับเร็ว','ป้องกันความเสียหาย — ฟอกเงิน ฉ้อโกง',0.85,MINT),
        ('ครอบคลุม','1,484 สถานี — 77 จังหวัดทั่วประเทศ',0.80,LILAC),
    ]):
        y = 28 + i * 20
        pdf.set_font('th', 'B', 12); pdf.set_text_color(*WHITE)
        pdf.set_xy(MX, y); pdf.cell(35, 7, label)
        pdf.card(MX + 38, y, CW - 38, 9, DGREEN)
        pdf.card(MX + 38, y, (CW - 38) * pct, 9, clr)
        pdf.set_font('th', 'B', 9); pdf.set_text_color(*VDARK)
        pdf.set_xy(MX + 41, y + 0.5); pdf.cell(CW - 44, 8, desc)

    pdf.card(MX, 135, CW, 12, DGREEN)
    pdf.text_block(MX, 137, CW, 'คืนทุนใน 1 ปี — ค่า license i2 ปีเดียว > งบ SPNI ทั้ง 3 ปี', 13, WHITE, True, 'C')

    # ════════════ 21. TEAM ════════════
    pdf.new_slide(LGRAY)
    pdf.slide_title('ทีมพัฒนา + ประมาณการผู้ใช้งาน')
    pdf.card(MX, 24, hw, 40, WHITE, GREEN)
    pdf.card_title(MX, 24, hw, 'Phase 1-2: คนเดียว + AI', GREEN, 12)
    pdf.bullet_list(MX+3, 35, hw-6, ['ร.ต.อ.ณัฐวุฒิ + **Claude AI**','**41,000 บรรทัด** 244 tests 120+ API'], size=10)

    pdf.card(rx, 24, hw, 40, WHITE, ORANGE)
    pdf.card_title(rx, 24, hw, 'Phase 3-4: ทีม 8-12 คน', ORANGE, 12)
    pdf.bullet_list(rx+3, 35, hw-6, ['Backend **2-3** | Frontend **1-2** | DevOps **1-2**','AI/ML **1** | QA **1-2** | PM **1**'], size=10, bc=ORANGE)

    pdf.card(MX, 70, CW, 80, WHITE, BLUE)
    pdf.card_title(MX, 70, CW, 'ประมาณการผู้ใช้ — จากจังหวัดสู่ทั้งประเทศ', BLUE, 12)
    u_rows = [('ระดับ','ผู้ใช้พร้อมกัน','ธุรกรรม/เดือน','Storage/ปี'),
              ('Phase 1 pilot','1-3 คน','10,000','1 GB'),
              ('Phase 2 (5 จว.)','50-150 คน','500,000','50 GB'),
              ('Phase 3 (20 จว.)','200-600 คน','2,000,000','200 GB'),
              ('Phase 4 ทั้งประเทศ','2,000-5,000 คน','10,000,000+','1+ TB')]
    ucw_ = (CW - 8) / 4
    for i, row in enumerate(u_rows):
        y_ = 84 + i * 9
        for j, cell in enumerate(row):
            x_ = MX + 4 + j * ucw_
            bg_ = NAVY if i == 0 else (WHITE if i % 2 == 1 else MGRAY)
            pdf.set_fill_color(*bg_); pdf.rect(x_, y_, ucw_, 9, 'F')
            tc = WHITE if i == 0 else TXT
            pdf.set_font('th', 'B' if (i==0 or j==0) else '', 9)
            pdf.set_text_color(*tc)
            al_ = 'L' if j == 0 else 'C'
            pdf.set_xy(x_ + 2, y_ + 1); pdf.cell(ucw_ - 4, 7, cell, align=al_)

    # ════════════ 22. CLOSING ════════════
    pdf.new_slide(NAVY)
    pdf.text_block(MX, 12, CW, 'สรุปและขั้นตอนถัดไป', 26, WHITE, True, 'C')
    pdf.set_fill_color(*GOLD); pdf.rect(PW/2-15, 27, 30, 0.8, 'F')

    for i, (num, text, clr) in enumerate([
        ('1.','BSIE v4.1 พร้อมใช้วันนี้ — ไม่ต้องรองบประมาณ',MINT),
        ('2.','ทดลอง Pilot กับคดีจริง 5-10 คดี (ฟรี)',SKY),
        ('3.','เก็บ feedback จากพนักงานสอบสวน',GOLD),
        ('4.','เสนองบ Phase 2: ~8 ล้านบาท (5 จังหวัดนำร่อง)',SALMON),
        ('5.','ขยายสู่ SPNI Platform ทั้งประเทศ — 77 จังหวัด 1,484 สถานี',LILAC),
    ]):
        y = 38 + i * 15
        pdf.set_font('th', 'B', 18); pdf.set_text_color(*clr)
        pdf.set_xy(MX + 55, y); pdf.cell(10, 10, num)
        pdf.set_font('th', '', 14); pdf.set_text_color(*WHITE)
        pdf.set_xy(MX + 68, y + 1); pdf.cell(CW - 80, 10, text)

    pdf.card(MX, 118, CW, 14, (30,58,95))
    pdf.text_block(MX, 120, CW, 'งบ SPNI ทั้ง 3 ปี (~170 ล้าน) < ค่า license i2 ปีเดียว (742+ ล้าน) -> คืนทุนทันที', 12, GOLD, True, 'C')

    pdf.text_block(MX, 150, CW, 'ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง | โทร: 096-776-8757 | BSIE v4.1', 10, SUBTLE, align='C')

    # -- Save --
    out = BASE / 'docs' / 'SPNI_BSIE_Presentation.pdf'
    pdf.output(str(out))
    print(f'✅ PDF saved: {out}')
    print(f'   {pdf.page} pages')


if __name__ == '__main__':
    generate()
