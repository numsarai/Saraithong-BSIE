"""Central bank logo registry and deterministic logo generation.

The goal of this module is to keep bank branding metadata in one place so the
frontend, API, and report exporter all use the same bank identity catalog.

The SVG and PNG renderers intentionally generate simple offline-safe bank
badges. They are not meant to replace source evidence and never affect parser
semantics.
"""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
from typing import Iterable, Mapping
import html

from PIL import Image, ImageDraw, ImageFont

from paths import STATIC_DIR


_BANK_LOGO_ASSET_DIR = STATIC_DIR / "bank-logos"

_RAW_BANK_BRANDS = [
    {
        "key": "scb",
        "name": "Siam Commercial Bank",
        "short_name": "SCB",
        "monogram": "SCB",
        "primary_color": "#4A2D7F",
        "secondary_color": "#7F56D9",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "kbank",
        "name": "Kasikornbank",
        "short_name": "KBank",
        "monogram": "KB",
        "primary_color": "#0F8B4C",
        "secondary_color": "#34A853",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "ktb",
        "name": "Krung Thai Bank",
        "short_name": "KTB",
        "monogram": "KTB",
        "primary_color": "#1E63D5",
        "secondary_color": "#5AA6FF",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "bbl",
        "name": "Bangkok Bank",
        "short_name": "BBL",
        "monogram": "BBL",
        "primary_color": "#1C3E94",
        "secondary_color": "#405FC8",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "bay",
        "name": "Bank of Ayudhya",
        "short_name": "Krungsri",
        "monogram": "BAY",
        "primary_color": "#F4C20D",
        "secondary_color": "#D89A00",
        "text_color": "#1F2937",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "ttb",
        "name": "ttb",
        "short_name": "ttb",
        "monogram": "ttb",
        "primary_color": "#1F4E79",
        "secondary_color": "#F97316",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "gsb",
        "name": "Government Savings Bank",
        "short_name": "GSB",
        "monogram": "GSB",
        "primary_color": "#E85A9B",
        "secondary_color": "#FF8BB7",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": True,
    },
    {
        "key": "baac",
        "name": "Bank for Agriculture and Agricultural Cooperatives",
        "short_name": "BAAC",
        "monogram": "BAAC",
        "primary_color": "#0E7A4A",
        "secondary_color": "#2CB67D",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "ghab",
        "name": "Government Housing Bank",
        "short_name": "GH Bank",
        "monogram": "GHB",
        "primary_color": "#E46C0A",
        "secondary_color": "#F59E0B",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "exim",
        "name": "Export-Import Bank of Thailand",
        "short_name": "EXIM",
        "monogram": "EXIM",
        "primary_color": "#006D77",
        "secondary_color": "#1AA6B7",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "islami",
        "name": "Islamic Bank of Thailand",
        "short_name": "Islamic Bank",
        "monogram": "IBT",
        "primary_color": "#0F766E",
        "secondary_color": "#0EA5A4",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "kkp",
        "name": "Kiatnakin Phatra Bank",
        "short_name": "KKP",
        "monogram": "KKP",
        "primary_color": "#7C3AED",
        "secondary_color": "#A78BFA",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "cimb_thai",
        "name": "CIMB Thai Bank",
        "short_name": "CIMB Thai",
        "monogram": "CIMB",
        "primary_color": "#C62828",
        "secondary_color": "#EF5350",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "tisco",
        "name": "TISCO Bank",
        "short_name": "TISCO",
        "monogram": "TISCO",
        "primary_color": "#0F4C81",
        "secondary_color": "#2563EB",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "thai_credit",
        "name": "Thai Credit Bank",
        "short_name": "Thai Credit",
        "monogram": "TCB",
        "primary_color": "#C2410C",
        "secondary_color": "#FB923C",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "uob_thai",
        "name": "UOB Thailand",
        "short_name": "UOB",
        "monogram": "UOB",
        "primary_color": "#1D4ED8",
        "secondary_color": "#DC2626",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "lh_bank",
        "name": "Land and Houses Bank",
        "short_name": "LH Bank",
        "monogram": "LHB",
        "primary_color": "#0F8B4C",
        "secondary_color": "#7BC67E",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "icbc_thai",
        "name": "ICBC Thai",
        "short_name": "ICBC Thai",
        "monogram": "ICBC",
        "primary_color": "#B91C1C",
        "secondary_color": "#EF4444",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "boc_thai",
        "name": "Bank of China (Thai)",
        "short_name": "BOC Thai",
        "monogram": "BOC",
        "primary_color": "#9F1239",
        "secondary_color": "#E11D48",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "scbt",
        "name": "Standard Chartered Bank Thai",
        "short_name": "SCBT",
        "monogram": "SC",
        "primary_color": "#1F9D8B",
        "secondary_color": "#2DD4BF",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "sme_d",
        "name": "SME D Bank",
        "short_name": "SME D",
        "monogram": "SME",
        "primary_color": "#0F766E",
        "secondary_color": "#22C55E",
        "text_color": "#FFFFFF",
        "bank_type": "thai_bank",
        "has_template_default": False,
    },
    {
        "key": "bot",
        "name": "Bank of Thailand",
        "short_name": "BOT",
        "monogram": "BOT",
        "primary_color": "#1E3A8A",
        "secondary_color": "#3B82F6",
        "text_color": "#FFFFFF",
        "bank_type": "regulator",
        "has_template_default": False,
    },
    {
        "key": "generic",
        "name": "Generic Template",
        "short_name": "Generic",
        "monogram": "GEN",
        "primary_color": "#334155",
        "secondary_color": "#64748B",
        "text_color": "#FFFFFF",
        "bank_type": "format_helper",
        "has_template_default": True,
    },
    {
        "key": "ofx",
        "name": "OFX Import",
        "short_name": "OFX",
        "monogram": "OFX",
        "primary_color": "#0F766E",
        "secondary_color": "#14B8A6",
        "text_color": "#FFFFFF",
        "bank_type": "format_helper",
        "has_template_default": True,
    },
    {
        "key": "ciaf",
        "name": "CIAF Export",
        "short_name": "CIAF",
        "monogram": "CIAF",
        "primary_color": "#312E81",
        "secondary_color": "#6366F1",
        "text_color": "#FFFFFF",
        "bank_type": "format_helper",
        "has_template_default": True,
    },
]


