"""Processor — main orchestration: ties discovery, rendering, OCR, and output together."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from pdfnotes.config import ProcessingConfig
from pdfnotes.discovery import DiscoveredPDF, SkippedPDF, discover_pdfs
from pdfnotes.exceptions import (
    ImageWriteError,
    MarkdownWriteError,
    NoPDFsFoundError,
    OCRError,
    PageRenderError,
    PDFNotesError,
    PDFReadError,
)
from pdfnotes.image_writer import get_image_path, save_page_image, verify_image
from pdfnotes.logging_config import setup_logging
from pdfnotes.markdown_writer import write_combined_markdown, write_pdf_markdown
from pdfnotes.ocr_engine import find_tesseract, run_ocr, validate_languages
from pdfnotes.pdf_reader import PDFDocument
from pdfnotes.progress import RichProgress, create_progress
from pdfnotes.renderer import render_page_to_pil
from pdfnotes.report_generator import generate_report
from pdfnotes.state_manager import StateManager
from pdfnotes.text_cleaner import combine_native_and_ocr, format_page_content

logger = logging.getLogger("pdfnotes.processor")


def run_processing(config: ProcessingConfig) -> int:
    """Execute the full processing pipeline.

    Args:
        config: Processing configuration.

    Returns:
        Exit code: 0 = success, 1 = partial failure.
    """
    started_at = datetime.now(timezone.utc)

    # Set up logging
    app_logger = setup_logging(config.log_path, debug=config.debug)
    logger.info("Starting processing run")
    logger.info("Source: %s", config.source_dir)
    logger.info("Output: %s", config.resolved_output_dir)
    logger.info("OCR languages: %s", config.ocr_lang)
    logger.info("Image format: %s, DPI: %d", config.image_format, config.image_dpi)

    # Create output directories
    config.ocr_dir.mkdir(parents=True, exist_ok=True)
    config.images_dir.mkdir(parents=True, exist_ok=True)

    # Validate Tesseract
    tesseract_cmd = find_tesseract(config.tesseract_cmd)
    logger.info("Tesseract found: %s", tesseract_cmd)

    # Validate languages
    validate_languages(tesseract_cmd, config.ocr_lang)

    # Discover PDFs
    discovered, skipped = discover_pdfs(
        config.source_dir,
        recursive=config.recursive,
        output_dir=config.resolved_output_dir,
    )

    # Filter by user selection if specified
    if config.selected_files:
        selected_set = set(config.selected_files)
        discovered = [
            p for p in discovered
            if p.path.name in selected_set or p.relative_name in selected_set or str(p.path) in selected_set
        ]

    if not discovered:
        if skipped:
            logger.warning(
                "Found %d PDFs but all were skipped. Check the report for details.",
                len(skipped),
            )
            # Still generate a report
            finished_at = datetime.now(timezone.utc)
            generate_report(
                config.report_path,
                config.source_dir,
                config.resolved_output_dir,
                config.ocr_lang,
                config.image_format,
                config.image_dpi,
                started_at,
                finished_at,
                [],
                [{"path": str(s.path), "reason": s.reason} for s in skipped],
            )
            return 1
        raise NoPDFsFoundError(f"No PDF files found in: {config.source_dir}")

    # Set up progress display
    progress = create_progress()
    progress.print_header(
        str(config.source_dir),
        str(config.resolved_output_dir),
        config.ocr_lang,
        config.image_dpi,
        len(discovered),
    )

    # Open state database
    pdf_results: list[dict] = []

    with StateManager(config.state_db_path) as state:
        # Initialize state for all discovered PDFs
        for pdf in discovered:
            state.init_pdf(
                relative_name=pdf.relative_name,
                source_path=str(pdf.path),
                file_size=pdf.size_bytes,
                file_mtime=pdf.path.stat().st_mtime,
                sha256=pdf.sha256,
                page_count=pdf.page_count,
                ocr_lang=config.ocr_lang,
                image_format=config.image_format,
                image_dpi=config.image_dpi,
            )

        # Start live progress
        if isinstance(progress, RichProgress):
            progress.start_live()

        try:
            # Process each PDF
            for idx, pdf in enumerate(discovered, start=1):
                progress.update_pdf(pdf.path.name, idx, len(discovered))

                # Check if already complete (resume mode)
                if config.resume and state.is_pdf_complete(pdf.relative_name):
                    logger.info("Skipping already completed: %s", pdf.path.name)
                    progress.complete_pdf(pdf.path.name, True)

                    # Collect result from state
                    pdf_state = state.get_pdf_state(pdf.relative_name)
                    page_states = state.get_page_states(pdf.relative_name)
                    pdf_results.append(_build_pdf_result(
                        pdf, pdf_state, page_states, config,
                    ))
                    continue

                result = _process_single_pdf(
                    pdf, config, state, tesseract_cmd, progress,
                )
                pdf_results.append(result)

                success = result["status"] in ("completed", "completed_with_warnings")
                progress.complete_pdf(pdf.path.name, success)

        finally:
            if isinstance(progress, RichProgress):
                progress.stop_live()

        # Build combined Markdown
        _build_combined_markdown(config, discovered, pdf_results)

    # Generate report
    finished_at = datetime.now(timezone.utc)

    report = generate_report(
        config.report_path,
        config.source_dir,
        config.resolved_output_dir,
        config.ocr_lang,
        config.image_format,
        config.image_dpi,
        started_at,
        finished_at,
        pdf_results,
        [{"path": str(s.path), "reason": s.reason} for s in skipped],
    )

    # Print summary
    summary = report["summary"]
    progress.print_summary(
        completed=summary["pdfs_completed"],
        failed=summary["pdfs_failed"],
        total=summary["pdfs_discovered"],
        pages_completed=summary["pages_completed"],
        pages_failed=summary["pages_failed"],
    )

    # Print report location
    print(f"📄 Report: {config.report_path}")
    print(f"📁 Output: {config.resolved_output_dir}")
    print(f"📝 Log: {config.log_path}")

    # Determine exit code
    if summary["pdfs_failed"] > 0 or summary["pages_failed"] > 0:
        return 1
    return 0


def _process_single_pdf(
    pdf: DiscoveredPDF,
    config: ProcessingConfig,
    state: StateManager,
    tesseract_cmd: str,
    progress,
) -> dict:
    """Process a single PDF: render pages, run OCR, write Markdown.

    Returns:
        Result dict for the report.
    """
    pdf_start = time.time()
    logger.info("Processing: %s (%d pages)", pdf.path.name, pdf.page_count)

    state.mark_pdf_started(pdf.relative_name)

    page_contents: dict[int, str] = {}
    page_image_paths: dict[int, Path] = {}
    pages_completed = 0
    pages_failed = 0
    images_created = 0
    ocr_failures = 0
    native_failures = 0
    page_errors: list[dict] = []

    try:
        with PDFDocument(pdf.path) as doc:
            incomplete_pages = state.get_incomplete_pages(pdf.relative_name)

            for page_num_1based in range(1, pdf.page_count + 1):
                page_num_0based = page_num_1based - 1

                progress.update_page(page_num_1based, pdf.page_count, pdf.path.name)

                # Check if this page is already complete (resume)
                if config.resume and page_num_1based not in incomplete_pages:
                    page_state = state.get_page_state(
                        pdf.relative_name, page_num_1based
                    )
                    if page_state and page_state["status"] == "completed":
                        pages_completed += 1
                        if page_state.get("image_saved"):
                            img_path = get_image_path(
                                config.images_dir,
                                pdf.relative_name,
                                page_num_1based,
                                pdf.page_count,
                                config.image_format,
                            )
                            if verify_image(img_path):
                                page_image_paths[page_num_1based] = img_path
                                images_created += 1
                        # We need to reconstruct page content for Markdown
                        # Read it from existing Markdown later, or reprocess
                        if isinstance(progress, RichProgress):
                            progress.increment_page_result(True)
                        continue

                # ---- Process this page ----
                page_ok = True
                native_text = ""
                ocr_text = ""
                page_img = None

                # 1. Render page image
                try:
                    fitz_page = doc.get_page(page_num_0based)
                    page_img = render_page_to_pil(fitz_page, dpi=config.image_dpi)
                except PageRenderError as e:
                    logger.error(
                        "Render failed: %s page %d: %s",
                        pdf.path.name, page_num_1based, e,
                    )
                    page_errors.append({
                        "page": page_num_1based,
                        "error": f"Render failed: {e}",
                    })
                    state.mark_page_failed(
                        pdf.relative_name, page_num_1based, str(e)
                    )
                    pages_failed += 1
                    if isinstance(progress, RichProgress):
                        progress.increment_page_result(False)
                    continue

                # 2. Save page image
                try:
                    img_path = get_image_path(
                        config.images_dir,
                        pdf.relative_name,
                        page_num_1based,
                        pdf.page_count,
                        config.image_format,
                    )
                    img_size = save_page_image(page_img, img_path, config.image_format)
                    page_image_paths[page_num_1based] = img_path
                    images_created += 1
                    state.mark_page_image_saved(
                        pdf.relative_name,
                        page_num_1based,
                        str(img_path),
                        img_size,
                    )
                except ImageWriteError as e:
                    logger.error(
                        "Image save failed: %s page %d: %s",
                        pdf.path.name, page_num_1based, e,
                    )
                    page_errors.append({
                        "page": page_num_1based,
                        "error": f"Image save failed: {e}",
                    })
                    # Continue — we can still extract text

                # 3. Extract native text
                native_extracted = False
                try:
                    native_text = doc.extract_page_text(page_num_0based)
                    native_extracted = bool(native_text.strip())
                except Exception as e:
                    logger.warning(
                        "Native text extraction failed: %s page %d: %s",
                        pdf.path.name, page_num_1based, e,
                    )
                    native_failures += 1

                # 4. Run OCR
                ocr_completed = False
                ocr_recovered = False
                try:
                    ocr_text = run_ocr(
                        page_img,
                        lang=config.ocr_lang,
                        tesseract_cmd=tesseract_cmd,
                        timeout=config.ocr_timeout,
                        psm=config.ocr_psm,
                        preprocess=config.preprocess,
                    )
                    ocr_completed = True
                    ocr_recovered = bool(ocr_text.strip())
                except OCRError as e:
                    logger.warning(
                        "OCR failed: %s page %d: %s",
                        pdf.path.name, page_num_1based, e,
                    )
                    ocr_failures += 1
                    page_errors.append({
                        "page": page_num_1based,
                        "error": f"OCR failed: {e}",
                    })

                # 5. Combine native + OCR text
                combined_text, text_source = combine_native_and_ocr(
                    native_text, ocr_text
                )

                # 6. Format for Markdown
                formatted_text = format_page_content(combined_text)
                page_contents[page_num_1based] = formatted_text

                # 7. Update state
                state.mark_page_text_extracted(
                    pdf.relative_name,
                    page_num_1based,
                    native_extracted=native_extracted,
                    ocr_completed=ocr_completed,
                    ocr_text_recovered=ocr_recovered,
                    text_source=text_source,
                )
                state.mark_page_complete(pdf.relative_name, page_num_1based)
                pages_completed += 1

                if isinstance(progress, RichProgress):
                    progress.increment_page_result(True)

                # Release the page image to free memory
                del page_img

        # Write Markdown for this PDF
        md_path = config.ocr_dir / f"{pdf.relative_name}.md"
        display_name = pdf.path.stem.replace("_", " ").replace("-", " ")

        # For resume, we need content for all pages, including previously completed ones
        # If some pages have no content in page_contents, try to fill from state
        if config.resume:
            for pn in range(1, pdf.page_count + 1):
                if pn not in page_contents:
                    # Page was completed in a previous run; we need to reprocess
                    # for its text content since we don't store raw text in state
                    page_contents.setdefault(pn, "")

        try:
            write_pdf_markdown(
                md_path,
                display_name,
                pdf.path.name,
                pdf.page_count,
                page_contents,
                page_image_paths,
            )
            markdown_written = True
        except MarkdownWriteError as e:
            logger.error("Failed to write Markdown for %s: %s", pdf.path.name, e)
            markdown_written = False

        state.mark_pdf_complete(pdf.relative_name)

        duration = time.time() - pdf_start
        logger.info(
            "Completed: %s in %.1fs (%d/%d pages OK)",
            pdf.path.name, duration, pages_completed, pdf.page_count,
        )

        status = "completed"
        if pages_failed > 0 or ocr_failures > 0:
            status = "completed_with_warnings"

        return {
            "source_path": str(pdf.path),
            "relative_name": pdf.relative_name,
            "markdown_path": str(md_path),
            "page_count": pdf.page_count,
            "pages_completed": pages_completed,
            "pages_failed": pages_failed,
            "images_created": images_created,
            "ocr_failures": ocr_failures,
            "native_text_failures": native_failures,
            "processing_duration_seconds": round(duration, 2),
            "status": status,
            "markdown_written": markdown_written,
            "errors": page_errors if page_errors else None,
        }

    except (PDFReadError, PDFNotesError) as e:
        duration = time.time() - pdf_start
        logger.error("Failed to process %s: %s", pdf.path.name, e)
        state.mark_pdf_failed(pdf.relative_name, str(e))

        return {
            "source_path": str(pdf.path),
            "relative_name": pdf.relative_name,
            "markdown_path": None,
            "page_count": pdf.page_count,
            "pages_completed": pages_completed,
            "pages_failed": pdf.page_count - pages_completed,
            "images_created": images_created,
            "ocr_failures": ocr_failures,
            "native_text_failures": native_failures,
            "processing_duration_seconds": round(duration, 2),
            "status": "failed",
            "markdown_written": False,
            "errors": [{"error": str(e)}],
        }
    except Exception as e:
        duration = time.time() - pdf_start
        logger.error(
            "Unexpected error processing %s: %s", pdf.path.name, e, exc_info=True
        )
        state.mark_pdf_failed(pdf.relative_name, str(e))

        return {
            "source_path": str(pdf.path),
            "relative_name": pdf.relative_name,
            "markdown_path": None,
            "page_count": pdf.page_count,
            "pages_completed": pages_completed,
            "pages_failed": pdf.page_count - pages_completed,
            "images_created": images_created,
            "ocr_failures": ocr_failures,
            "native_text_failures": native_failures,
            "processing_duration_seconds": round(duration, 2),
            "status": "failed",
            "markdown_written": False,
            "errors": [{"error": str(e)}],
        }


def _build_pdf_result(
    pdf: DiscoveredPDF,
    pdf_state: dict | None,
    page_states: list[dict],
    config: ProcessingConfig,
) -> dict:
    """Build a result dict from existing state (for resumed completed PDFs)."""
    pages_completed = sum(1 for p in page_states if p["status"] == "completed")
    pages_failed = sum(1 for p in page_states if p["status"] == "failed")
    images_created = sum(1 for p in page_states if p["image_saved"])

    md_path = config.ocr_dir / f"{pdf.relative_name}.md"

    return {
        "source_path": str(pdf.path),
        "relative_name": pdf.relative_name,
        "markdown_path": str(md_path),
        "page_count": pdf.page_count,
        "pages_completed": pages_completed,
        "pages_failed": pages_failed,
        "images_created": images_created,
        "ocr_failures": 0,
        "native_text_failures": 0,
        "processing_duration_seconds": 0,
        "status": pdf_state["status"] if pdf_state else "completed",
        "markdown_written": True,
        "errors": None,
    }


def _build_combined_markdown(
    config: ProcessingConfig,
    discovered: list[DiscoveredPDF],
    pdf_results: list[dict],
) -> None:
    """Build the combined semester Markdown file."""
    combined_path = config.ocr_dir / "semester_combined.md"

    entries = []
    for pdf, result in zip(discovered, pdf_results):
        display_name = pdf.path.stem.replace("_", " ").replace("-", " ")
        entries.append({
            "name": display_name,
            "source": pdf.path.name,
            "markdown_path": result.get("markdown_path", ""),
            "status": result["status"],
            "error": (
                result["errors"][0].get("error", "Unknown")
                if result.get("errors")
                else None
            ),
        })

    try:
        size = write_combined_markdown(
            combined_path,
            entries,
            warn_size_mb=config.combined_size_warn_mb,
        )
        logger.info("Combined Markdown: %s (%.1f MB)", combined_path, size / 1048576)
    except MarkdownWriteError as e:
        logger.error("Failed to write combined Markdown: %s", e)
