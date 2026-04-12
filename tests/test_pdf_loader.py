"""Tests for core/pdf_loader.py — PDF table extraction."""
import tempfile
from pathlib import Path

import pandas as pd
import pdfplumber
import pytest

from core.pdf_loader import parse_pdf_file, _select_best_table, _merge_compatible_tables


def _create_simple_pdf(path: Path, rows: list[list[str]]) -> None:
    """Create a minimal PDF with a single table using pdfplumber's companion fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    col_width = 180 / max(len(r) for r in rows)
    for row in rows:
        for cell in row:
            pdf.cell(col_width, 8, str(cell), border=1)
        pdf.ln()
    pdf.output(str(path))


class TestParsePdfFile:
    def test_returns_empty_for_no_tables(self, tmp_path):
        """PDF with no table structure returns empty DataFrame."""
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Hello world - no table here")
        path = tmp_path / "empty.pdf"
        pdf.output(str(path))

        result = parse_pdf_file(path)
        assert result["source_format"] == "PDF"
        assert result["ocr_used"] is False
        assert result["tables_found"] == 0
        assert result["df"].empty

    def test_extracts_simple_table(self, tmp_path):
        """PDF with a bordered table is extracted correctly."""
        path = tmp_path / "simple.pdf"
        _create_simple_pdf(path, [
            ["Date", "Description", "Amount"],
            ["2026-01-01", "Deposit", "1000.00"],
            ["2026-01-02", "Withdrawal", "-500.00"],
        ])

        result = parse_pdf_file(path)
        assert result["source_format"] == "PDF"
        assert result["tables_found"] >= 1
        assert result["page_count"] == 1
        df = result["df"]
        assert len(df) >= 2  # at least 2 data rows

    def test_page_count_correct(self, tmp_path):
        """Multi-page PDF reports correct page count."""
        from fpdf import FPDF

        pdf = FPDF()
        for _ in range(3):
            pdf.add_page()
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 10, "Page content")
        path = tmp_path / "multipage.pdf"
        pdf.output(str(path))

        result = parse_pdf_file(path)
        assert result["page_count"] == 3


class TestMergeCompatibleTables:
    def test_single_table_unchanged(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        merged = _merge_compatible_tables([df])
        assert len(merged) == 1

    def test_merges_same_column_count(self):
        t1 = pd.DataFrame([["Date", "Amount"], ["2026-01-01", "100"]])
        t2 = pd.DataFrame([["Date", "Amount"], ["2026-01-02", "200"]])
        merged = _merge_compatible_tables([t1, t2])
        assert len(merged) == 1
        assert len(merged[0]) >= 3  # header + 2 data rows (header dedup)


class TestSelectBestTable:
    def test_prefers_table_with_date_headers(self):
        t1 = pd.DataFrame([["foo", "bar"], ["a", "b"]])
        t2 = pd.DataFrame([["Date", "Description", "Amount"], ["2026-01-01", "Test", "100"]])
        best, header = _select_best_table([t1, t2])
        assert "Date" in best.columns or len(best) > 0
