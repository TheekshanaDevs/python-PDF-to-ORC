"""Markdown writer — generate per-PDF and combined semester Markdown files."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from pdfnotes.exceptions import MarkdownWriteError

logger = logging.getLogger("pdfnotes.markdown_writer")


def _safe_anchor(text: str) -> str:
    """Generate a GitHub-compatible anchor from a heading string."""
    anchor = text.lower().strip()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    return anchor


def _relative_image_link(md_path: Path, image_path: Path) -> str:
    """Compute the relative path from the Markdown file to the image.

    Args:
        md_path: Path to the Markdown file.
        image_path: Path to the page image.

    Returns:
        Relative path string suitable for a Markdown link.
    """
    try:
        # Get relative path from the MD file's directory to the image
        md_dir = md_path.parent
        rel = os.path.relpath(image_path, md_dir)
        # Use forward slashes for cross-platform Markdown compatibility
        return rel.replace("\\", "/")
    except ValueError:
        # On Windows, paths on different drives can't be made relative
        return str(image_path).replace("\\", "/")


def write_pdf_markdown(
    output_path: Path,
    pdf_name: str,
    source_filename: str,
    page_count: int,
    page_contents: dict[int, str],
    page_image_paths: dict[int, Path],
    images_relative_to: Path | None = None,
) -> int:
    """Write a Markdown file for a single PDF.

    Args:
        output_path: Path to the output .md file.
        pdf_name: Display name for the document heading.
        source_filename: Original PDF filename.
        page_count: Total number of pages.
        page_contents: Dict mapping 1-based page numbers to extracted text.
        page_image_paths: Dict mapping 1-based page numbers to image paths.
        images_relative_to: If provided, compute image links relative to this.

    Returns:
        File size in bytes.

    Raises:
        MarkdownWriteError: If writing fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            # Document header
            f.write(f"# {pdf_name}\n\n")
            f.write(f"**Source:** {source_filename}\n")
            f.write(f"**Pages:** {page_count}\n\n")
            f.write("---\n\n")

            # Page content
            for page_num in range(1, page_count + 1):
                f.write(f"## Page {page_num}\n\n")

                # Image link
                if page_num in page_image_paths:
                    img_path = page_image_paths[page_num]
                    rel_link = _relative_image_link(output_path, img_path)
                    f.write(
                        f"[View original page image]({rel_link})\n\n"
                    )

                # Page text
                content = page_contents.get(page_num, "")
                if content.strip():
                    f.write(content.strip())
                    f.write("\n\n")
                else:
                    f.write("*[No text content extracted from this page]*\n\n")

                # Page separator (except for the last page)
                if page_num < page_count:
                    f.write("---\n\n")

        # Atomic rename
        tmp_path.replace(output_path)
        size = output_path.stat().st_size
        logger.info("Wrote Markdown: %s (%d bytes)", output_path.name, size)
        return size

    except OSError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise MarkdownWriteError(f"Failed to write Markdown: {output_path} — {e}") from e


def write_combined_markdown(
    output_path: Path,
    pdf_entries: list[dict],
    warn_size_mb: float = 100.0,
) -> int:
    """Write the combined semester Markdown file by streaming from individual files.

    Args:
        output_path: Path to semester_combined.md.
        pdf_entries: List of dicts with keys:
            - 'name': Display name
            - 'source': Source filename
            - 'markdown_path': Path to individual Markdown file
            - 'status': Processing status
        warn_size_mb: Warn if the file exceeds this size in MB.

    Returns:
        File size in bytes.

    Raises:
        MarkdownWriteError: If writing fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    successful_entries = [e for e in pdf_entries if e.get("status") != "failed"]
    failed_entries = [e for e in pdf_entries if e.get("status") == "failed"]

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("# Semester Lecture Notes\n\n")

            # Table of contents
            f.write("## Table of Contents\n\n")

            # Track anchors for uniqueness
            seen_anchors: dict[str, int] = {}
            anchors: dict[str, str] = {}

            for entry in successful_entries:
                name = entry["name"]
                anchor = _safe_anchor(name)
                if anchor in seen_anchors:
                    seen_anchors[anchor] += 1
                    anchor = f"{anchor}-{seen_anchors[anchor]}"
                else:
                    seen_anchors[anchor] = 1
                anchors[name] = anchor
                f.write(f"- [{name}](#{anchor})\n")

            if failed_entries:
                f.write("\n### Failed PDFs\n\n")
                for entry in failed_entries:
                    f.write(f"- ~~{entry['name']}~~ — *{entry.get('error', 'Processing failed')}*\n")

            f.write("\n---\n\n")

            # Content from each PDF's Markdown file
            for entry in successful_entries:
                md_path = Path(entry["markdown_path"])
                name = entry["name"]

                if not md_path.exists():
                    logger.warning("Markdown file missing for combined: %s", md_path)
                    f.write(f"# {name}\n\n")
                    f.write(f"**Source:** {entry['source']}\n\n")
                    f.write("*[Markdown file not found]*\n\n---\n\n")
                    continue

                # Stream the individual file content (skip its top-level heading
                # since we'll write our own)
                with open(md_path, "r", encoding="utf-8") as md_f:
                    content = md_f.read()

                f.write(content)
                f.write("\n\n---\n\n")

        # Atomic rename
        tmp_path.replace(output_path)
        size = output_path.stat().st_size
        size_mb = size / (1024 * 1024)

        logger.info("Wrote combined Markdown: %s (%.1f MB)", output_path.name, size_mb)

        if size_mb > warn_size_mb:
            logger.warning(
                "Combined Markdown is %.1f MB (exceeds %.1f MB warning threshold). "
                "Some AI tools may have upload or context limits.",
                size_mb,
                warn_size_mb,
            )

        return size

    except OSError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise MarkdownWriteError(
            f"Failed to write combined Markdown: {output_path} — {e}"
        ) from e
