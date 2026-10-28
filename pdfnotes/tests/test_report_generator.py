"""Tests for report generator module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestReportGenerator:
    """Tests for JSON report generation."""

    def test_generate_valid_json_report(self, tmp_dir):
        """Should generate valid JSON."""
        from pdfnotes.report_generator import generate_report

        report_path = tmp_dir / "report.json"
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)

        pdf_results = [
            {
                "source_path": "/test/lecture1.pdf",
                "relative_name": "lecture1",
                "page_count": 5,
                "pages_completed": 5,
                "pages_failed": 0,
                "images_created": 5,
                "status": "completed",
                "markdown_written": True,
            },
        ]

        report = generate_report(
            report_path=report_path,
            source_dir=Path("/test"),
            output_dir=Path("/test/Result"),
            ocr_lang="eng",
            image_format="png",
            image_dpi=200,
            started_at=started,
            finished_at=finished,
            pdf_results=pdf_results,
        )

        assert report_path.exists()

        # Verify valid JSON
        with open(report_path, encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["status"] == "completed"
        assert loaded["summary"]["pdfs_completed"] == 1
        assert loaded["summary"]["pages_completed"] == 5

    def test_report_with_failures(self, tmp_dir):
        """Report should reflect failures correctly."""
        from pdfnotes.report_generator import generate_report

        report_path = tmp_dir / "report.json"
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 10, 5, 0, tzinfo=timezone.utc)

        pdf_results = [
            {
                "source_path": "/test/ok.pdf",
                "page_count": 3,
                "pages_completed": 3,
                "pages_failed": 0,
                "images_created": 3,
                "status": "completed",
                "markdown_written": True,
            },
            {
                "source_path": "/test/bad.pdf",
                "page_count": 2,
                "pages_completed": 0,
                "pages_failed": 2,
                "images_created": 0,
                "status": "failed",
                "markdown_written": False,
            },
        ]

        report = generate_report(
            report_path=report_path,
            source_dir=Path("/test"),
            output_dir=Path("/test/Result"),
            ocr_lang="eng",
            image_format="png",
            image_dpi=200,
            started_at=started,
            finished_at=finished,
            pdf_results=pdf_results,
        )

        assert report["status"] == "completed_with_warnings"
        assert report["summary"]["pdfs_completed"] == 1
        assert report["summary"]["pdfs_failed"] == 1

    def test_report_with_skipped_pdfs(self, tmp_dir):
        """Report should include skipped files."""
        from pdfnotes.report_generator import generate_report

        report_path = tmp_dir / "report.json"
        started = datetime(2024, 1, 1, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, tzinfo=timezone.utc)

        report = generate_report(
            report_path=report_path,
            source_dir=Path("/test"),
            output_dir=Path("/test/Result"),
            ocr_lang="eng",
            image_format="png",
            image_dpi=200,
            started_at=started,
            finished_at=finished,
            pdf_results=[],
            skipped_pdfs=[{"path": "/test/locked.pdf", "reason": "Password-protected"}],
        )

        assert "skipped_files" in report
        assert len(report["skipped_files"]) == 1

    def test_determine_status(self):
        """Test status determination logic."""
        from pdfnotes.report_generator import determine_overall_status

        assert determine_overall_status(5, 0, 0, 5) == "completed"
        assert determine_overall_status(4, 1, 0, 5) == "completed_with_warnings"
        assert determine_overall_status(5, 0, 2, 5) == "completed_with_warnings"
        assert determine_overall_status(0, 5, 0, 5) == "failed"
        assert determine_overall_status(0, 0, 0, 0) == "no_pdfs"

    def test_report_includes_duration(self, tmp_dir):
        """Report should calculate duration."""
        from pdfnotes.report_generator import generate_report

        report_path = tmp_dir / "report.json"
        started = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2024, 1, 1, 10, 5, 30, tzinfo=timezone.utc)

        report = generate_report(
            report_path=report_path,
            source_dir=Path("/test"),
            output_dir=Path("/test/Result"),
            ocr_lang="eng",
            image_format="png",
            image_dpi=200,
            started_at=started,
            finished_at=finished,
            pdf_results=[],
        )

        assert report["duration_seconds"] == 330.0
