"""State manager — SQLite-based resume and progress tracking."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pdfnotes.exceptions import StateError

logger = logging.getLogger("pdfnotes.state_manager")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pdf_state (
    relative_name TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    ocr_lang TEXT NOT NULL,
    image_format TEXT NOT NULL,
    image_dpi INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    markdown_written INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_state (
    relative_name TEXT NOT NULL,
    page_num INTEGER NOT NULL,
    image_saved INTEGER NOT NULL DEFAULT 0,
    image_path TEXT,
    image_size INTEGER,
    native_text_extracted INTEGER NOT NULL DEFAULT 0,
    ocr_completed INTEGER NOT NULL DEFAULT 0,
    ocr_text_recovered INTEGER NOT NULL DEFAULT 0,
    text_source TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (relative_name, page_num),
    FOREIGN KEY (relative_name) REFERENCES pdf_state(relative_name)
);

CREATE TABLE IF NOT EXISTS run_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class StateManager:
    """Manages processing state using SQLite for reliable resume support.

    Usage::

        with StateManager(db_path) as state:
            state.init_pdf(...)
            state.mark_page_complete(...)
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "StateManager":
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), timeout=30)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except sqlite3.Error as e:
            raise StateError(f"Cannot open state database: {self.db_path} — {e}") from e
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            try:
                self._conn.commit()
            except sqlite3.Error:
                pass
            self._conn.close()
            self._conn = None
        return False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StateError("State database is not open")
        return self._conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def init_pdf(
        self,
        relative_name: str,
        source_path: str,
        file_size: int,
        file_mtime: float,
        sha256: str,
        page_count: int,
        ocr_lang: str,
        image_format: str,
        image_dpi: int,
    ) -> None:
        """Initialize or update the state entry for a PDF.

        If the PDF already exists in state and the file hasn't changed
        and settings match, this is a no-op.
        """
        now = self._now()
        existing = self.get_pdf_state(relative_name)

        if existing:
            # Check if the source file or settings have changed
            if (
                existing["sha256"] == sha256
                and existing["ocr_lang"] == ocr_lang
                and existing["image_format"] == image_format
                and existing["image_dpi"] == image_dpi
            ):
                logger.debug("PDF state unchanged: %s", relative_name)
                return

            # File or settings changed — reset
            logger.info("PDF changed or settings differ; resetting state: %s", relative_name)
            self.conn.execute("DELETE FROM page_state WHERE relative_name = ?", (relative_name,))
            self.conn.execute("DELETE FROM pdf_state WHERE relative_name = ?", (relative_name,))

        self.conn.execute(
            """INSERT INTO pdf_state
               (relative_name, source_path, file_size, file_mtime, sha256,
                page_count, ocr_lang, image_format, image_dpi, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (relative_name, source_path, file_size, file_mtime, sha256,
             page_count, ocr_lang, image_format, image_dpi, now),
        )

        # Initialize page states
        for page_num in range(1, page_count + 1):
            self.conn.execute(
                """INSERT OR IGNORE INTO page_state
                   (relative_name, page_num, status, updated_at)
                   VALUES (?, ?, 'pending', ?)""",
                (relative_name, page_num, now),
            )

        self.conn.commit()

    def get_pdf_state(self, relative_name: str) -> dict | None:
        """Return the state dict for a PDF, or None."""
        cursor = self.conn.execute(
            "SELECT * FROM pdf_state WHERE relative_name = ?",
            (relative_name,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def get_all_pdf_states(self) -> list[dict]:
        """Return all PDF state entries."""
        cursor = self.conn.execute("SELECT * FROM pdf_state ORDER BY relative_name")
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_page_state(self, relative_name: str, page_num: int) -> dict | None:
        """Return the state dict for a specific page."""
        cursor = self.conn.execute(
            "SELECT * FROM page_state WHERE relative_name = ? AND page_num = ?",
            (relative_name, page_num),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def get_page_states(self, relative_name: str) -> list[dict]:
        """Return all page states for a PDF."""
        cursor = self.conn.execute(
            "SELECT * FROM page_state WHERE relative_name = ? ORDER BY page_num",
            (relative_name,),
        )
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def is_page_complete(self, relative_name: str, page_num: int) -> bool:
        """Check if a page has been fully processed."""
        state = self.get_page_state(relative_name, page_num)
        if state is None:
            return False
        return state["status"] == "completed"

    def mark_page_image_saved(
        self,
        relative_name: str,
        page_num: int,
        image_path: str,
        image_size: int,
    ) -> None:
        """Record that a page image was saved successfully."""
        self.conn.execute(
            """UPDATE page_state
               SET image_saved = 1, image_path = ?, image_size = ?, updated_at = ?
               WHERE relative_name = ? AND page_num = ?""",
            (image_path, image_size, self._now(), relative_name, page_num),
        )
        self.conn.commit()

    def mark_page_text_extracted(
        self,
        relative_name: str,
        page_num: int,
        native_extracted: bool,
        ocr_completed: bool,
        ocr_text_recovered: bool,
        text_source: str,
    ) -> None:
        """Record text extraction results for a page."""
        self.conn.execute(
            """UPDATE page_state
               SET native_text_extracted = ?, ocr_completed = ?,
                   ocr_text_recovered = ?, text_source = ?, updated_at = ?
               WHERE relative_name = ? AND page_num = ?""",
            (
                int(native_extracted),
                int(ocr_completed),
                int(ocr_text_recovered),
                text_source,
                self._now(),
                relative_name,
                page_num,
            ),
        )
        self.conn.commit()

    def mark_page_complete(self, relative_name: str, page_num: int) -> None:
        """Mark a page as fully processed."""
        self.conn.execute(
            """UPDATE page_state
               SET status = 'completed', updated_at = ?
               WHERE relative_name = ? AND page_num = ?""",
            (self._now(), relative_name, page_num),
        )
        self.conn.commit()

    def mark_page_failed(
        self, relative_name: str, page_num: int, error: str
    ) -> None:
        """Mark a page as failed with an error message."""
        self.conn.execute(
            """UPDATE page_state
               SET status = 'failed', error_message = ?, updated_at = ?
               WHERE relative_name = ? AND page_num = ?""",
            (error, self._now(), relative_name, page_num),
        )
        self.conn.commit()

    def mark_pdf_started(self, relative_name: str) -> None:
        """Mark a PDF as currently being processed."""
        self.conn.execute(
            """UPDATE pdf_state
               SET status = 'processing', started_at = ?, updated_at = ?
               WHERE relative_name = ?""",
            (self._now(), self._now(), relative_name),
        )
        self.conn.commit()

    def mark_pdf_complete(self, relative_name: str) -> None:
        """Mark a PDF as fully processed."""
        # Check if any pages failed
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM page_state WHERE relative_name = ? AND status = 'failed'",
            (relative_name,),
        )
        failed_count = cursor.fetchone()[0]

        status = "completed_with_warnings" if failed_count > 0 else "completed"
        self.conn.execute(
            """UPDATE pdf_state
               SET status = ?, markdown_written = 1, finished_at = ?, updated_at = ?
               WHERE relative_name = ?""",
            (status, self._now(), self._now(), relative_name),
        )
        self.conn.commit()

    def mark_pdf_failed(self, relative_name: str, error: str) -> None:
        """Mark a PDF as failed."""
        self.conn.execute(
            """UPDATE pdf_state
               SET status = 'failed', error_message = ?, finished_at = ?, updated_at = ?
               WHERE relative_name = ?""",
            (error, self._now(), self._now(), relative_name),
        )
        self.conn.commit()

    def is_pdf_complete(self, relative_name: str) -> bool:
        """Check if a PDF has been fully processed."""
        state = self.get_pdf_state(relative_name)
        if state is None:
            return False
        return state["status"] in ("completed", "completed_with_warnings")

    def get_incomplete_pages(self, relative_name: str) -> list[int]:
        """Return page numbers (1-based) that are not yet completed."""
        cursor = self.conn.execute(
            """SELECT page_num FROM page_state
               WHERE relative_name = ? AND status != 'completed'
               ORDER BY page_num""",
            (relative_name,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        """Return overall processing statistics from the state database."""
        stats = {}

        cursor = self.conn.execute("SELECT COUNT(*) FROM pdf_state")
        stats["total_pdfs"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM pdf_state WHERE status IN ('completed', 'completed_with_warnings')"
        )
        stats["completed_pdfs"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM pdf_state WHERE status = 'failed'"
        )
        stats["failed_pdfs"] = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM page_state")
        stats["total_pages"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM page_state WHERE status = 'completed'"
        )
        stats["completed_pages"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM page_state WHERE status = 'failed'"
        )
        stats["failed_pages"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM page_state WHERE image_saved = 1"
        )
        stats["images_saved"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM page_state WHERE ocr_text_recovered = 1"
        )
        stats["ocr_text_recovered"] = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT COALESCE(SUM(page_count), 0) FROM pdf_state"
        )
        stats["total_page_count"] = cursor.fetchone()[0]

        return stats

    def set_metadata(self, key: str, value: str) -> None:
        """Store a key-value pair in run metadata."""
        self.conn.execute(
            "INSERT OR REPLACE INTO run_metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_metadata(self, key: str) -> str | None:
        """Retrieve a metadata value by key."""
        cursor = self.conn.execute(
            "SELECT value FROM run_metadata WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
