"""Integration tests — end-to-end processing pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import create_text_pdf, has_tesseract, skip_no_tesseract


@skip_no_tesseract
class TestEndToEnd:
    """End-to-end integration tests requiring Tesseract."""

    def test_process_single_pdf(self, source_dir):
        """Should process a single PDF and create all outputs."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(
            source_dir / "lecture.pdf",
            ["Introduction to Testing\n\nThis is page 1.", "Page 2 content here."],
        )

        config = ProcessingConfig(
            source_dir=source_dir,
            ocr_lang="eng",
            image_format="png",
            image_dpi=200,
        )

        exit_code = run_processing(config)

        # Check exit code
        assert exit_code == 0

        # Check output structure
        result_dir = source_dir / "Result"
        assert result_dir.exists()
        assert (result_dir / "OCR").exists()
        assert (result_dir / "Images").exists()

        # Check Markdown
        md = result_dir / "OCR" / "lecture.md"
        assert md.exists()
        content = md.read_text(encoding="utf-8")
        assert "lecture" in content.lower()
        assert "Page 1" in content or "page 1" in content.lower()
        assert "Page 2" in content or "page 2" in content.lower()

        # Check combined
        combined = result_dir / "OCR" / "semester_combined.md"
        assert combined.exists()
        combined_content = combined.read_text(encoding="utf-8")
        assert "Semester Lecture Notes" in combined_content

        # Check images
        img_dir = result_dir / "Images" / "lecture"
        assert img_dir.exists()
        images = list(img_dir.glob("*.png"))
        assert len(images) == 2

        # Check report
        report_path = result_dir / "report.json"
        assert report_path.exists()
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["pdfs_completed"] == 1
        assert report["summary"]["pages_completed"] == 2
        assert report["summary"]["images_created"] == 2

    def test_process_multiple_pdfs(self, source_dir):
        """Should process multiple PDFs."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(source_dir / "lecture_01.pdf", ["Lecture 1 content"])
        create_text_pdf(source_dir / "lecture_02.pdf", ["Lecture 2 content"])
        create_text_pdf(source_dir / "notes.pdf", ["Notes content"])

        config = ProcessingConfig(source_dir=source_dir, ocr_lang="eng")
        exit_code = run_processing(config)
        assert exit_code == 0

        result_dir = source_dir / "Result"
        md_files = list((result_dir / "OCR").glob("*.md"))
        # Should have 3 individual + 1 combined
        assert len(md_files) == 4

        with open(result_dir / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["pdfs_completed"] == 3

    def test_resume_processing(self, source_dir):
        """Should resume from saved state."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(source_dir / "test.pdf", ["Page 1", "Page 2"])

        config = ProcessingConfig(source_dir=source_dir, ocr_lang="eng")

        # First run
        exit_code = run_processing(config)
        assert exit_code == 0

        # Second run with resume — should skip completed work
        config.resume = True
        exit_code = run_processing(config)
        assert exit_code == 0

        # Verify no duplication in combined Markdown
        combined = source_dir / "Result" / "OCR" / "semester_combined.md"
        content = combined.read_text(encoding="utf-8")
        # The content should appear exactly once
        assert content.count("# test") <= 2  # heading + toc entry

    def test_custom_output_dir(self, source_dir, output_dir):
        """Should use custom output directory."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(source_dir / "test.pdf", ["Content"])

        config = ProcessingConfig(
            source_dir=source_dir,
            output_dir=output_dir,
            ocr_lang="eng",
        )

        exit_code = run_processing(config)
        assert exit_code == 0

        assert (output_dir / "OCR" / "test.md").exists()
        assert (output_dir / "Images" / "test").exists()

    def test_jpeg_output(self, source_dir):
        """Should save images as JPEG when configured."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(source_dir / "test.pdf", ["Content"])

        config = ProcessingConfig(
            source_dir=source_dir,
            ocr_lang="eng",
            image_format="jpeg",
        )

        exit_code = run_processing(config)
        assert exit_code == 0

        img_dir = source_dir / "Result" / "Images" / "test"
        jpg_images = list(img_dir.glob("*.jpg"))
        assert len(jpg_images) == 1

    def test_original_pdfs_unchanged(self, source_dir):
        """Original PDFs should not be modified."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        pdf_path = create_text_pdf(source_dir / "test.pdf", ["Content"])
        original_size = pdf_path.stat().st_size
        original_mtime = pdf_path.stat().st_mtime

        config = ProcessingConfig(source_dir=source_dir, ocr_lang="eng")
        run_processing(config)

        assert pdf_path.stat().st_size == original_size

    def test_process_continues_after_one_failure(self, source_dir):
        """Should continue with other PDFs when one is corrupt (skipped at discovery)."""
        from pdfnotes.config import ProcessingConfig
        from pdfnotes.processor import run_processing

        create_text_pdf(source_dir / "good.pdf", ["Good content"])
        # Create a corrupt PDF — this gets caught at discovery and skipped
        (source_dir / "bad.pdf").write_bytes(b"not a real PDF file")

        config = ProcessingConfig(source_dir=source_dir, ocr_lang="eng")
        exit_code = run_processing(config)

        # The corrupt PDF is skipped at discovery; the good one succeeds → exit 0
        assert exit_code == 0

        # Good PDF should still be processed
        assert (source_dir / "Result" / "OCR" / "good.md").exists()

        # Report should list the skipped file
        import json
        with open(source_dir / "Result" / "report.json", encoding="utf-8") as f:
            report = json.load(f)
        assert report["summary"]["pdfs_completed"] == 1
        assert len(report.get("skipped_files", [])) == 1
