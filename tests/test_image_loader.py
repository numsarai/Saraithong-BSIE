"""Tests for core/image_loader.py — OCR-based table extraction."""
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from core.image_loader import _build_table_from_ocr, EASYOCR_AVAILABLE


class TestBuildTableFromOcr:
    """Unit tests for table reconstruction from OCR bounding boxes."""

    def test_empty_results_returns_empty_df(self):
        df, header = _build_table_from_ocr([])
        assert df.empty
        assert header == 0

    def test_single_row_returns_empty(self):
        """Need at least 2 rows (header + data) to form a table."""
        results = [
            ([[0, 0], [100, 0], [100, 20], [0, 20]], "Date", 0.9),
        ]
        df, header = _build_table_from_ocr(results)
        assert df.empty

    def test_basic_two_row_table(self):
        """Two rows of OCR results should produce a 1-row DataFrame."""
        results = [
            # Header row (y ~= 10)
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "Date", 0.95),
            ([[60, 0], [150, 0], [150, 20], [60, 20]], "Amount", 0.90),
            # Data row (y ~= 40)
            ([[0, 30], [50, 30], [50, 50], [0, 50]], "2026-01-01", 0.88),
            ([[60, 30], [150, 30], [150, 50], [60, 50]], "1000.00", 0.92),
        ]
        df, header = _build_table_from_ocr(results)
        assert not df.empty
        assert len(df) == 1
        assert header == 0

    def test_low_confidence_filtered(self):
        """Results below confidence threshold are dropped."""
        results = [
            ([[0, 0], [50, 0], [50, 20], [0, 20]], "Date", 0.95),
            ([[60, 0], [150, 0], [150, 20], [60, 20]], "Amount", 0.90),
            ([[0, 30], [50, 30], [50, 50], [0, 50]], "2026-01-01", 0.1),  # too low
            ([[60, 30], [150, 30], [150, 50], [60, 50]], "1000.00", 0.05),  # too low
        ]
        df, header = _build_table_from_ocr(results)
        # Only header row passes, so single row → empty
        assert df.empty

    def test_row_grouping_by_y_proximity(self):
        """Boxes with close Y coordinates are grouped into the same row."""
        results = [
            ([[0, 10], [50, 10], [50, 25], [0, 25]], "Date", 0.9),
            ([[60, 12], [150, 12], [150, 27], [60, 27]], "Desc", 0.9),
            ([[160, 8], [250, 8], [250, 23], [160, 23]], "Amount", 0.9),
            # Data row 1 (y ~= 45)
            ([[0, 40], [50, 40], [50, 55], [0, 55]], "01/01", 0.85),
            ([[60, 42], [150, 42], [150, 57], [60, 57]], "Test", 0.87),
            ([[160, 38], [250, 38], [250, 53], [160, 53]], "100", 0.9),
        ]
        df, header = _build_table_from_ocr(results)
        assert len(df) == 1
        assert len(df.columns) == 3


class TestEasyOCRAvailability:
    def test_easyocr_flag_is_bool(self):
        assert isinstance(EASYOCR_AVAILABLE, bool)

    @patch("core.image_loader.EASYOCR_AVAILABLE", False)
    @patch("core.image_loader._reader", None)
    def test_missing_easyocr_raises_error(self):
        from core.image_loader import _get_reader
        with pytest.raises(RuntimeError, match="EasyOCR"):
            _get_reader()