_BANK_BRANDS_BY_KEY = {entry["key"]: entry for entry in _RAW_BANK_BRANDS}

_BANK_REFERENCE_DETAILS = {
    "baac": {
        "bank_name_th": "ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร",
        "bank_name_en": "Bank for Agriculture and Agricultural Cooperatives",
        "head_office_address": "2346 ถนนพหลโยธิน แขวงเสนานิคม เขตจตุจักร กรุงเทพฯ 10900",
    },
    "bay": {
        "bank_name_th": "ธนาคารกรุงศรีอยุธยา",
        "bank_name_en": "Bank of Ayudhya",
        "head_office_address": "1222 ถนนพระรามที่ 3 แขวงบางโพงพาง เขตยานนาวา กรุงเทพฯ 10120",
    },
    "bbl": {
        "bank_name_th": "ธนาคารกรุงเทพ",
        "bank_name_en": "Bangkok Bank",
        "head_office_address": "333 ถนนสีลม แขวงสีลม เขตบางรัก กรุงเทพฯ 10500",
    },
    "bot": {
        "bank_name_th": "ธนาคารแห่งประเทศไทย",
        "bank_name_en": "Bank of Thailand",
        "head_office_address": "273 ถนนสามเสน แขวงวัดสามพระยา เขตพระนคร กรุงเทพฯ 10200",
    },
    "cimb_thai": {
        "bank_name_th": "ธนาคารซีไอเอ็มบี ไทย",
        "bank_name_en": "CIMB Thai Bank",
        "head_office_address": "44 ถนนหลังสวน แขวงลุมพินี เขตปทุมวัน กรุงเทพมหานคร 10330",
    },
    "ghab": {
        "bank_name_th": "ธนาคารอาคารสงเคราะห์",
        "bank_name_en": "Government Housing Bank",
        "head_office_address": "63 ถนนพระราม 9 แขวงห้วยขวาง เขตห้วยขวาง กรุงเทพมหานคร 10310",
    },
    "gsb": {
        "bank_name_th": "ธนาคารออมสิน",
        "bank_name_en": "Government Savings Bank",
        "head_office_address": "470 ถนนพหลโยธิน แขวงสามเสนใน เขตพญาไท กรุงเทพมหานคร 10400",
    },
    "kbank": {
        "bank_name_th": "ธนาคารกสิกรไทย",
        "bank_name_en": "Kasikornbank",
        "head_office_address": "400/22 ถนนพหลโยธิน แขวงสามเสนใน เขตพญาไท กรุงเทพฯ 10400",
    },
    "ktb": {
        "bank_name_th": "ธนาคารกรุงไทย",
        "bank_name_en": "Krung Thai Bank",
        "head_office_address": "35 ถนนสุขุมวิท แขวงคลองเตยเหนือ เขตวัฒนา กรุงเทพฯ 10110",
    },
    "lh_bank": {
        "bank_name_th": "ธนาคารแลนด์ แอนด์ เฮ้าส์",
        "bank_name_en": "Land and Houses Bank",
        "head_office_address": "1 อาคารคิวเฮ้าส์ ลุมพินี ถนนสาทรใต้ แขวงยานนาวา เขตสาทร กรุงเทพมหานคร 10120",
    },
    "scb": {
        "bank_name_th": "ธนาคารไทยพาณิชย์",
        "bank_name_en": "Siam Commercial Bank",
        "head_office_address": "9 ถนนรัชดาภิเษก แขวงจตุจักร เขตจตุจักร กรุงเทพฯ 10900",
    },
    "ttb": {
        "bank_name_th": "ทีทีบี",
        "bank_name_en": "TMBThanachart Bank",
        "head_office_address": "3000 ถนนพหลโยธิน แขวงจอมพล เขตจตุจักร กรุงเทพฯ 10900",
    },
    "uob_thai": {
        "bank_name_th": "ธนาคารยูโอบี",
        "bank_name_en": "UOB Thailand",
        "head_office_address": "690 ถนนสุขุมวิท แขวงคลองตัน เขตคลองเตย กรุงเทพมหานคร 10110",
    },
}


