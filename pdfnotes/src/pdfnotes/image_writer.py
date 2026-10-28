"""Image writer — save rendered page images to disk."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from pdfnotes.exceptions import ImageWriteError

logger = logging.getLogger("pdfnotes.image_writer")


def _ensure_dir(directory: Path) -> None:
    """Create directory and parents if they don't exist."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ImageWriteError(f"Cannot create image directory: {directory} — {e}") from e


def _page_number_format(page_num: int, total_pages: int) -> str:
    """Format page number with appropriate zero-padding.

    Uses at least 3 digits, or more if the PDF has over 999 pages.
    """
    digits = max(3, len(str(total_pages)))
    return str(page_num).zfill(digits)


def get_image_path(
    images_dir: Path,
    pdf_relative_name: str,
    page_num: int,
    total_pages: int,
    image_format: str = "png",
) -> Path:
    """Compute the output path for a page image.

    Args:
        images_dir: Base images directory (e.g., Result/Images).
        pdf_relative_name: The relative name for the PDF (used as subfolder).
        page_num: 1-based page number.
        total_pages: Total pages in the PDF.
        image_format: Image format extension ("png" or "jpeg"/"jpg").

    Returns:
        Full path to the image file.
    """
    ext = "jpg" if image_format.lower() in ("jpeg", "jpg") else "png"
    page_str = _page_number_format(page_num, total_pages)
    filename = f"{pdf_relative_name}_page_{page_str}.{ext}"
    return images_dir / pdf_relative_name / filename


def save_page_image(
    image: Image.Image,
    output_path: Path,
    image_format: str = "png",
) -> int:
    """Save a rendered page image to disk.

    Writes to a temporary file first, then renames for atomicity.

    Args:
        image: PIL Image to save.
        output_path: Target file path.
        image_format: "png" or "jpeg"/"jpg".

    Returns:
        File size in bytes.

    Raises:
        ImageWriteError: If saving fails.
    """
    _ensure_dir(output_path.parent)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        if image_format.lower() in ("jpeg", "jpg"):
            image.save(str(tmp_path), format="JPEG", quality=90)
        else:
            image.save(str(tmp_path), format="PNG", optimize=True)

        # Atomic rename
        tmp_path.replace(output_path)

        size = output_path.stat().st_size
        if size == 0:
            raise ImageWriteError(f"Saved image is empty: {output_path}")

        logger.debug("Saved image: %s (%d bytes)", output_path.name, size)
        return size

    except ImageWriteError:
        raise
    except OSError as e:
        # Clean up temp file on failure
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ImageWriteError(f"Failed to save image {output_path}: {e}") from e
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ImageWriteError(f"Unexpected error saving image {output_path}: {e}") from e


def verify_image(path: Path) -> bool:
    """Verify that an image file exists and is a valid image.

    Args:
        path: Path to the image file.

    Returns:
        True if the image is valid, False otherwise.
    """
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False
