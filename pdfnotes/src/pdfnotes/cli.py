"""CLI — command-line interface for pdfnotes."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pdfnotes import __app_name__, __version__
from pdfnotes.config import ProcessingConfig
from pdfnotes.exceptions import (
    NoPDFsFoundError,
    PDFNotesError,
    SourceFolderError,
    TesseractLanguageError,
    TesseractNotFoundError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfnotes",
        description=(
            f"{__app_name__} v{__version__}\n"
            "Convert PDF lecture notes to clean Markdown with OCR support.\n"
            "Fully offline — no data leaves your computer."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Interactive wizard command
    subparsers.add_parser(
        "interactive",
        help="Launch interactive terminal wizard (arrow keys & checkboxes)",
        description="Interactive wizard to choose folders, select files, and configure options.",
    )

    # Process command
    process_parser = subparsers.add_parser(
        "process",
        help="Process PDF files in a folder",
        description=(
            "Find all PDFs in the specified folder, extract text using OCR,\n"
            "generate page images, and create Markdown output files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pdfnotes process ./University\n"
            "  pdfnotes process ./notes --lang eng+sin\n"
            "  pdfnotes process ./notes --recursive --resume\n"
            '  pdfnotes process ./notes --output "/path/to/output"\n'
            "  pdfnotes process ./notes --image-format jpeg --dpi 300\n"
        ),
    )

    process_parser.add_argument(
        "source",
        type=str,
        help="Path to the folder containing PDF files",
    )
    process_parser.add_argument(
        "--files", "-f",
        type=str,
        nargs="+",
        default=None,
        help="Optional: specific PDF file names to process inside the source folder",
    )
    process_parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Custom output directory (default: Result/ inside source folder)",
    )
    process_parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=False,
        help="Also search subfolders for PDFs",
    )
    process_parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help=(
            "Resume interrupted processing from saved state. Without --resume,\n"
            "existing completed outputs are preserved but new PDFs or changed\n"
            "PDFs are (re)processed. With --resume, only truly incomplete work\n"
            "is continued."
        ),
    )
    process_parser.add_argument(
        "--lang", "-l",
        type=str,
        default="eng",
        help='OCR language(s), e.g. "eng" or "eng+sin" (default: eng)',
    )
    process_parser.add_argument(
        "--image-format",
        type=str,
        choices=["png", "jpeg", "jpg"],
        default="png",
        help="Output image format (default: png)",
    )
    process_parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Image rendering resolution in DPI (default: 200)",
    )
    process_parser.add_argument(
        "--tesseract-cmd",
        type=str,
        default=None,
        help="Path to the tesseract executable (auto-detected if not set)",
    )
    process_parser.add_argument(
        "--ocr-timeout",
        type=int,
        default=120,
        help="Maximum seconds per page for OCR (default: 120)",
    )
    process_parser.add_argument(
        "--ocr-psm",
        type=int,
        default=3,
        choices=range(0, 14),
        help="Tesseract page segmentation mode (default: 3 = fully automatic)",
    )
    process_parser.add_argument(
        "--no-preprocess",
        action="store_true",
        default=False,
        help="Disable image preprocessing before OCR",
    )
    process_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 = success, 1 = partial failure, 2 = fatal error.
    """
    # If launched with no arguments in an interactive terminal, default to interactive wizard
    if (argv is None and len(sys.argv) == 1 and sys.stdin.isatty()) or (argv == [] and sys.stdin.isatty()):
        from pdfnotes.interactive import run_interactive_wizard
        return run_interactive_wizard()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "interactive":
        from pdfnotes.interactive import run_interactive_wizard
        return run_interactive_wizard()

    if args.command == "process":
        return _run_process(args)

    parser.print_help()
    return 0


def _run_process(args: argparse.Namespace) -> int:
    """Execute the process command."""
    # Build config
    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output).resolve() if args.output else None

    # Normalize image format
    image_format = args.image_format
    if image_format == "jpg":
        image_format = "jpeg"

    config = ProcessingConfig(
        source_dir=source_dir,
        output_dir=output_dir,
        recursive=args.recursive,
        resume=args.resume,
        ocr_lang=args.lang,
        image_format=image_format,
        image_dpi=args.dpi,
        tesseract_cmd=args.tesseract_cmd,
        ocr_timeout=args.ocr_timeout,
        ocr_psm=args.ocr_psm,
        debug=args.debug,
        preprocess=not args.no_preprocess,
        selected_files=args.files,
    )

    # Import here to avoid slow startup on --help
    from pdfnotes.processor import run_processing

    try:
        exit_code = run_processing(config)
        return exit_code
    except SourceFolderError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 2
    except NoPDFsFoundError as e:
        print(f"\n⚠️  {e}", file=sys.stderr)
        return 1
    except TesseractNotFoundError as e:
        print(f"\n❌ Tesseract OCR not found!\n\n{e}", file=sys.stderr)
        return 2
    except TesseractLanguageError as e:
        print(f"\n❌ Missing OCR language data!\n\n{e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user.", file=sys.stderr)
        print("Run with --resume to continue from where you left off.", file=sys.stderr)
        return 1
    except PDFNotesError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        if config.debug:
            import traceback
            traceback.print_exc()
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        print("Run with --debug for a full traceback.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