def _title_from_key(key: str) -> str:
    text = str(key or "").strip().replace("_", " ")
    return " ".join(part.capitalize() for part in text.split()) or "Unknown Bank"


def _fallback_brand(key: str, display_name: str | None = None) -> dict:
    display = str(display_name or _title_from_key(key)).strip() or _title_from_key(key)
    monogram = "".join(ch for ch in display.upper() if ch.isalnum())[:4] or "BANK"
    return {
        "key": str(key or "unknown").strip().lower() or "unknown",
        "name": display,
        "short_name": display,
        "monogram": monogram,
        "primary_color": "#475569",
        "secondary_color": "#94A3B8",
        "text_color": "#FFFFFF",
        "bank_type": "custom_bank",
        "has_template_default": False,
    }


def _template_status(bank_type: str, has_template: bool) -> tuple[str, str]:
    if bank_type == "format_helper":
        return "format_helper", "Format helper"
    if has_template:
        return "template_ready", "Template ready"
    return "logo_ready", "Logo ready / template pending"


def _bank_logo_asset_candidates(key: str) -> list[Path]:
    normalized = str(key or "").strip().lower()
    if not normalized:
        return []
    return [
        _BANK_LOGO_ASSET_DIR / f"{normalized}.svg",
        _BANK_LOGO_ASSET_DIR / f"{normalized}.png",
        _BANK_LOGO_ASSET_DIR / f"{normalized}.jpg",
        _BANK_LOGO_ASSET_DIR / f"{normalized}.jpeg",
    ]


