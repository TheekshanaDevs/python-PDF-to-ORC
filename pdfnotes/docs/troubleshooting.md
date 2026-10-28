# Troubleshooting Guide

## Common Issues

### Tesseract not found

**Error:** `Tesseract OCR is not installed or not found in PATH`

**Linux fix:**
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-eng
```

**Windows fix:**
1. Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install Tesseract
3. Add the installation directory to your system PATH, or use:
```bash
pdfnotes process ./notes --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### Missing OCR language data

**Error:** `Missing OCR language data: sin`

**Linux:**
```bash
sudo apt install tesseract-ocr-sin
```

**Windows:**
1. Re-run the Tesseract installer and select the language
2. Or download the `.traineddata` file from [tessdata](https://github.com/tesseract-ocr/tessdata)
3. Place it in the Tesseract `tessdata` directory

**Verify installed languages:**
```bash
tesseract --list-langs
```

### ModuleNotFoundError

**Error:** `ModuleNotFoundError: No module named 'pdfnotes'`

Make sure the virtual environment is activated:
```bash
source .venv/bin/activate  # Linux
.venv\Scripts\activate     # Windows
```

Then install:
```bash
pip install -e ".[dev]"
```

### Permission denied

**Error:** `Permission denied` when creating output files

- Check that you have write access to the source folder
- Or use `--output` to specify a writable directory:
```bash
pdfnotes process ./readonly-notes --output ~/Desktop/Results
```

### PDF is password-protected

**Message:** `Skipped password-protected: document.pdf`

Password-protected PDFs are automatically skipped. Remove the password from the PDF first using a PDF editor, then reprocess.

### Corrupt or unreadable PDF

**Message:** `Skipped unreadable PDF: document.pdf`

The PDF file may be damaged. Try:
1. Opening the file in a PDF viewer to verify it works
2. Re-downloading the file
3. Using a PDF repair tool

### OCR produces poor results

If OCR output is low quality:

1. **Check the scan quality** — Open the page images in `Result/Images/` to see what Tesseract is working with
2. **Try higher DPI** — Use `--dpi 300` for better resolution
3. **Disable preprocessing** — If preprocessing hurts quality: `--no-preprocess`
4. **Try different PSM** — The page segmentation mode affects how Tesseract analyzes the page:
   - `--ocr-psm 3` (default) — Fully automatic
   - `--ocr-psm 6` — Assume a single uniform block of text
   - `--ocr-psm 4` — Assume a single column of text
5. **Check the language** — Ensure the correct OCR language is specified with `--lang`

### OCR timeout

**Error:** `OCR timed out after 120s`

Some pages may take very long to process:
```bash
pdfnotes process ./notes --ocr-timeout 300
```

### Disk space issues

**Error:** `No space left on device`

Page images can use significant disk space. Estimate ~200 KB per page at 200 DPI PNG. For 1000 pages, that's ~200 MB.

Options:
- Use JPEG format: `--image-format jpeg` (smaller files)
- Use a different output drive: `--output /path/to/bigger/drive`
- Clean up old results before reprocessing

### Resume not working

If `--resume` doesn't skip completed work:

1. The source PDF may have changed (SHA-256 hash differs)
2. OCR settings may have changed (language, DPI, format)
3. The state database may be corrupted

To force a fresh start, delete the state file:
```bash
rm Result/.pdfnotes_state.db
```

### Duplicate text in Markdown

The application compares native PDF text with OCR output and avoids obvious duplication. If you still see duplicated content:

1. This may indicate the text appeared differently in native extraction vs OCR
2. Check if the "Additional text recovered by OCR" section contains genuinely new content
3. The similarity threshold defaults to 75% — content that looks different enough is preserved

### Windows-specific issues

**Long file paths:**
Windows has a 260-character path limit by default. If your PDFs have very long names in deeply nested folders, you may hit this limit. Enable long paths in Windows or use shorter names.

**PowerShell execution:**
```powershell
python -m pdfnotes process "C:\Users\student\University"
```

**Path separators:**
Both forward slashes (`/`) and backslashes (`\`) work in the CLI.

## Getting more help

1. Run with `--debug` for detailed logging
2. Check `Result/processing.log` for diagnostic messages
3. Check `Result/report.json` for per-file error details
4. Open an issue with the debug log if the problem persists

## Installation Guide — Windows

### Step 1: Install Python

1. Download Python 3.9+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important:** Check "Add Python to PATH" during installation
4. Verify:
```powershell
python --version
```

### Step 2: Install Tesseract OCR

1. Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer
3. Select additional languages during installation if needed
4. Note the installation path (typically `C:\Program Files\Tesseract-OCR`)
5. Add to PATH:
   - Open System Properties → Advanced → Environment Variables
   - Edit the `Path` variable
   - Add `C:\Program Files\Tesseract-OCR`
6. Verify:
```powershell
tesseract --version
```

### Step 3: Set up the project

```powershell
cd C:\path\to\pdfnotes

python -m venv .venv
.venv\Scripts\activate

pip install -e ".[dev]"
```

### Step 4: Run

```powershell
pdfnotes process "C:\Users\student\University\Semester1"
```

Or specify the Tesseract path directly:
```powershell
pdfnotes process "C:\Users\student\University" --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```
