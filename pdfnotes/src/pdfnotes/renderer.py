"""Page renderer — render PDF pages to images using PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
from PIL import Image

from pdfnotes.exceptions import PageRenderError

logger = logging.getLogger("pdfnotes.renderer")


def render_page_to_pil(page: fitz.Page, dpi: int = 200) -> Image.Image:
    """Render a PyMuPDF page to a Pillow Image at the specified DPI.

    Args:
        page: A fitz.Page object.
        dpi: Target resolution in dots per inch.

    Returns:
        A PIL Image in RGB mode.

    Raises:
        PageRenderError: If rendering fails.
    """
    try:
        zoom = dpi / 72.0  # PDF default is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        return img
    except Exception as e:
        raise PageRenderError(
            f"Failed to render page {page.number + 1}: {e}"
        ) from e


def get_page_dimensions(page: fitz.Page) -> tuple[float, float]:
    """Return the page dimensions (width, height) in points."""
    rect = page.rect
    return rect.width, rect.height
