"""Tests for page renderer module."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import create_text_pdf


class TestRenderer:
    """Tests for page rendering."""

    def test_render_page_to_pil(self, source_dir):
        """Should render a page to a PIL Image."""
        from pdfnotes.pdf_reader import PDFDocument
        from pdfnotes.renderer import render_page_to_pil

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Hello"])

        with PDFDocument(pdf_path) as doc:
            page = doc.get_page(0)
            img = render_page_to_pil(page, dpi=200)

            assert isinstance(img, Image.Image)
            assert img.mode == "RGB"
            assert img.width > 0
            assert img.height > 0

    def test_render_at_different_dpi(self, source_dir):
        """Higher DPI should produce larger images."""
        from pdfnotes.pdf_reader import PDFDocument
        from pdfnotes.renderer import render_page_to_pil

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Hello"])

        with PDFDocument(pdf_path) as doc:
            page = doc.get_page(0)
            img_100 = render_page_to_pil(page, dpi=100)
            img_300 = render_page_to_pil(page, dpi=300)

            assert img_300.width > img_100.width
            assert img_300.height > img_100.height

    def test_render_multiple_pages(self, source_dir):
        """Should render different pages independently."""
        from pdfnotes.pdf_reader import PDFDocument
        from pdfnotes.renderer import render_page_to_pil

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["P1", "P2"])

        with PDFDocument(pdf_path) as doc:
            img1 = render_page_to_pil(doc.get_page(0))
            img2 = render_page_to_pil(doc.get_page(1))

            assert isinstance(img1, Image.Image)
            assert isinstance(img2, Image.Image)
