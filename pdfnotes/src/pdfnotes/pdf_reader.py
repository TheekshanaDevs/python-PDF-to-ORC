"""PDF reader — open PDFs, extract native text, and provide metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator

import pymupdf as fitz  # PyMuPDF

from pdfnotes.exceptions import PDFCorruptError, PDFPasswordError, PDFReadError

logger = logging.getLogger("pdfnotes.pdf_reader")


class PDFDocument:
    """Context-managed wrapper around a PyMuPDF document.

    Usage::

        with PDFDocument(path) as doc:
            for page_num in range(doc.page_count):
                text = doc.extract_page_text(page_num)
    """

    def __init__(self, path: Path):
        self.path = path
        self._doc: fitz.Document | None = None

    def __enter__(self) -> "PDFDocument":
        try:
            self._doc = fitz.open(str(self.path))
        except Exception as e:
            raise PDFCorruptError(f"Cannot open PDF: {self.path} — {e}") from e

        if self._doc.is_encrypted:
            if not self._doc.authenticate(""):
                self._doc.close()
                self._doc = None
                raise PDFPasswordError(f"PDF is password-protected: {self.path}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._doc is not None:
            self._doc.close()
            self._doc = None
        return False

    @property
    def doc(self) -> fitz.Document:
        if self._doc is None:
            raise PDFReadError("PDF document is not open")
        return self._doc

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def metadata(self) -> dict:
        """Return PDF metadata (title, author, etc.)."""
        return dict(self.doc.metadata) if self.doc.metadata else {}

    def extract_page_text(self, page_num: int) -> str:
        """Extract native text from a single page using PyMuPDF.

        Args:
            page_num: Zero-based page index.

        Returns:
            Extracted text string (may be empty for scanned pages).
        """
        try:
            page = self.doc[page_num]
            text = page.get_text("text")
            return text if text else ""
        except Exception as e:
            logger.warning(
                "Native text extraction failed on %s page %d: %s",
                self.path.name,
                page_num + 1,
                e,
            )
            return ""

    def extract_page_blocks(self, page_num: int) -> list[dict]:
        """Extract text blocks with position information.

        Returns a list of block dicts with keys: x0, y0, x1, y1, text, type.
        """
        try:
            page = self.doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            result = []
            for block in blocks:
                if block.get("type") == 0:  # text block
                    lines_text = []
                    for line in block.get("lines", []):
                        span_texts = [span.get("text", "") for span in line.get("spans", [])]
                        lines_text.append("".join(span_texts))
                    result.append({
                        "x0": block.get("bbox", [0])[0],
                        "y0": block.get("bbox", [0, 0])[1],
                        "x1": block.get("bbox", [0, 0, 0])[2] if len(block.get("bbox", [])) > 2 else 0,
                        "y1": block.get("bbox", [0, 0, 0, 0])[3] if len(block.get("bbox", [])) > 3 else 0,
                        "text": "\n".join(lines_text),
                        "type": "text",
                    })
            return result
        except Exception as e:
            logger.debug("Block extraction failed on %s page %d: %s", self.path.name, page_num + 1, e)
            return []

    def get_page(self, page_num: int) -> fitz.Page:
        """Return the raw fitz.Page object for rendering."""
        return self.doc[page_num]
