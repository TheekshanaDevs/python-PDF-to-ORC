# Usage Guide

## Basic usage

Process all PDFs in a folder:

```bash
pdfnotes process "/path/to/your/pdf-folder"
```

Or using the module form:

```bash
python -m pdfnotes process "/path/to/your/pdf-folder"
```

## Command reference

### Process command options

| Option | Default | Description |
|---|---|---|
| `source` | (required) | Path to folder containing PDFs |
| `--output`, `-o` | `Result/` inside source | Custom output directory |
| `--recursive`, `-r` | off | Search subfolders for PDFs |
| `--resume` | off | Resume from saved progress |
| `--lang`, `-l` | `eng` | OCR language(s) |
| `--image-format` | `png` | Image format: `png` or `jpeg` |
| `--dpi` | `200` | Image resolution (dots per inch) |
| `--tesseract-cmd` | auto-detect | Path to tesseract executable |
| `--ocr-timeout` | `120` | Max seconds per page for OCR |
| `--ocr-psm` | `3` | Tesseract page segmentation mode |
| `--no-preprocess` | off | Skip image preprocessing |
| `--debug` | off | Enable debug logging |

## Examples

### Process a single folder
```bash
pdfnotes process ./University
```

### Process with subfolders
```bash
pdfnotes process ./University --recursive
```

### Resume after interruption
```bash
# Press Ctrl+C during processing
# Later, resume:
pdfnotes process ./University --resume
```

### Multiple OCR languages
```bash
pdfnotes process ./University --lang eng+sin
```

### Save output elsewhere
```bash
pdfnotes process ./University --output ~/Desktop/Results
```

### JPEG images (smaller file size)
```bash
pdfnotes process ./University --image-format jpeg
```

### Higher resolution images
```bash
pdfnotes process ./University --dpi 300
```

### Specify Tesseract path (Windows)
```bash
pdfnotes process ./University --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### Debug mode
```bash
pdfnotes process ./University --debug
```

## Understanding the output

### Markdown files (OCR/)

Each PDF gets its own Markdown file with:
- Document title and source filename
- Page count
- Extracted text organized by page
- Links to corresponding page images

### Page images (Images/)

Each PDF gets a subfolder containing one PNG/JPEG per page:
```
Images/Lecture_01/
├── Lecture_01_page_001.png
├── Lecture_01_page_002.png
└── ...
```

### Combined Markdown

`semester_combined.md` contains all processed PDFs in one file with:
- Table of contents
- Clear boundaries between documents
- All page content

### Report (report.json)

JSON file with complete processing statistics:
- PDFs discovered, completed, failed, skipped
- Pages processed, failed
- Images created
- Processing duration

### Log (processing.log)

Detailed diagnostic log for troubleshooting.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All PDFs processed successfully |
| 1 | Partial success (some PDFs or pages failed) |
| 2 | Fatal error (cannot start processing) |

## Tips

1. **Start with a small test** — Try with 2–3 PDFs first to verify everything works.
2. **Use resume for large collections** — If processing 50+ PDFs, use `--resume` so you can stop and continue.
3. **Check the report** — Always review `report.json` after processing to catch any issues.
4. **PNG vs JPEG** — Use PNG (default) for best quality. Use JPEG for smaller file sizes.
5. **Debug mode** — Use `--debug` if something goes wrong for detailed logging.
