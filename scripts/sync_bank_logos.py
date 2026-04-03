"""Fetch real bank logo icons for BSIE.

This script pulls the favicon/app icon exposed by the official bank domain via
Google's favicon cache endpoint, normalizes the result into square PNG assets,
and writes them into ``static/bank-logos`` using each BSIE bank key.

The goal is pragmatic: give the UI and exported workbooks a recognizable,
bank-specific logo immediately, while still allowing manual replacement with
exact brand artwork later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
import json
import sys

import requests
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.bank_logo_registry import _RAW_BANK_BRANDS  # noqa: E402


OUTPUT_DIR = REPO_ROOT / "static" / "bank-logos"
MANIFEST_PATH = OUTPUT_DIR / "sources.json"
PREVIEW_PATH = OUTPUT_DIR / "_catalog-preview.png"
GOOGLE_S2_URL = "https://www.google.com/s2/favicons"
USER_AGENT = "Mozilla/5.0 (BSIE logo sync)"


@dataclass(frozen=True)
class LogoSource:
    key: str
    official_url: str
    icon_url: str | None = None


_OFFICIAL_BANK_URLS = {
    "scb": {"official_url": "https://www.scb.co.th/"},
    "kbank": {"official_url": "https://www.kasikornbank.com/"},
    "ktb": {"official_url": "https://krungthai.com/"},
    "bbl": {"official_url": "https://www.bangkokbank.com/"},
    "bay": {"official_url": "https://www.krungsri.com/"},
    "ttb": {"official_url": "https://www.ttbbank.com/"},
    "gsb": {"official_url": "https://www.gsb.or.th/"},
    "baac": {"official_url": "https://www.baac.or.th/"},
    "ghab": {"official_url": "https://www.ghbank.co.th/"},
    "exim": {
        "official_url": "https://www.exim.go.th/",
        "icon_url": "https://www.exim.go.th/App_Themes/EximInter/images/favicon.ico",
    },
    "islami": {
        "official_url": "https://www.ibank.co.th/",
        "icon_url": "https://www.ibank.co.th/templates/images/favicon.ico",
    },
    "kkp": {"official_url": "https://www.kkpfg.com/"},
    "cimb_thai": {"official_url": "https://www.cimbthai.com/"},
    "tisco": {"official_url": "https://www.tisco.co.th/"},
    "thai_credit": {"official_url": "https://www.thaicreditbank.com/"},
    "uob_thai": {"official_url": "https://www.uob.co.th/"},
    "lh_bank": {"official_url": "https://www.lhbank.co.th/"},
    "icbc_thai": {
        "official_url": "https://www.icbcthai.com/",
        "icon_url": "https://v.icbc.com.cn/userfiles/Resources/ICBC/haiwai/ICBCThailand/photo/2015/ICBCThailand_Logo.gif",
    },
    "boc_thai": {"official_url": "https://www.bankofchina.com/th/"},
    "scbt": {"official_url": "https://www.sc.com/th/"},
    "sme_d": {"official_url": "https://www.smebank.co.th/"},
}


def _thai_bank_entries() -> list[dict]:
    return [entry for entry in _RAW_BANK_BRANDS if entry.get("bank_type") == "thai_bank"]


def _fetch_logo(source: LogoSource) -> Image.Image:
    response = requests.get(
        GOOGLE_S2_URL,
        params={"sz": 256, "domain_url": source.official_url},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if response.status_code == 404 and source.icon_url:
        response = requests.get(source.icon_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)).convert("RGBA")
    return image


def _normalize_canvas(image: Image.Image, size: int = 256) -> Image.Image:
    image = image.copy()
    max_inner = int(size * 0.72)
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("Invalid logo image size")
    scale = min(max_inner / width, max_inner / height)
    if abs(scale - 1.0) > 0.01:
        resized = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    x = (size - image.size[0]) // 2
    y = (size - image.size[1]) // 2
    canvas.paste(image, (x, y), image)
    return canvas


def _write_preview(entries: list[dict]) -> None:
    if not entries:
        return
    card_w = 180
    card_h = 180
    columns = 4
    rows = (len(entries) + columns - 1) // columns
    preview = Image.new("RGBA", (columns * card_w, rows * card_h), (15, 23, 42, 255))
    for index, entry in enumerate(entries):
        row = index // columns
        col = index % columns
        x = col * card_w
        y = row * card_h
        tile = Image.new("RGBA", (card_w, card_h), (31, 41, 55, 255))
        tile_logo = Image.open(OUTPUT_DIR / f"{entry['key']}.png").convert("RGBA")
        tile_logo.thumbnail((112, 112), Image.Resampling.LANCZOS)
        logo_x = (card_w - tile_logo.size[0]) // 2
        logo_y = 18
        tile.paste(tile_logo, (logo_x, logo_y), tile_logo)
        preview.paste(tile, (x, y))
    preview.save(PREVIEW_PATH, format="PNG")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC).isoformat()
    manifest: list[dict] = []
    failures: list[str] = []

    for entry in _thai_bank_entries():
        key = str(entry["key"])
        source_data = _OFFICIAL_BANK_URLS.get(key)
        if not source_data:
            raise RuntimeError(f"Missing official URL mapping for {key}")
        official_url = str(source_data["official_url"])
        source = LogoSource(
            key=key,
            official_url=official_url,
            icon_url=str(source_data["icon_url"]) if source_data.get("icon_url") else None,
        )
        try:
            image = _normalize_canvas(_fetch_logo(source))
        except Exception as exc:  # pragma: no cover - operational path
            failures.append(f"{key}: {exc}")
            print(f"failed {key} from {official_url}: {exc}")
            continue
        output_path = OUTPUT_DIR / f"{key}.png"
        image.save(output_path, format="PNG")
        manifest.append(
            {
                "key": key,
                "name": entry["name"],
                "official_url": official_url,
                "fetched_via": GOOGLE_S2_URL,
                "fetched_at_utc": fetched_at,
                "width": image.size[0],
                "height": image.size[1],
                "output_file": output_path.name,
                "note": "Official-site favicon/app icon cached via Google S2. Replace with exact brand artwork later if needed.",
            }
        )
        print(f"saved {output_path.name} from {official_url}")

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_preview(manifest)
    print(f"wrote manifest -> {MANIFEST_PATH}")
    print(f"wrote preview  -> {PREVIEW_PATH}")
    if failures:
        print("failures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
