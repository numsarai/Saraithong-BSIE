"""
image_loader.py
---------------
Extract transaction tables from images and scanned PDFs using OCR.

Uses EasyOCR for Thai + English text recognition, then reconstructs a table
from the detected text bounding boxes by clustering rows and columns.

EasyOCR is an optional dependency — if missing, a clear error is raised.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from core.loader import score_header_row

logger = logging.getLogger(__name__)

# ── Lazy EasyOCR singleton ───────────────────────────────────────────────

_reader: Any | None = None
EASYOCR_AVAILABLE = False

try:
    import easyocr  # noqa: F401
    EASYOCR_AVAILABLE = True
except ImportError:
    pass


def _get_reader() -> Any:
    """Return a cached EasyOCR Reader for Thai + English."""
    global _reader
    if not EASYOCR_AVAILABLE:
        raise RuntimeError(
            "OCR support requires EasyOCR. Install with: pip install easyocr"
        )
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["th", "en"], gpu=False)
        logger.info("EasyOCR reader initialized (Thai + English)")
    return _reader


# ── Public API ───────────────────────────────────────────────────────────

def parse_image_file(path: Path | str) -> dict:
    """Extract a transaction table from an image or scanned PDF via OCR.

    Returns
    -------
    dict with keys:
        df : pd.DataFrame   – extracted table (empty if OCR fails)
        source_format : str  – ``"IMAGE"``
        page_count : int     – 1 for images, page count for scanned PDFs
        ocr_used : bool      – always ``True``
        header_row : int
        tables_found : int   – 0 or 1
    """
    path = Path(path)
    logger.info("Image loader: processing %s", path.name)

    if path.suffix.lower() == ".pdf":
        return _parse_scanned_pdf(path)
    return _parse_single_image(path)


def _parse_single_image(path: Path) -> dict:
    """OCR a single image file and reconstruct the table."""
    reader = _get_reader()
    results = reader.readtext(str(path), detail=1)
    df, header_row = _build_table_from_ocr(results)

    return {
        "df": df,
        "source_format": "IMAGE",
        "page_count": 1,
        "ocr_used": True,
        "header_row": header_row,
        "tables_found": 1 if not df.empty else 0,
    }


def _parse_scanned_pdf(path: Path) -> dict:
    """Render each PDF page to an image, OCR, and merge results."""
    import pdfplumber

    all_results: list[list] = []
    page_count = 0

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            img = page.to_image(resolution=300)
            pil_image = img.original
            reader = _get_reader()
            page_results = reader.readtext(pil_image, detail=1)
            all_results.extend(page_results)

    df, header_row = _build_table_from_ocr(all_results)

    return {
        "df": df,
        "source_format": "IMAGE",
        "page_count": page_count,
        "ocr_used": True,
        "header_row": header_row,
        "tables_found": 1 if not df.empty else 0,
    }


# ── Table reconstruction from OCR ────────────────────────────────────────

_MIN_CONFIDENCE = 0.3
_ROW_Y_TOLERANCE = 15  # pixels — boxes within this Y range are same row


def _build_table_from_ocr(
    ocr_results: list,
) -> tuple[pd.DataFrame, int]:
    """Convert OCR bounding boxes into a DataFrame.

    Each EasyOCR result is ``(bbox, text, confidence)`` where bbox is
    ``[[x0,y0], [x1,y0], [x1,y1], [x0,y1]]``.

    Steps:
    1. Filter by confidence threshold
    2. Cluster text boxes into rows by Y-center
    3. Sort boxes within each row by X
    4. Build a raw grid and detect the header
    """
    if not ocr_results:
        return pd.DataFrame(), 0

    # Filter low-confidence results
    boxes = []
    for bbox, text, conf in ocr_results:
        if conf >= _MIN_CONFIDENCE and text.strip():
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            x_center = (bbox[0][0] + bbox[1][0]) / 2
            boxes.append({
                "text": text.strip(),
                "x": x_center,
                "y": y_center,
                "conf": conf,
            })

    if not boxes:
        return pd.DataFrame(), 0

    # Sort by Y then X
    boxes.sort(key=lambda b: (b["y"], b["x"]))

    # Cluster into rows by Y proximity
    rows: list[list[dict]] = []
    current_row: list[dict] = [boxes[0]]
    for box in boxes[1:]:
        if abs(box["y"] - current_row[0]["y"]) <= _ROW_Y_TOLERANCE:
            current_row.append(box)
        else:
            rows.append(sorted(current_row, key=lambda b: b["x"]))
            current_row = [box]
    rows.append(sorted(current_row, key=lambda b: b["x"]))

    if len(rows) < 2:
        return pd.DataFrame(), 0

    # Determine column count from the most common row width
    col_counts = [len(r) for r in rows]
    max_cols = max(col_counts) if col_counts else 0

    # Build raw text grid
    grid: list[list[str]] = []
    for row in rows:
        cells = [b["text"] for b in row]
        # Pad short rows
        while len(cells) < max_cols:
            cells.append("")
        grid.append(cells[:max_cols])

    # Find header row
    best_header = 0
    best_score = -1.0
    for idx in range(min(10, len(grid))):
        score = score_header_row(grid[idx])
        if score > best_score:
            best_score = score
            best_header = idx

    # Build DataFrame
    if best_header < len(grid):
        columns = grid[best_header]
        # Deduplicate column names
        seen: dict[str, int] = {}
        unique_cols: list[str] = []
        for col in columns:
            if col in seen:
                seen[col] += 1
                unique_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_cols.append(col)
        data_rows = grid[best_header + 1:]
        df = pd.DataFrame(data_rows, columns=unique_cols)
    else:
        df = pd.DataFrame(grid)

    # Drop fully empty rows
    df = df.loc[~(df == "").all(axis=1)].reset_index(drop=True)

    return df, best_header
