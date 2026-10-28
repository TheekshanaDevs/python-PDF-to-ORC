"""Progress display — Rich-based terminal progress for processing."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger("pdfnotes.progress")

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class PlainProgress:
    """Fallback progress display when Rich is not available."""

    def __init__(self):
        self.started = time.time()
        self._last_msg = ""

    def print_header(self, source: str, output: str, lang: str, dpi: int, pdf_count: int):
        print(f"\nPDF Notes Processor")
        print(f"  Source: {source}")
        print(f"  Output: {output}")
        print(f"  OCR languages: {lang}")
        print(f"  Image resolution: {dpi} DPI")
        print(f"  PDFs found: {pdf_count}")
        print()

    def update_pdf(self, name: str, index: int, total: int):
        elapsed = time.time() - self.started
        msg = f"[{index}/{total}] Processing: {name}  (elapsed: {elapsed:.0f}s)"
        print(msg)

    def update_page(self, page: int, total: int, pdf_name: str):
        pass  # Don't flood terminal

    def complete_pdf(self, name: str, success: bool):
        status = "✓" if success else "✗"
        print(f"  {status} {name}")

    def print_summary(
        self,
        completed: int,
        failed: int,
        total: int,
        pages_completed: int,
        pages_failed: int,
    ):
        elapsed = time.time() - self.started
        mins, secs = divmod(int(elapsed), 60)
        hours, mins = divmod(mins, 60)
        print(f"\nCompleted PDFs: {completed}/{total}")
        print(f"Failed PDFs: {failed}")
        print(f"Pages completed: {pages_completed}")
        print(f"Pages failed: {pages_failed}")
        print(f"Elapsed time: {hours:02d}:{mins:02d}:{secs:02d}")
        print()


class RichProgress:
    """Rich-based terminal progress display."""

    def __init__(self):
        self.console = Console()
        self.started = time.time()
        self._source = ""
        self._output = ""
        self._lang = ""
        self._dpi = 0
        self._pdf_count = 0
        self._current_pdf = ""
        self._current_page = 0
        self._total_pages = 0
        self._completed_pdfs = 0
        self._failed_pdfs = 0
        self._completed_pages = 0
        self._failed_pages = 0
        self._pdf_index = 0
        self._total_pdfs = 0
        self._live: Live | None = None
        self._overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        )
        self._page_progress = Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
        )
        self._overall_task = None
        self._page_task = None

    def print_header(self, source: str, output: str, lang: str, dpi: int, pdf_count: int):
        self._source = source
        self._output = output
        self._lang = lang
        self._dpi = dpi
        self._pdf_count = pdf_count
        self._total_pdfs = pdf_count

        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold green]PDF Notes Processor[/]\n\n"
                f"[dim]Source:[/]  {source}\n"
                f"[dim]Output:[/]  {output}\n"
                f"[dim]OCR:[/]     {lang}\n"
                f"[dim]DPI:[/]     {dpi}\n"
                f"[dim]PDFs:[/]    {pdf_count}",
                border_style="blue",
            )
        )
        self.console.print()

    def start_live(self):
        """Start the live updating display."""
        self._overall_task = self._overall_progress.add_task(
            "Overall", total=self._total_pdfs
        )
        self._page_task = self._page_progress.add_task(
            "Pages", total=0
        )
        self._live = Live(self._make_display(), console=self.console, refresh_per_second=4)
        self._live.start()

    def stop_live(self):
        """Stop the live display."""
        if self._live:
            self._live.stop()
            self._live = None

    def _make_display(self) -> Table:
        """Build the live display table."""
        elapsed = time.time() - self.started
        mins, secs = divmod(int(elapsed), 60)
        hours, mins = divmod(mins, 60)

        table = Table.grid(padding=(0, 2))
        table.add_row(self._overall_progress)
        table.add_row(self._page_progress)
        table.add_row()

        stats = Table.grid(padding=(0, 3))
        stats.add_row(
            f"[bold]Processing:[/] {self._current_pdf}",
            f"[bold]Page:[/] {self._current_page}/{self._total_pages}",
        )
        stats.add_row(
            f"[green]Completed PDFs:[/] {self._completed_pdfs}/{self._total_pdfs}",
            f"[red]Failed PDFs:[/] {self._failed_pdfs}",
        )
        stats.add_row(
            f"[green]Completed pages:[/] {self._completed_pages}",
            f"[red]Failed pages:[/] {self._failed_pages}",
        )
        stats.add_row(
            f"[dim]Elapsed:[/] {hours:02d}:{mins:02d}:{secs:02d}",
        )

        table.add_row(stats)
        return table

    def update_pdf(self, name: str, index: int, total: int):
        self._current_pdf = name
        self._pdf_index = index
        self._total_pdfs = total
        if self._live:
            self._live.update(self._make_display())

    def update_page(self, page: int, total: int, pdf_name: str):
        self._current_page = page
        self._total_pages = total
        if self._page_task is not None:
            self._page_progress.update(
                self._page_task,
                completed=page,
                total=total,
                description=f"Page {page}/{total}",
            )
        if self._live:
            self._live.update(self._make_display())

    def complete_pdf(self, name: str, success: bool):
        if success:
            self._completed_pdfs += 1
        else:
            self._failed_pdfs += 1
        if self._overall_task is not None:
            self._overall_progress.update(
                self._overall_task,
                completed=self._completed_pdfs + self._failed_pdfs,
            )
        if self._live:
            self._live.update(self._make_display())

    def increment_page_result(self, success: bool):
        """Track individual page results."""
        if success:
            self._completed_pages += 1
        else:
            self._failed_pages += 1
        if self._live:
            self._live.update(self._make_display())

    def print_summary(
        self,
        completed: int,
        failed: int,
        total: int,
        pages_completed: int,
        pages_failed: int,
    ):
        elapsed = time.time() - self.started
        mins, secs = divmod(int(elapsed), 60)
        hours, mins = divmod(mins, 60)

        self.console.print()
        summary = Table(title="Processing Summary", show_header=False, border_style="green")
        summary.add_column("Metric", style="bold")
        summary.add_column("Value")

        summary.add_row("PDFs Completed", f"[green]{completed}[/] / {total}")
        summary.add_row("PDFs Failed", f"[{'red' if failed else 'green'}]{failed}[/]")
        summary.add_row("Pages Completed", f"[green]{pages_completed}[/]")
        summary.add_row("Pages Failed", f"[{'red' if pages_failed else 'green'}]{pages_failed}[/]")
        summary.add_row("Elapsed Time", f"{hours:02d}:{mins:02d}:{secs:02d}")

        self.console.print(summary)
        self.console.print()


def create_progress() -> RichProgress | PlainProgress:
    """Create the appropriate progress display."""
    if HAS_RICH:
        return RichProgress()
    return PlainProgress()
