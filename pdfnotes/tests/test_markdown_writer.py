"""Tests for Markdown writer module."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestPDFMarkdown:
    """Tests for per-PDF Markdown generation."""

    def test_write_single_pdf_markdown(self, tmp_dir):
        """Should create a valid Markdown file."""
        from pdfnotes.markdown_writer import write_pdf_markdown

        md_path = tmp_dir / "test.md"
        img_dir = tmp_dir / "images"
        img_dir.mkdir()

        # Create a fake image
        img_path = img_dir / "test_page_001.png"
        img_path.write_bytes(b"fake image")

        size = write_pdf_markdown(
            output_path=md_path,
            pdf_name="Test Lecture",
            source_filename="Test_Lecture.pdf",
            page_count=2,
            page_contents={1: "Page 1 content here", 2: "Page 2 content"},
            page_image_paths={1: img_path},
        )

        assert md_path.exists()
        assert size > 0

        content = md_path.read_text(encoding="utf-8")
        assert "# Test Lecture" in content
        assert "**Source:** Test_Lecture.pdf" in content
        assert "**Pages:** 2" in content
        assert "## Page 1" in content
        assert "## Page 2" in content
        assert "Page 1 content here" in content
        assert "Page 2 content" in content

    def test_page_without_content(self, tmp_dir):
        """Pages with no text should show a notice."""
        from pdfnotes.markdown_writer import write_pdf_markdown

        md_path = tmp_dir / "empty.md"

        write_pdf_markdown(
            output_path=md_path,
            pdf_name="Empty",
            source_filename="empty.pdf",
            page_count=1,
            page_contents={1: ""},
            page_image_paths={},
        )

        content = md_path.read_text(encoding="utf-8")
        assert "No text content" in content

    def test_image_link_in_markdown(self, tmp_dir):
        """Should include relative image links."""
        from pdfnotes.markdown_writer import write_pdf_markdown

        ocr_dir = tmp_dir / "OCR"
        ocr_dir.mkdir()
        img_dir = tmp_dir / "Images" / "lecture"
        img_dir.mkdir(parents=True)

        img_path = img_dir / "lecture_page_001.png"
        img_path.write_bytes(b"img")

        md_path = ocr_dir / "lecture.md"

        write_pdf_markdown(
            output_path=md_path,
            pdf_name="Lecture",
            source_filename="lecture.pdf",
            page_count=1,
            page_contents={1: "Content"},
            page_image_paths={1: img_path},
        )

        content = md_path.read_text(encoding="utf-8")
        assert "View original page image" in content
        assert "Images" in content

    def test_atomic_write(self, tmp_dir):
        """No .tmp file should remain after successful write."""
        from pdfnotes.markdown_writer import write_pdf_markdown

        md_path = tmp_dir / "test.md"

        write_pdf_markdown(
            output_path=md_path,
            pdf_name="Test",
            source_filename="test.pdf",
            page_count=1,
            page_contents={1: "Content"},
            page_image_paths={},
        )

        assert md_path.exists()
        assert not md_path.with_suffix(".md.tmp").exists()


class TestCombinedMarkdown:
    """Tests for combined semester Markdown."""

    def test_write_combined_markdown(self, tmp_dir):
        """Should create a combined Markdown with ToC."""
        from pdfnotes.markdown_writer import write_pdf_markdown, write_combined_markdown

        ocr_dir = tmp_dir / "OCR"
        ocr_dir.mkdir()

        # Create individual files
        for name in ["Lecture_01", "Lecture_02"]:
            write_pdf_markdown(
                output_path=ocr_dir / f"{name}.md",
                pdf_name=name.replace("_", " "),
                source_filename=f"{name}.pdf",
                page_count=1,
                page_contents={1: f"Content of {name}"},
                page_image_paths={},
            )

        combined_path = ocr_dir / "semester_combined.md"
        entries = [
            {
                "name": "Lecture 01",
                "source": "Lecture_01.pdf",
                "markdown_path": str(ocr_dir / "Lecture_01.md"),
                "status": "completed",
            },
            {
                "name": "Lecture 02",
                "source": "Lecture_02.pdf",
                "markdown_path": str(ocr_dir / "Lecture_02.md"),
                "status": "completed",
            },
        ]

        size = write_combined_markdown(combined_path, entries)

        assert combined_path.exists()
        content = combined_path.read_text(encoding="utf-8")
        assert "Semester Lecture Notes" in content
        assert "Table of Contents" in content
        assert "Lecture 01" in content
        assert "Lecture 02" in content
        assert "Content of Lecture_01" in content
        assert "Content of Lecture_02" in content

    def test_combined_includes_failed_pdfs(self, tmp_dir):
        """Failed PDFs should be listed in the combined Markdown."""
        from pdfnotes.markdown_writer import write_combined_markdown

        combined_path = tmp_dir / "combined.md"

        entries = [
            {
                "name": "Working",
                "source": "working.pdf",
                "markdown_path": "",
                "status": "failed",
                "error": "Corrupt file",
            },
        ]

        write_combined_markdown(combined_path, entries)
        content = combined_path.read_text(encoding="utf-8")
        assert "Failed" in content
        assert "Working" in content

    def test_no_duplicate_content(self, tmp_dir):
        """Running combined twice should not duplicate content."""
        from pdfnotes.markdown_writer import write_pdf_markdown, write_combined_markdown

        ocr_dir = tmp_dir / "OCR"
        ocr_dir.mkdir()

        write_pdf_markdown(
            output_path=ocr_dir / "test.md",
            pdf_name="Test",
            source_filename="test.pdf",
            page_count=1,
            page_contents={1: "Unique content"},
            page_image_paths={},
        )

        entries = [{
            "name": "Test",
            "source": "test.pdf",
            "markdown_path": str(ocr_dir / "test.md"),
            "status": "completed",
        }]

        combined = ocr_dir / "combined.md"
        write_combined_markdown(combined, entries)
        write_combined_markdown(combined, entries)  # Second write

        content = combined.read_text(encoding="utf-8")
        assert content.count("Unique content") == 1
