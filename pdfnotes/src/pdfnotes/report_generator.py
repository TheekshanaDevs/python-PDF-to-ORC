"""Report generator — create the JSON processing report."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pdfnotes import __app_name__, __version__
from pdfnotes.exceptions import PDFNotesError

logger = logging.getLogger("pdfnotes.report_generator")


def determine_overall_status(
    pdfs_completed: int,
    pdfs_failed: int,
    pages_failed: int,
    pdfs_discovered: int,
) -> str:
    """Determine the overall run status.

    Returns:
        One of: "completed", "completed_with_warnings", "failed", "no_pdfs".
    """
    if pdfs_discovered == 0:
        return "no_pdfs"
    if pdfs_failed == pdfs_discovered:
        return "failed"
    if pdfs_failed > 0 or pages_failed > 0:
        return "completed_with_warnings"
    if pdfs_completed == pdfs_discovered:
        return "completed"
    return "completed_with_warnings"


def generate_report(
    report_path: Path,
    source_dir: Path,
    output_dir: Path,
    ocr_lang: str,
    image_format: str,
    image_dpi: int,
    started_at: datetime,
    finished_at: datetime,
    pdf_results: list[dict],
    skipped_pdfs: list[dict] | None = None,
) -> dict:
    """Generate and save the JSON processing report.

    Args:
        report_path: Where to write the report.
        source_dir: Source folder path.
        output_dir: Output folder path.
        ocr_lang: OCR language string used.
        image_format: Image format used.
        image_dpi: DPI setting used.
        started_at: When processing began.
        finished_at: When processing finished.
        pdf_results: List of per-PDF result dicts.
        skipped_pdfs: List of dicts for skipped PDFs (path, reason).

    Returns:
        The complete report dict.
    """
    # Aggregate statistics
    pdfs_discovered = len(pdf_results) + (len(skipped_pdfs) if skipped_pdfs else 0)
    pdfs_completed = sum(1 for r in pdf_results if r.get("status") in ("completed", "completed_with_warnings"))
    pdfs_failed = sum(1 for r in pdf_results if r.get("status") == "failed")
    pdfs_skipped = len(skipped_pdfs) if skipped_pdfs else 0

    pages_discovered = sum(r.get("page_count", 0) for r in pdf_results)
    pages_completed = sum(r.get("pages_completed", 0) for r in pdf_results)
    pages_failed = sum(r.get("pages_failed", 0) for r in pdf_results)
    images_created = sum(r.get("images_created", 0) for r in pdf_results)
    md_files_created = sum(1 for r in pdf_results if r.get("markdown_written", False))

    overall_status = determine_overall_status(
        pdfs_completed, pdfs_failed, pages_failed, len(pdf_results),
    )

    duration = (finished_at - started_at).total_seconds()

    report = {
        "application": __app_name__,
        "version": __version__,
        "status": overall_status,
        "source_directory": str(source_dir),
        "output_directory": str(output_dir),
        "ocr_languages": ocr_lang,
        "image_format": image_format,
        "image_dpi": image_dpi,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(duration, 2),
        "summary": {
            "pdfs_discovered": pdfs_discovered,
            "pdfs_completed": pdfs_completed,
            "pdfs_failed": pdfs_failed,
            "pdfs_skipped": pdfs_skipped,
            "pages_discovered": pages_discovered,
            "pages_completed": pages_completed,
            "pages_failed": pages_failed,
            "images_created": images_created,
            "markdown_files_created": md_files_created,
        },
        "files": pdf_results,
    }

    if skipped_pdfs:
        report["skipped_files"] = skipped_pdfs

    # Write report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = report_path.with_suffix(".json.tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        tmp_path.replace(report_path)
        logger.info("Report saved: %s", report_path)
    except OSError as e:
        logger.error("Failed to write report: %s", e)
        # Don't raise — the report is supplementary

    return report
