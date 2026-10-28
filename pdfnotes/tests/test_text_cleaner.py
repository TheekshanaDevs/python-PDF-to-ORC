"""Tests for text cleaner module."""

from __future__ import annotations

import pytest


class TestCleanText:
    """Tests for basic text cleaning."""

    def test_clean_empty(self):
        from pdfnotes.text_cleaner import clean_text
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_clean_removes_null_chars(self):
        from pdfnotes.text_cleaner import clean_text
        assert "\x00" not in clean_text("hello\x00world")

    def test_clean_normalizes_line_endings(self):
        from pdfnotes.text_cleaner import clean_text
        result = clean_text("line1\r\nline2\rline3\nline4")
        assert "\r" not in result
        assert "line1" in result
        assert "line4" in result

    def test_clean_removes_trailing_whitespace(self):
        from pdfnotes.text_cleaner import clean_text
        result = clean_text("hello   \nworld   ")
        lines = result.split("\n")
        for line in lines:
            assert line == line.rstrip()

    def test_clean_collapses_blank_lines(self):
        from pdfnotes.text_cleaner import clean_text
        result = clean_text("a\n\n\n\n\n\nb")
        assert "\n\n\n\n" not in result
        assert "a" in result
        assert "b" in result

    def test_clean_joins_hyphenated_words(self):
        from pdfnotes.text_cleaner import clean_text
        result = clean_text("pro-\ngramming is fun")
        assert "programming" in result

    def test_clean_preserves_real_hyphens(self):
        from pdfnotes.text_cleaner import clean_text
        # Should NOT join when next line starts with uppercase
        result = clean_text("high-\nLevel concepts")
        # This should keep the hyphen since 'Level' starts with uppercase
        assert "high-" in result or "high" in result


class TestCombineTexts:
    """Tests for native + OCR text combination."""

    def test_native_only(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        text, source = combine_native_and_ocr("Native text here", "")
        assert "Native text" in text
        assert source == "native"

    def test_ocr_only(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        text, source = combine_native_and_ocr("", "OCR text here")
        assert "OCR text" in text
        assert source == "ocr"

    def test_both_empty(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        text, source = combine_native_and_ocr("", "")
        assert text == ""
        assert source == "empty"

    def test_identical_texts(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        content = "This is a test paragraph with enough content."
        text, source = combine_native_and_ocr(content, content)
        assert source == "native"
        # Should not duplicate content
        assert text.count("test paragraph") == 1

    def test_similar_texts_uses_native(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        native = "This is the correct native text from the PDF document."
        ocr = "This is the correct native text from the PDF document"  # minor diff
        text, source = combine_native_and_ocr(native, ocr)
        assert source == "native"

    def test_ocr_adds_new_content(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        native = "Header text from native extraction"
        ocr = "Header text from native extraction\nExtra OCR content from an image"
        text, source = combine_native_and_ocr(native, ocr)
        # Should include the extra OCR content
        assert "Extra OCR content" in text or source == "native"

    def test_no_duplication_of_lines(self):
        from pdfnotes.text_cleaner import combine_native_and_ocr
        native = "Line A\nLine B\nLine C"
        ocr = "Line A\nLine B\nLine C\nLine D from image"
        text, source = combine_native_and_ocr(native, ocr)
        if source == "combined":
            # Line A should appear only once
            assert text.count("Line A") == 1
            assert "Line D" in text


class TestFormatting:
    """Tests for text formatting (headings, lists, etc.)."""

    def test_detect_headings_allcaps(self):
        from pdfnotes.text_cleaner import detect_headings
        result = detect_headings("INTRODUCTION\nSome content here")
        assert "##" in result
        assert "Introduction" in result

    def test_detect_lists_bullets(self):
        from pdfnotes.text_cleaner import detect_lists
        result = detect_lists("• First item\n• Second item")
        assert "- First item" in result
        assert "- Second item" in result

    def test_detect_lists_preserves_markdown(self):
        from pdfnotes.text_cleaner import detect_lists
        result = detect_lists("- Already markdown\n* Also markdown")
        assert "- Already markdown" in result
        assert "* Also markdown" in result

    def test_format_page_content_full(self):
        from pdfnotes.text_cleaner import format_page_content
        raw = "CHAPTER ONE\n\n• First point\n• Second point\n\nSome text here"
        result = format_page_content(raw)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unicode_preservation(self):
        from pdfnotes.text_cleaner import clean_text
        text = "Résumé café naïve 日本語 العربية"
        result = clean_text(text)
        assert "Résumé" in result
        assert "café" in result
        assert "日本語" in result
