# Installation Guide — Linux

This guide covers installing PDF Notes Processor on Ubuntu-based distributions (Ubuntu, KDE neon, Linux Mint, Pop!_OS, etc.).

## Step 1: Install Python

Most Ubuntu-based systems include Python 3. Verify:

```bash
python3 --version
```

You need Python 3.9 or later. If Python is not installed:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

## Step 2: Install Tesseract OCR

Tesseract is the OCR engine. It must be installed as a system package:

```bash
sudo apt update
sudo apt install tesseract-ocr
```

### Install language data

**English (required):**
```bash
sudo apt install tesseract-ocr-eng
```

**Sinhala (optional):**
```bash
sudo apt install tesseract-ocr-sin
```

**See all available languages:**
```bash
apt-cache search tesseract-ocr-
```

### Verify Tesseract

```bash
tesseract --version
tesseract --list-langs
```

You should see `eng` in the list of languages.

## Step 3: Set up the project

```bash
# Navigate to the project directory
cd /path/to/pdfnotes

# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install the application with dev dependencies
pip install -e ".[dev]"
```

## Step 4: Verify installation

```bash
# Check the application
pdfnotes --version

# Check Tesseract is accessible
python3 -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

## Step 5: Run the application

```bash
# Activate the virtual environment (if not already active)
source .venv/bin/activate

# Process a folder of PDFs
pdfnotes process "/home/student/University/Semester1"
```

## Step 6: Find the output

After processing, check the `Result/` folder inside your source directory:

```
/home/student/University/Semester1/Result/
├── OCR/           ← Markdown files
├── Images/        ← Page images
├── report.json    ← Processing report
└── processing.log ← Detailed log
```

## Offline operation

After completing Steps 1–3, no internet connection is needed. All processing runs locally using Tesseract and Python libraries installed on your machine.

## Running tests

```bash
source .venv/bin/activate
pytest
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `tesseract: command not found` | Run `sudo apt install tesseract-ocr` |
| `Failed to load language 'sin'` | Run `sudo apt install tesseract-ocr-sin` |
| `ModuleNotFoundError: No module named 'pdfnotes'` | Activate the virtual environment: `source .venv/bin/activate` |
| Permission denied on output | Check write permissions on the source folder |

For more help, see [troubleshooting.md](troubleshooting.md).
