"""Tests for PDF discovery module."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import create_text_pdf


class TestDiscovery:
    """Tests for the discovery module."""

    def test_discover_pdfs_in_folder(self, source_dir):
        """Should find all PDFs in a flat folder."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "lecture1.pdf", ["Page 1 content"])
        create_text_pdf(source_dir / "lecture2.pdf", ["Page 1", "Page 2"])

        discovered, skipped = discover_pdfs(source_dir)

        assert len(discovered) == 2
        assert len(skipped) == 0
        names = [p.relative_name for p in discovered]
        assert "lecture1" in names
        assert "lecture2" in names

    def test_discover_no_pdfs(self, source_dir):
        """Should raise NoPDFsFoundError for a folder with no PDFs."""
        from pdfnotes.exceptions import NoPDFsFoundError
        from pdfnotes.discovery import discover_pdfs

        # Create a non-PDF file
        (source_dir / "notes.txt").write_text("hello")

        with pytest.raises(NoPDFsFoundError):
            discover_pdfs(source_dir)

    def test_discover_missing_folder(self, tmp_dir):
        """Should raise SourceFolderError for a nonexistent folder."""
        from pdfnotes.exceptions import SourceFolderError
        from pdfnotes.discovery import discover_pdfs

        with pytest.raises(SourceFolderError):
            discover_pdfs(tmp_dir / "nonexistent")

    def test_discover_uppercase_extension(self, source_dir):
        """Should find .PDF files (case-insensitive)."""
        from pdfnotes.discovery import discover_pdfs

        pdf_path = create_text_pdf(source_dir / "LECTURE.pdf", ["Content"])
        # Rename to .PDF
        new_path = source_dir / "LECTURE.PDF"
        pdf_path.rename(new_path)

        discovered, _ = discover_pdfs(source_dir)
        assert len(discovered) == 1

    def test_discover_recursive(self, source_dir):
        """Should find PDFs in subfolders when recursive=True."""
        from pdfnotes.discovery import discover_pdfs

        sub1 = source_dir / "week1"
        sub1.mkdir()
        sub2 = source_dir / "week2"
        sub2.mkdir()

        create_text_pdf(source_dir / "intro.pdf", ["Intro"])
        create_text_pdf(sub1 / "lecture1.pdf", ["Week 1"])
        create_text_pdf(sub2 / "lecture2.pdf", ["Week 2"])

        discovered, _ = discover_pdfs(source_dir, recursive=True)
        assert len(discovered) == 3

    def test_discover_non_recursive_ignores_subfolders(self, source_dir):
        """Should NOT find PDFs in subfolders when recursive=False."""
        from pdfnotes.discovery import discover_pdfs

        sub = source_dir / "sub"
        sub.mkdir()

        create_text_pdf(source_dir / "top.pdf", ["Top"])
        create_text_pdf(sub / "nested.pdf", ["Nested"])

        discovered, _ = discover_pdfs(source_dir, recursive=False)
        assert len(discovered) == 1
        assert discovered[0].relative_name == "top"

    def test_discover_excludes_output_dir(self, source_dir):
        """Should exclude the Result directory from scanning."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "lecture.pdf", ["Content"])
        result_dir = source_dir / "Result" / "OCR"
        result_dir.mkdir(parents=True)
        create_text_pdf(result_dir / "output.pdf", ["Should be excluded"])

        discovered, _ = discover_pdfs(
            source_dir, recursive=True, output_dir=source_dir / "Result"
        )
        assert len(discovered) == 1
        assert discovered[0].relative_name == "lecture"

    def test_discover_duplicate_names_recursive(self, source_dir):
        """Should handle duplicate filenames in different subfolders."""
        from pdfnotes.discovery import discover_pdfs

        sub1 = source_dir / "folder1"
        sub1.mkdir()
        sub2 = source_dir / "folder2"
        sub2.mkdir()

        create_text_pdf(sub1 / "notes.pdf", ["Folder 1 notes"])
        create_text_pdf(sub2 / "notes.pdf", ["Folder 2 notes"])

        discovered, _ = discover_pdfs(source_dir, recursive=True)
        assert len(discovered) == 2
        names = [p.relative_name for p in discovered]
        # Names should be unique
        assert len(set(names)) == 2

    def test_discover_deterministic_order(self, source_dir):
        """PDFs should be sorted deterministically."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "z_lecture.pdf", ["Z"])
        create_text_pdf(source_dir / "a_lecture.pdf", ["A"])
        create_text_pdf(source_dir / "m_lecture.pdf", ["M"])

        discovered, _ = discover_pdfs(source_dir)
        names = [p.relative_name for p in discovered]
        assert names == sorted(names, key=str.lower)

    def test_discover_ignores_non_pdf_files(self, source_dir):
        """Should ignore non-PDF files."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "lecture.pdf", ["Content"])
        (source_dir / "readme.txt").write_text("Not a PDF")
        (source_dir / "image.png").write_bytes(b"\x89PNG")
        (source_dir / "data.csv").write_text("a,b,c")

        discovered, _ = discover_pdfs(source_dir)
        assert len(discovered) == 1

    def test_discover_sha256_computed(self, source_dir):
        """Each discovered PDF should have a SHA-256 hash."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "lecture.pdf", ["Content"])

        discovered, _ = discover_pdfs(source_dir)
        assert len(discovered[0].sha256) == 64  # SHA-256 hex is 64 chars

    def test_discover_page_count(self, source_dir):
        """Should report correct page count."""
        from pdfnotes.discovery import discover_pdfs

        create_text_pdf(source_dir / "multi.pdf", ["P1", "P2", "P3"])

        discovered, _ = discover_pdfs(source_dir)
        assert discovered[0].page_count == 3
