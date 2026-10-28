# PDF Notes Processor

**Offline PDF-to-Markdown OCR tool for university lecture notes.**

Convert entire semesters of PDF lecture notes into clean, searchable Markdown files — perfect for uploading to AI study tools, revision, and question answering.

## Features

- 📄 **Batch PDF processing** — Process all PDFs in a folder at once
- 🔍 **Dual text extraction** — Extracts native PDF text AND runs OCR on every page
- 📸 **Image-based text recovery** — Reads text from scanned pages, screenshots, diagrams, and embedded images
- 📝 **Clean Markdown output** — One `.md` file per PDF plus a combined semester file
- 🖼️ **Page images** — Every page saved as a PNG/JPEG image at 200 DPI
- 🔄 **Resume support** — Interrupted processing can be resumed without repeating work
- 📊 **Detailed reports** — JSON report with per-PDF and per-page statistics
- 🌐 **Multi-language OCR** — Supports English, Sinhala, and any Tesseract language
- 💻 **Cross-platform** — Works on Linux and Windows
- 🔒 **Fully offline** — No data leaves your computer

## Requirements

- **Python** 3.9 or later
- **Tesseract OCR** 4.x or 5.x (system package — must be installed separately)
- ~500 MB disk space for dependencies

## Quick Start

### 1. Install Tesseract OCR

**Ubuntu / KDE neon / Debian:**
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-eng
```

**Windows:**
Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH.

### 2. Install PDF Notes Processor

```bash
# Clone or download the project
cd pdfnotes

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux
# .venv\Scripts\activate   # Windows

# Install
pip install -e ".[dev]"
```

### 3. Process Your PDFs

```bash
# Basic usage
pdfnotes process "/path/to/your/lecture-notes"

# Or using the module form
python -m pdfnotes process "/path/to/your/lecture-notes"
```

## CLI Commands

### Process a folder
```bash
pdfnotes process ./University
```

### Process with subfolders
```bash
pdfnotes process ./University --recursive
```

### Resume interrupted processing
```bash
pdfnotes process ./University --resume
```

### Use multiple OCR languages
```bash
# English + Sinhala
pdfnotes process ./University --lang eng+sin
```

### Custom output directory
```bash
pdfnotes process ./University --output /path/to/output
```

### JPEG images instead of PNG
```bash
pdfnotes process ./University --image-format jpeg
```

### All options
```bash
pdfnotes process ./University \
    --recursive \
    --resume \
    --lang eng+sin \
    --image-format png \
    --dpi 200 \
    --ocr-timeout 120 \
    --debug
```

### Help
```bash
pdfnotes --help
pdfnotes process --help
```

## Output Structure

Given this input folder:
```
University/
├── Lecture_01.pdf
├── Lecture_02.pdf
└── Database_Notes.pdf
```

The program creates:
```
University/
├── Lecture_01.pdf          (unchanged)
├── Lecture_02.pdf          (unchanged)
├── Database_Notes.pdf      (unchanged)
└── Result/
    ├── OCR/
    │   ├── Lecture_01.md
    │   ├── Lecture_02.md
    │   ├── Database_Notes.md
    │   └── semester_combined.md
    ├── Images/
    │   ├── Lecture_01/
    │   │   ├── Lecture_01_page_001.png
    │   │   └── Lecture_01_page_002.png
    │   ├── Lecture_02/
    │   │   └── ...
    │   └── Database_Notes/
    │       └── ...
    ├── report.json
    └── processing.log
```

## OCR Language Setup

### List installed languages
```bash
tesseract --list-langs
```

### Install additional languages

**Ubuntu/Debian:**
```bash
# Sinhala
sudo apt install tesseract-ocr-sin

# Tamil
sudo apt install tesseract-ocr-tam

# All available
apt-cache search tesseract-ocr-
```

**Windows:**
Re-run the Tesseract installer and select additional languages, or download `.traineddata` files from [tessdata](https://github.com/tesseract-ocr/tessdata) and place them in the Tesseract `tessdata` directory.

### Using multiple languages
```bash
pdfnotes process ./notes --lang eng+sin
```

The `+` separates language codes. All specified languages must be installed.

## Resume Support

Processing state is saved in `Result/.pdfnotes_state.db` (SQLite).

- **Normal run** (no `--resume`): Existing completed results are preserved. New or changed PDFs are processed. Pages are not re-processed if the source PDF hasn't changed and settings match.
- **Resume run** (`--resume`): Explicitly skips all fully completed PDFs and only processes incomplete ones.

State is invalidated when:
- The source PDF changes (detected via SHA-256 hash)
- OCR language settings change
- Image format or DPI settings change

## Report

The `report.json` file contains:
- Overall status (`completed`, `completed_with_warnings`, `failed`)
- Processing timestamps and duration
- Per-PDF statistics (pages, images, errors)
- Skipped files with reasons
- Summary counts

## Known Limitations

- **Handwriting recognition** — Tesseract is designed for printed text. Handwriting recognition accuracy is limited.
- **Complex equations** — Mathematical equations may not be perfectly converted.
- **Complex table layouts** — Tables with merged cells or complex structures may not preserve perfectly.
- **Low-quality scans** — Very low resolution or heavily degraded scans will produce poor OCR results.
- **Right-to-left text** — RTL text requires appropriate Tesseract language data.
- **OCR accuracy** — OCR is inherently imperfect. Always verify critical content.

## Privacy & Offline Operation

This tool is **completely offline**:
- ❌ No network requests
- ❌ No cloud APIs
- ❌ No telemetry
- ❌ No data upload
- ✅ All processing happens locally
- ✅ Only uses installed local software (Python + Tesseract)

Once dependencies are installed, no internet connection is needed.

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests without requiring Tesseract
pytest -m "not requires_tesseract"

# Run with coverage
pytest --cov=pdfnotes --cov-report=html
```

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

## Uninstall

```bash
pip uninstall pdfnotes
# Optionally remove Tesseract
sudo apt remove tesseract-ocr  # Linux
```

The `Result/` output folder is not removed by uninstalling. Delete it manually if no longer needed.

## License

MIT License
