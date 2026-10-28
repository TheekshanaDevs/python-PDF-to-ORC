"""Shared test fixtures and helpers."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

# Check for Tesseract availability
_HAS_TESSERACT = shutil.which("tesseract") is not None


def has_tesseract() -> bool:
    return _HAS_TESSERACT


def has_tesseract_lang(lang: str) -> bool:
    """Check if a specific Tesseract language is installed."""
    if not _HAS_TESSERACT:
        return False
    import subprocess

    result = subprocess.run(
        ["tesseract", "--list-langs"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return lang in output


skip_no_tesseract = pytest.mark.skipif(
    not _HAS_TESSERACT,
    reason="Tesseract OCR not installed",
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test output."""
    d = tempfile.mkdtemp(prefix="pdfnotes_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def source_dir(tmp_dir):
    """Create a source directory with test PDFs."""
    src = tmp_dir / "source"
    src.mkdir()
    return src


@pytest.fixture
def output_dir(tmp_dir):
    """Create an output directory."""
    out = tmp_dir / "output"
    out.mkdir()
    return out


def create_text_pdf(path: Path, pages: list[str]) -> Path:
    """Create a simple PDF with text pages using reportlab.

    Args:
        path: Output PDF path.
        pages: List of text content, one per page.

    Returns:
        Path to the created PDF.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed (install with: pip install reportlab)")

    c = canvas.Canvas(str(path), pagesize=letter)
    for page_text in pages:
        # Draw text with line breaks
        text_obj = c.beginText(72, 700)
        text_obj.setFont("Helvetica", 12)
        for line in page_text.split("\n"):
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.showPage()
    c.save()
    return path


def create_image_pdf(path: Path, num_pages: int = 1) -> Path:
    """Create a PDF containing images with text (for OCR testing).

    Creates pages that have text rendered as images rather than native PDF text.

    Args:
        path: Output PDF path.
        num_pages: Number of pages.

    Returns:
        Path to the created PDF.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    from PIL import Image, ImageDraw, ImageFont

    c = canvas.Canvas(str(path), pagesize=letter)

    for i in range(num_pages):
        # Create an image with text
        img = Image.new("RGB", (600, 800), "white")
        draw = ImageDraw.Draw(img)

        # Use default font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except (IOError, OSError):
            font = ImageFont.load_default()

        draw.text((50, 50), f"Page {i + 1}", fill="black", font=font)
        draw.text((50, 100), "This is test content rendered as an image.", fill="black", font=font)
        draw.text((50, 150), "OCR should be able to read this text.", fill="black", font=font)

        # Save temporary image
        img_path = path.parent / f"_temp_page_{i}.png"
        img.save(str(img_path))

        # Add image to PDF
        c.drawImage(str(img_path), 0, 0, width=612, height=792)
        c.showPage()

        # Clean up temp image
        img_path.unlink()

    c.save()
    return path


def create_empty_pdf(path: Path) -> Path:
    """Create a valid but empty PDF (no pages). This is tricky - we create then remove pages."""
    # Actually, reportlab always creates at least one page if showPage is called.
    # Let's create a minimal PDF with fitz instead.
    try:
        import pymupdf as fitz
        doc = fitz.open()
        # Don't add any pages — results in 0-page PDF
        doc.save(str(path))
        doc.close()
        return path
    except ImportError:
        pytest.skip("PyMuPDF not installed")
