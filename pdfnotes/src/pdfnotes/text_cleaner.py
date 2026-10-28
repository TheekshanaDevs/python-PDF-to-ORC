"""Text cleaner — clean extracted text and combine native + OCR results."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger("pdfnotes.text_cleaner")


def clean_text(text: str) -> str:
    """Clean extracted text without changing its meaning.

    Fixes common extraction artifacts:
    - Excessive blank lines
    - Trailing whitespace
    - Broken words from line wrapping (conservative)
    - Null characters

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    # Remove null characters
    text = text.replace("\x00", "")

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]

    # Join hyphenated line breaks (conservative: only lowercase-lowercase)
    joined_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            i + 1 < len(lines)
            and line.endswith("-")
            and len(line) > 1
            and lines[i + 1]
            and lines[i + 1][0].islower()
        ):
            # Join the hyphenated word
            joined_lines.append(line[:-1] + lines[i + 1])
            i += 2
        else:
            joined_lines.append(line)
            i += 1

    text = "\n".join(joined_lines)

    # Collapse runs of 3+ blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def _normalize_for_comparison(text: str) -> str:
    """Normalize text for similarity comparison.

    Lowercases, removes excess whitespace, and strips punctuation
    for fuzzy matching purposes.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def _split_into_lines(text: str) -> list[str]:
    """Split text into non-empty lines for comparison."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def _line_similarity(line_a: str, line_b: str) -> float:
    """Return similarity ratio between two lines (0.0 to 1.0)."""
    norm_a = _normalize_for_comparison(line_a)
    norm_b = _normalize_for_comparison(line_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def combine_native_and_ocr(
    native_text: str,
    ocr_text: str,
    similarity_threshold: float = 0.75,
) -> tuple[str, str]:
    """Combine native PDF text and OCR text, avoiding obvious duplication.

    Strategy:
    1. If native text is empty, use OCR text entirely.
    2. If OCR text is empty, use native text entirely.
    3. If both exist, use native text as base and append OCR-only lines.
    4. Compare line-by-line; lines found only in OCR are appended as
       additional OCR-recovered content.

    Args:
        native_text: Text extracted from PDF metadata/text layer.
        ocr_text: Text from Tesseract OCR on the rendered page.
        similarity_threshold: Lines with similarity above this are considered
            duplicates and won't be added from OCR.

    Returns:
        Tuple of (combined_text, source_label) where source_label is one of
        "native", "ocr", "combined", or "empty".
    """
    native_clean = clean_text(native_text)
    ocr_clean = clean_text(ocr_text)

    if not native_clean and not ocr_clean:
        return "", "empty"

    if not native_clean:
        return ocr_clean, "ocr"

    if not ocr_clean:
        return native_clean, "native"

    # Both have content — compare and merge
    native_lines = _split_into_lines(native_clean)
    ocr_lines = _split_into_lines(ocr_clean)

    if not native_lines:
        return ocr_clean, "ocr"
    if not ocr_lines:
        return native_clean, "native"

    # Check overall similarity first
    overall_sim = SequenceMatcher(
        None,
        _normalize_for_comparison(native_clean),
        _normalize_for_comparison(ocr_clean),
    ).ratio()

    if overall_sim > 0.90:
        # Texts are very similar — native is likely better quality
        logger.debug("Native and OCR texts are >90%% similar; using native text")
        return native_clean, "native"

    # Find OCR-only lines not in native text
    ocr_only_lines = []
    for ocr_line in ocr_lines:
        if len(ocr_line.strip()) < 3:
            # Skip very short lines (likely noise)
            continue

        is_duplicate = False
        for native_line in native_lines:
            sim = _line_similarity(ocr_line, native_line)
            if sim >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            ocr_only_lines.append(ocr_line)

    if not ocr_only_lines:
        return native_clean, "native"

    # Append OCR-only content
    combined = native_clean + "\n\n---\n*[Additional text recovered by OCR]*\n\n"
    combined += "\n".join(ocr_only_lines)

    logger.debug(
        "Combined native (%d lines) + OCR-only (%d lines)",
        len(native_lines),
        len(ocr_only_lines),
    )

    return combined, "combined"


def detect_headings(text: str) -> str:
    """Attempt to detect and format headings in extracted text.

    Uses heuristics:
    - Short lines in ALL CAPS → ## heading
    - Lines ending with colon that are short → ### heading
    - Numbered section patterns like "1. Title" or "Chapter 1"

    Args:
        text: Cleaned extracted text.

    Returns:
        Text with detected headings formatted as Markdown.
    """
    if not text:
        return ""

    lines = text.split("\n")
    result = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            result.append(line)
            continue

        # Don't re-format existing Markdown headings
        if stripped.startswith("#"):
            result.append(line)
            continue

        # ALL CAPS short lines (likely section headers)
        if (
            stripped.isupper()
            and len(stripped) > 3
            and len(stripped) < 80
            and not stripped.startswith(("•", "-", "*", "–"))
            and not any(c.isdigit() and c == stripped[0] for c in [stripped[0]])
        ):
            result.append(f"## {stripped.title()}")
            continue

        # Chapter/Section numbered headers
        chapter_match = re.match(
            r"^(Chapter|Section|Part|Module|Unit|Lecture)\s+(\d+)\s*[:\-–]?\s*(.*)",
            stripped,
            re.IGNORECASE,
        )
        if chapter_match and len(stripped) < 100:
            result.append(f"## {stripped}")
            continue

        # Numbered sections like "1.1 Title" or "1. Title"
        section_match = re.match(r"^(\d+(?:\.\d+)*)\s+([A-Z].*)", stripped)
        if section_match and len(stripped) < 100:
            depth = section_match.group(1).count(".") + 2
            prefix = "#" * min(depth + 1, 4)
            result.append(f"{prefix} {stripped}")
            continue

        result.append(line)

    return "\n".join(result)


def detect_code_blocks(text: str) -> str:
    """Detect and format code blocks in extracted text.

    Looks for indented blocks that resemble programming code.
    """
    if not text:
        return ""

    lines = text.split("\n")
    result = []
    in_code_block = False
    code_lines: list[str] = []

    # Simple heuristics for code detection
    code_indicators = [
        r"^\s{4,}",  # 4+ spaces indent
        r"^\t",  # tab indent
    ]
    code_keywords = {
        "def ", "class ", "import ", "from ", "return ",
        "if ", "else:", "elif ", "for ", "while ",
        "try:", "except", "finally:", "with ",
        "print(", "int(", "str(", "len(",
        "public ", "private ", "void ", "static ",
        "function ", "var ", "let ", "const ",
        "SELECT ", "INSERT ", "UPDATE ", "CREATE ",
        "#include", "using namespace",
    }

    for line in lines:
        stripped = line.strip()

        # Already in a code block
        if stripped.startswith("```"):
            result.append(line)
            in_code_block = not in_code_block
            continue

        if in_code_block:
            result.append(line)
            continue

        result.append(line)

    return "\n".join(result)


def detect_lists(text: str) -> str:
    """Ensure bullet/numbered list items are properly formatted for Markdown."""
    if not text:
        return ""

    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip()

        # Convert common bullet characters to Markdown bullets
        if stripped and stripped[0] in ("•", "►", "▪", "▸", "○", "●", "◦", "■"):
            result.append(f"- {stripped[1:].strip()}")
            continue

        # Preserve existing Markdown list items
        if re.match(r"^[-*+]\s", stripped) or re.match(r"^\d+[.)]\s", stripped):
            result.append(line)
            continue

        result.append(line)

    return "\n".join(result)


def format_page_content(text: str) -> str:
    """Apply all text formatting passes to page content.

    Args:
        text: Raw or cleaned extracted text.

    Returns:
        Markdown-formatted text.
    """
    text = clean_text(text)
    text = detect_headings(text)
    text = detect_lists(text)
    text = detect_code_blocks(text)
    return text
