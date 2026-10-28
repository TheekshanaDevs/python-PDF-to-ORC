"""Tests for image writer module."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


class TestImageWriter:
    """Tests for saving page images."""

    def test_save_png_image(self, tmp_dir):
        """Should save a PNG image."""
        from pdfnotes.image_writer import save_page_image

        img = Image.new("RGB", (200, 300), "white")
        path = tmp_dir / "page_001.png"

        size = save_page_image(img, path, "png")

        assert path.exists()
        assert size > 0
        # Verify it's a valid PNG
        with Image.open(path) as loaded:
            assert loaded.format == "PNG"

    def test_save_jpeg_image(self, tmp_dir):
        """Should save a JPEG image."""
        from pdfnotes.image_writer import save_page_image

        img = Image.new("RGB", (200, 300), "white")
        path = tmp_dir / "page_001.jpg"

        size = save_page_image(img, path, "jpeg")

        assert path.exists()
        assert size > 0

    def test_get_image_path(self, tmp_dir):
        """Should compute correct image paths."""
        from pdfnotes.image_writer import get_image_path

        path = get_image_path(tmp_dir, "lecture1", 1, 10, "png")
        assert path == tmp_dir / "lecture1" / "lecture1_page_001.png"

        path = get_image_path(tmp_dir, "lecture1", 5, 100, "png")
        assert path == tmp_dir / "lecture1" / "lecture1_page_005.png"

        path = get_image_path(tmp_dir, "lecture1", 1, 1000, "png")
        assert path == tmp_dir / "lecture1" / "lecture1_page_0001.png"

    def test_get_image_path_jpeg(self, tmp_dir):
        """JPEG format should use .jpg extension."""
        from pdfnotes.image_writer import get_image_path

        path = get_image_path(tmp_dir, "test", 1, 10, "jpeg")
        assert path.suffix == ".jpg"

    def test_atomic_write_no_tmp_file(self, tmp_dir):
        """No .tmp file should remain after saving."""
        from pdfnotes.image_writer import save_page_image

        img = Image.new("RGB", (100, 100), "white")
        path = tmp_dir / "test.png"

        save_page_image(img, path, "png")

        assert not path.with_suffix(".png.tmp").exists()

    def test_verify_image_valid(self, tmp_dir):
        """Should verify a valid image."""
        from pdfnotes.image_writer import save_page_image, verify_image

        img = Image.new("RGB", (100, 100), "blue")
        path = tmp_dir / "valid.png"
        save_page_image(img, path, "png")

        assert verify_image(path)

    def test_verify_image_invalid(self, tmp_dir):
        """Should reject an invalid image file."""
        from pdfnotes.image_writer import verify_image

        bad = tmp_dir / "bad.png"
        bad.write_bytes(b"not an image")

        assert not verify_image(bad)

    def test_verify_image_missing(self, tmp_dir):
        """Should return False for missing files."""
        from pdfnotes.image_writer import verify_image

        assert not verify_image(tmp_dir / "nonexistent.png")

    def test_verify_image_empty(self, tmp_dir):
        """Should reject empty files."""
        from pdfnotes.image_writer import verify_image

        empty = tmp_dir / "empty.png"
        empty.write_bytes(b"")

        assert not verify_image(empty)

    def test_creates_subdirectory(self, tmp_dir):
        """Should create the parent directory if needed."""
        from pdfnotes.image_writer import save_page_image

        img = Image.new("RGB", (100, 100), "red")
        path = tmp_dir / "sub" / "dir" / "image.png"

        save_page_image(img, path, "png")

        assert path.exists()