def find_bank_logo_asset_path(key: str | None) -> Path | None:
    for candidate in _bank_logo_asset_candidates(str(key or "")):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def build_logo_record(
    key: str,
    *,
    display_name: str | None = None,
    has_template: bool | None = None,
    template_source: str = "registry",
) -> dict:
    base = deepcopy(_BANK_BRANDS_BY_KEY.get(key) or _fallback_brand(key, display_name))
    name = str(display_name or base["name"] or _title_from_key(key)).strip() or _title_from_key(key)
    effective_has_template = base["has_template_default"] if has_template is None else bool(has_template)
    status, badge = _template_status(str(base.get("bank_type") or "thai_bank"), effective_has_template)
    asset_path = find_bank_logo_asset_path(key)
    logo_url = f"/static/bank-logos/{asset_path.name}" if asset_path else f"/api/bank-logos/{str(base['key']).strip().lower()}.svg"
    base.update({
        "key": str(base["key"]).strip().lower(),
        "name": name,
        "short_name": str(base.get("short_name") or name).strip() or name,
        "monogram": str(base.get("monogram") or name[:4]).strip().upper()[:6] or "BANK",
        "has_template": effective_has_template,
        "template_source": template_source,
        "template_status": status,
        "template_badge": badge,
        "logo_url": logo_url,
        "logo_asset_path": str(asset_path) if asset_path else "",
        "logo_source": "static_asset" if asset_path else "generated_badge",
    })
    reference_details = deepcopy(_BANK_REFERENCE_DETAILS.get(str(base["key"]).strip().lower()) or {})
    if reference_details:
        base.update(reference_details)
    return base


def build_bank_logo_catalog(template_banks: Iterable[Mapping[str, object]] | None = None) -> list[dict]:
    template_map: dict[str, dict] = {}
    for bank in template_banks or []:
        key = str(bank.get("key") or "").strip().lower()
        if not key:
            continue
        template_map[key] = build_logo_record(
            key,
            display_name=str(bank.get("name") or bank.get("bank_name") or _title_from_key(key)).strip(),
            has_template=True,
            template_source=str(bank.get("template_source") or "config"),
        )
        template_map[key]["is_builtin"] = bool(bank.get("is_builtin"))

    for key, base in _BANK_BRANDS_BY_KEY.items():
        if key in template_map:
            continue
        template_map[key] = build_logo_record(
            key,
            display_name=str(base.get("name") or _title_from_key(key)),
            has_template=bool(base.get("has_template_default")),
            template_source="registry",
        )

    def sort_key(item: dict) -> tuple[int, int, str]:
        bank_type = str(item.get("bank_type") or "")
        group = 0 if item.get("has_template") and bank_type == "thai_bank" else 1 if bank_type == "thai_bank" else 2
        return group, 0 if item.get("has_template") else 1, str(item.get("name") or "")

    return sorted(template_map.values(), key=sort_key)


def find_bank_logo_record(
    key: str | None = None,
    *,
    display_name: str | None = None,
    has_template: bool | None = None,
    template_source: str = "registry",
) -> dict:
    normalized_key = str(key or "").strip().lower()
    if normalized_key:
        return build_logo_record(
            normalized_key,
            display_name=display_name,
            has_template=has_template,
            template_source=template_source,
        )

    display = str(display_name or "").strip()
    lowered_display = display.lower()
    for brand in _RAW_BANK_BRANDS:
        candidates = {
            str(brand.get("name") or "").strip().lower(),
            str(brand.get("short_name") or "").strip().lower(),
            str(brand.get("key") or "").strip().lower(),
        }
        if lowered_display and lowered_display in candidates:
            return build_logo_record(
                str(brand["key"]),
                display_name=display or str(brand.get("name") or ""),
                has_template=has_template,
                template_source=template_source,
            )

    return build_logo_record(
        normalized_key or (display.lower().replace(" ", "_") if display else "generic"),
        display_name=display or None,
        has_template=has_template,
        template_source=template_source,
    )


