"""Interactive TUI / Wizard for pdfnotes."""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
from questionary import Choice, Style
from rich.console import Console
from rich.panel import Panel

from pdfnotes import __app_name__, __version__
from pdfnotes.config import ProcessingConfig
from pdfnotes.discovery import discover_pdfs
from pdfnotes.processor import run_processing

console = Console()

CUSTOM_STYLE = Style(
    [
        ("qmark", "fg:#00d7af bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7af bold"),
        ("pointer", "fg:#ff5faf bold"),
        ("highlighted", "fg:#00ffff bold"),
        ("selected", "fg:#5fd700"),
        ("separator", "fg:#6c6c6c"),
        ("instruction", "fg:#8a8a8a italic"),
    ]
)


def _format_size(size_bytes: int) -> str:
    """Format bytes into readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"


def run_interactive_wizard(default_dir: Path | None = None) -> int:
    """Run interactive CLI wizard to select folder, pick files, and start processing.

    Args:
        default_dir: Optional starting directory.

    Returns:
        Exit code: 0 on success, 1 on error/cancel.
    """
    # Check if standard input is an interactive terminal
    if not sys.stdin.isatty():
        console.print("[bold yellow]Notice:[/bold yellow] No interactive terminal (TTY) detected.")
        console.print("To run the interactive menu with arrow keys, please run in your system terminal:")
        console.print("  [cyan]./run.sh[/cyan]\n")
        console.print("Or use the CLI command directly:")
        console.print("  [cyan]./run.sh process \"<path-to-folder>\" -o \"<output-folder>\"[/cyan]")
        return 0

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]{__app_name__} v{__version__}[/bold cyan]\n"
            "[dim]Interactive Lecture Notes Processor & OCR[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    # 1. Ask for Source Directory
    start_path = default_dir or Path.cwd()
    if not (start_path / "samples").exists() and (start_path.parent / "samples").exists():
        start_path = start_path.parent

    # Check quick suggestions
    suggestions = []
    if (Path.cwd() / "samples").exists():
        suggestions.append(str((Path.cwd() / "samples").resolve()))
    if Path.cwd().name == "pdfnotes" and (Path.cwd() / "samples").exists():
        suggestions.append("./samples")

    try:
        source_input = questionary.text(
            "Enter or paste the folder path containing your PDF lecture notes:",
            default="./samples" if (Path.cwd() / "samples").exists() else str(Path.cwd()),
            style=CUSTOM_STYLE,
        ).ask()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return 0

    if not source_input:
        console.print("[yellow]Cancelled by user.[/yellow]")
        return 0

    source_dir = Path(source_input.strip()).expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] '{source_dir}' is not a valid directory.")
        return 1

    # Check subfolders option
    recursive = questionary.confirm(
        "Scan subfolders recursively as well?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    if recursive is None:
        return 0

    # Discover PDFs
    console.print(f"[dim]Scanning '{source_dir}' for PDF files...[/dim]")
    discovered, skipped = discover_pdfs(source_dir, recursive=recursive)

    if not discovered:
        console.print(f"[bold yellow]No readable PDF files found in:[/bold yellow] {source_dir}")
        if skipped:
            console.print("[dim]Skipped files:[/dim]")
            for s in skipped:
                console.print(f"  • {s.path.name}: {s.reason}")
        return 1

    console.print(f"[green]Found {len(discovered)} PDF file(s).[/green]")

    # 2. Select files via Checkbox
    choices = []
    for pdf in discovered:
        size_str = _format_size(pdf.size_bytes)
        label = f"{pdf.path.name}  ({pdf.page_count} pages, {size_str})"
        choices.append(Choice(title=label, value=pdf.path.name, checked=True))

    selected_files = questionary.checkbox(
        "Select the PDFs you want to process (Space to toggle, Enter to confirm):",
        choices=choices,
        style=CUSTOM_STYLE,
    ).ask()

    if not selected_files:
        console.print("[yellow]No files selected. Aborting.[/yellow]")
        return 0

    console.print(f"[bold green]✓[/bold green] Selected [cyan]{len(selected_files)}[/cyan] PDF(s).")
    console.print()

    # 3. Quick Output Settings
    default_out = str((source_dir / "Result").resolve())
    output_choice = questionary.select(
        "Where do you want to save the output?",
        choices=[
            Choice(f"Default: '{source_dir.name}/Result' folder", value=default_out),
            Choice("Custom output folder...", value="custom"),
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if output_choice is None:
        return 0

    if output_choice == "custom":
        custom_out = questionary.text(
            "Enter custom output folder path:",
            default=str(Path.cwd() / "output"),
            style=CUSTOM_STYLE,
        ).ask()
        if not custom_out:
            return 0
        resolved_out = Path(custom_out.strip()).expanduser().resolve()
    else:
        resolved_out = Path(default_out)

    # 4. OCR / Quality Quick Settings
    configure_advanced = questionary.confirm(
        "Configure quality settings (DPI, OCR language, Image format)?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    image_dpi = 200
    image_fmt = "png"
    ocr_lang = "eng"

    if configure_advanced:
        dpi_str = questionary.select(
            "Image Rendering Quality (DPI):",
            choices=[
                Choice("Standard (200 DPI) - Recommended, fast and sharp", value="200"),
                Choice("High Resolution (300 DPI) - Best for small math formulas/handwriting", value="300"),
                Choice("Fast Draft (150 DPI) - Fastest processing", value="150"),
            ],
            style=CUSTOM_STYLE,
        ).ask()
        image_dpi = int(dpi_str or "200")

        image_fmt = questionary.select(
            "Page Image Format:",
            choices=[
                Choice("PNG - Lossless crisp quality", value="png"),
                Choice("JPEG - Smaller file size", value="jpeg"),
            ],
            style=CUSTOM_STYLE,
        ).ask() or "png"

        ocr_lang = questionary.text(
            "OCR Language (Tesseract code):",
            default="eng",
            style=CUSTOM_STYLE,
        ).ask() or "eng"

    # 5. Confirm and Start
    console.print()
    ready = questionary.confirm(
        f"Ready to process {len(selected_files)} file(s) into '{resolved_out}'?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    if not ready:
        console.print("[yellow]Cancelled.[/yellow]")
        return 0

    # Build config and run!
    config = ProcessingConfig(
        source_dir=source_dir,
        output_dir=resolved_out,
        recursive=recursive,
        resume=False,
        ocr_lang=ocr_lang,
        image_format=image_fmt,
        image_dpi=image_dpi,
        selected_files=selected_files,
    )

    console.print()
    return run_processing(config)
