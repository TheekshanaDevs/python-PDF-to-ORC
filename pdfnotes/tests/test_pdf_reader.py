"""Tests for PDF reader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import create_text_pdf


class TestPDFReader:
    """Tests for PDFDocument."""

    def test_open_valid_pdf(self, source_dir):
        """Should open a valid PDF successfully."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Hello World"])

        with PDFDocument(pdf_path) as doc:
            assert doc.page_count == 1

    def test_extract_text(self, source_dir):
        """Should extract native text from a page."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(
            source_dir / "test.pdf",
            ["First page content\nSecond line here"],
        )

        with PDFDocument(pdf_path) as doc:
            text = doc.extract_page_text(0)
            assert "First page" in text
            assert "Second line" in text

    def test_multi_page(self, source_dir):
        """Should handle multi-page PDFs."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(
            source_dir / "multi.pdf",
            ["Page 1 text", "Page 2 text", "Page 3 text"],
        )

        with PDFDocument(pdf_path) as doc:
            assert doc.page_count == 3
            assert "Page 1" in doc.extract_page_text(0)
            assert "Page 2" in doc.extract_page_text(1)
            assert "Page 3" in doc.extract_page_text(2)

    def test_metadata(self, source_dir):
        """Should return PDF metadata."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Content"])

        with PDFDocument(pdf_path) as doc:
            meta = doc.metadata
            assert isinstance(meta, dict)

    def test_corrupt_pdf_raises(self, source_dir):
        """Should raise PDFCorruptError for corrupt files."""
        from pdfnotes.pdf_reader import PDFDocument
        from pdfnotes.exceptions import PDFCorruptError

        corrupt = source_dir / "corrupt.pdf"
        corrupt.write_bytes(b"This is not a PDF file at all")

        with pytest.raises(PDFCorruptError):
            with PDFDocument(corrupt) as doc:
                pass

    def test_context_manager_closes(self, source_dir):
        """Should close document on context exit."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Content"])
        doc = PDFDocument(pdf_path)
        doc.__enter__()
        assert doc._doc is not None
        doc.__exit__(None, None, None)
        assert doc._doc is None

    def test_get_page(self, source_dir):
        """Should return a fitz.Page object."""
        from pdfnotes.pdf_reader import PDFDocument

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Content"])

        with PDFDocument(pdf_path) as doc:
            page = doc.get_page(0)
            assert page is not None