def render_bank_logo_svg(
    key: str | None = None,
    *,
    display_name: str | None = None,
    has_template: bool | None = None,
    size: int = 96,
) -> str:
    record = find_bank_logo_record(key, display_name=display_name, has_template=has_template)
    asset_path = find_bank_logo_asset_path(str(record.get("key") or key or ""))
    if asset_path and asset_path.suffix.lower() == ".svg":
        return asset_path.read_text(encoding="utf-8")
    size = max(int(size or 96), 48)
    inset = max(size // 10, 8)
    radius = max(size // 4, 18)
    accent_height = max(size // 10, 8)
    text_size = max((size // 3) - max(len(str(record["monogram"])) - 3, 0) * 4, 18)
    title = html.escape(str(record["name"]))
    monogram = html.escape(str(record["monogram"]))
    template_badge = html.escape(str(record["template_badge"]))
    primary = str(record["primary_color"])
    secondary = str(record["secondary_color"])
    text_color = str(record["text_color"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{title} logo">
  <title>{title}</title>
  <rect x="2" y="2" width="{size - 4}" height="{size - 4}" rx="{radius}" fill="#FFFFFF" stroke="rgba(15,23,42,0.14)" stroke-width="2"/>
  <rect x="{inset}" y="{inset}" width="{size - inset * 2}" height="{size - inset * 2}" rx="{max(radius - 6, 12)}" fill="{primary}"/>
  <rect x="{inset}" y="{inset}" width="{size - inset * 2}" height="{accent_height}" rx="{max(radius - 6, 12)}" fill="{secondary}"/>
  <circle cx="{size / 2}" cy="{size / 2 + 4}" r="{size / 3.3:.2f}" fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.32)" stroke-width="2"/>
  <text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="{text_size}" font-weight="700" fill="{text_color}">{monogram}</text>
  <desc>{template_badge}</desc>
</svg>"""


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = str(value or "#000000").strip().lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ("DejaVuSans-Bold.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_bank_logo_png_bytes(
    key: str | None = None,
    *,
    display_name: str | None = None,
    has_template: bool | None = None,
    size: tuple[int, int] = (96, 96),
) -> BytesIO:
    record = find_bank_logo_record(key, display_name=display_name, has_template=has_template)
    asset_path = find_bank_logo_asset_path(str(record.get("key") or key or ""))
    if asset_path and asset_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        image = Image.open(asset_path).convert("RGBA")
        if image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        payload = BytesIO()
        image.save(payload, format="PNG")
        payload.seek(0)
        return payload
    width = max(int(size[0]), 48)
    height = max(int(size[1]), 48)
    padding = max(width // 10, 8)
    radius = max(width // 4, 18)

    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=radius, fill=(255, 255, 255, 255), outline=(203, 213, 225, 255), width=2)
    draw.rounded_rectangle((padding, padding, width - padding, height - padding), radius=max(radius - 6, 12), fill=_hex_to_rgb(record["primary_color"]) + (255,))
    draw.rectangle((padding, padding, width - padding, padding + max(height // 10, 8)), fill=_hex_to_rgb(record["secondary_color"]) + (255,))
    circle_radius = int(min(width, height) / 3.3)
    center_x = width // 2
    center_y = height // 2 + 3
    draw.ellipse(
        (center_x - circle_radius, center_y - circle_radius, center_x + circle_radius, center_y + circle_radius),
        fill=(255, 255, 255, 46),
        outline=(255, 255, 255, 92),
        width=2,
    )

    text = str(record["monogram"])
    font_size = max(int(min(width, height) * 0.24), 16)
    font = _load_font(font_size)
    text_bbox = draw.textbbox((0, 0), text, font=font)
    max_text_width = int(circle_radius * 1.55)
    while font_size > 14 and (text_bbox[2] - text_bbox[0]) > max_text_width:
        font_size -= 2
        font = _load_font(font_size)
        text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (width - text_width) / 2
    text_y = (height - text_height) / 2 - 1
    draw.text((text_x, text_y), text, font=font, fill=_hex_to_rgb(record["text_color"]) + (255,))

    payload = BytesIO()
    image.save(payload, format="PNG")
    payload.seek(0)
    return payload
