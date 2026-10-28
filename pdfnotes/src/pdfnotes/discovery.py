"""PDF discovery — find, validate, and sort PDF files in a source folder."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from pdfnotes.exceptions import (
    NoPDFsFoundError,
    PDFCorruptError,
    PDFPasswordError,
    PDFReadError,
    SourceFolderError,
)

logger = logging.getLogger("pdfnotes.discovery")


@dataclass
class DiscoveredPDF:
    """Represents a validated PDF ready for processing."""

    path: Path
    relative_name: str  # Used for output naming (stem, or with subfolder prefix)
    size_bytes: int
    sha256: str
    page_count: int

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class SkippedPDF:
    """A PDF that was found but cannot be processed."""

    path: Path
    reason: str


def validate_source_folder(source_dir: Path) -> None:
    """Raise SourceFolderError if the folder is invalid."""
    if not source_dir.exists():
        raise SourceFolderError(f"Source folder does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise SourceFolderError(f"Source path is not a directory: {source_dir}")
    if not _is_readable(source_dir):
        raise SourceFolderError(f"Source folder is not readable: {source_dir}")


def _is_readable(path: Path) -> bool:
    """Check if a path is readable."""
    try:
        if path.is_dir():
            list(path.iterdir())
        else:
            path.open("rb").close()
        return True
    except (PermissionError, OSError):
        return False


def _file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _get_page_count(path: Path) -> int:
    """Open a PDF and return its page count. Raises on errors."""
    import pymupdf as fitz  # PyMuPDF

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise PDFCorruptError(f"Cannot open PDF: {path} — {e}") from e

    try:
        if doc.is_encrypted:
            if not doc.authenticate(""):
                raise PDFPasswordError(f"PDF is password-protected: {path}")

        count = doc.page_count
        if count == 0:
            raise PDFReadError(f"PDF has zero pages: {path}")
        return count
    finally:
        doc.close()


def discover_pdfs(
    source_dir: Path,
    recursive: bool = False,
    output_dir: Path | None = None,
) -> tuple[list[DiscoveredPDF], list[SkippedPDF]]:
    """Find and validate all PDFs in the source folder.

    Args:
        source_dir: Root folder to scan.
        recursive: Whether to scan subfolders.
        output_dir: The output directory to exclude from scanning.

    Returns:
        Tuple of (valid PDFs sorted deterministically, skipped PDFs).
    """
    validate_source_folder(source_dir)

    resolved_output = output_dir if output_dir else source_dir / "Result"
    resolved_output = resolved_output.resolve()

    discovered: list[DiscoveredPDF] = []
    skipped: list[SkippedPDF] = []

    # Collect candidate files
    if recursive:
        candidates = sorted(source_dir.rglob("*"))
    else:
        candidates = sorted(source_dir.iterdir())

    # Track relative names for collision detection
    seen_names: dict[str, Path] = {}

    for candidate in candidates:
        # Skip the output directory entirely
        try:
            if candidate.resolve().is_relative_to(resolved_output):
                continue
        except (ValueError, OSError):
            pass

        if not candidate.is_file():
            continue

        if candidate.suffix.lower() != ".pdf":
            continue

        # Build the relative name for output naming
        if recursive:
            try:
                rel = candidate.relative_to(source_dir)
                # Use parent dirs + stem to avoid collisions
                parts = list(rel.parent.parts) + [candidate.stem]
                relative_name = "_".join(parts) if len(parts) > 1 else candidate.stem
            except ValueError:
                relative_name = candidate.stem
        else:
            relative_name = candidate.stem

        # Handle duplicate names
        if relative_name in seen_names:
            counter = 2
            base = relative_name
            while relative_name in seen_names:
                relative_name = f"{base}_{counter}"
                counter += 1

        # Validate the PDF
        try:
            if not _is_readable(candidate):
                skipped.append(SkippedPDF(candidate, "File is not readable"))
                continue

            size = candidate.stat().st_size
            if size == 0:
                skipped.append(SkippedPDF(candidate, "File is empty (0 bytes)"))
                continue

            sha256 = _file_sha256(candidate)
            page_count = _get_page_count(candidate)

            pdf = DiscoveredPDF(
                path=candidate,
                relative_name=relative_name,
                size_bytes=size,
                sha256=sha256,
                page_count=page_count,
            )
            discovered.append(pdf)
            seen_names[relative_name] = candidate
            logger.info("Discovered: %s (%d pages)", candidate.name, page_count)

        except PDFPasswordError as e:
            skipped.append(SkippedPDF(candidate, str(e)))
            logger.warning("Skipped password-protected: %s", candidate.name)
        except (PDFCorruptError, PDFReadError) as e:
            skipped.append(SkippedPDF(candidate, str(e)))
            logger.warning("Skipped unreadable PDF: %s — %s", candidate.name, e)
        except OSError as e:
            skipped.append(SkippedPDF(candidate, f"OS error: {e}"))
            logger.warning("Skipped due to OS error: %s — %s", candidate.name, e)

    # Sort deterministically by relative_name
    discovered.sort(key=lambda p: p.relative_name.lower())

    if not discovered and not skipped:
        raise NoPDFsFoundError(f"No PDF files found in: {source_dir}")

    logger.info(
        "Discovery complete: %d valid PDFs, %d skipped",
        len(discovered),
        len(skipped),
    )

    return discovered, skipped
