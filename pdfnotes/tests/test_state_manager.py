"""Tests for state manager module."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestStateManager:
    """Tests for SQLite-based state management."""

    def test_create_database(self, tmp_dir):
        """Should create the state database."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            assert db_path.exists()

    def test_init_pdf(self, tmp_dir):
        """Should initialize PDF state."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="lecture1",
                source_path="/path/to/lecture1.pdf",
                file_size=1024,
                file_mtime=1000.0,
                sha256="abc123" * 10 + "abcd",
                page_count=5,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            pdf_state = state.get_pdf_state("lecture1")
            assert pdf_state is not None
            assert pdf_state["page_count"] == 5
            assert pdf_state["status"] == "pending"

    def test_page_states_initialized(self, tmp_dir):
        """Should create page state entries for all pages."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=3,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            pages = state.get_page_states("test")
            assert len(pages) == 3
            assert all(p["status"] == "pending" for p in pages)

    def test_mark_page_complete(self, tmp_dir):
        """Should mark a page as completed."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=2,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            state.mark_page_complete("test", 1)
            assert state.is_page_complete("test", 1)
            assert not state.is_page_complete("test", 2)

    def test_mark_pdf_complete(self, tmp_dir):
        """Should mark a PDF as completed."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=1,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            state.mark_page_complete("test", 1)
            state.mark_pdf_complete("test")
            assert state.is_pdf_complete("test")

    def test_incomplete_pages(self, tmp_dir):
        """Should return incomplete page numbers."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=5,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            state.mark_page_complete("test", 1)
            state.mark_page_complete("test", 3)

            incomplete = state.get_incomplete_pages("test")
            assert 2 in incomplete
            assert 4 in incomplete
            assert 5 in incomplete
            assert 1 not in incomplete

    def test_pdf_changed_resets_state(self, tmp_dir):
        """Should reset state when PDF hash changes."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=2,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )
            state.mark_page_complete("test", 1)
            state.mark_pdf_complete("test")

            # Re-init with different hash (file changed)
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=200,
                file_mtime=2000.0,
                sha256="b" * 64,
                page_count=2,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )

            assert not state.is_pdf_complete("test")
            assert len(state.get_incomplete_pages("test")) == 2

    def test_settings_changed_resets_state(self, tmp_dir):
        """Should reset when OCR settings change."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=1,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )
            state.mark_page_complete("test", 1)
            state.mark_pdf_complete("test")

            # Re-init with different language
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=1,
                ocr_lang="eng+sin",  # Changed!
                image_format="png",
                image_dpi=200,
            )

            assert not state.is_pdf_complete("test")

    def test_statistics(self, tmp_dir):
        """Should return correct processing statistics."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=3,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )
            state.mark_page_complete("test", 1)
            state.mark_page_complete("test", 2)
            state.mark_page_failed("test", 3, "OCR error")

            stats = state.get_statistics()
            assert stats["total_pdfs"] == 1
            assert stats["completed_pages"] == 2
            assert stats["failed_pages"] == 1

    def test_mark_page_failed(self, tmp_dir):
        """Should record page failure with error message."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=1,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )
            state.mark_page_failed("test", 1, "Render error")

            page = state.get_page_state("test", 1)
            assert page["status"] == "failed"
            assert "Render error" in page["error_message"]

    def test_persistence_across_sessions(self, tmp_dir):
        """State should persist across database open/close cycles."""
        from pdfnotes.state_manager import StateManager

        db_path = tmp_dir / "state.db"

        # Session 1: initialize and mark progress
        with StateManager(db_path) as state:
            state.init_pdf(
                relative_name="test",
                source_path="/test.pdf",
                file_size=100,
                file_mtime=1000.0,
                sha256="a" * 64,
                page_count=2,
                ocr_lang="eng",
                image_format="png",
                image_dpi=200,
            )
            state.mark_page_complete("test", 1)

        # Session 2: verify state
        with StateManager(db_path) as state:
            assert state.is_page_complete("test", 1)
            assert not state.is_page_complete("test", 2)
