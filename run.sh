#!/usr/bin/env bash
# ==============================================================================
# One-Click Launcher for PDF Notes Processor
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find Python in .venv
if [ -f "$SCRIPT_DIR/pdfnotes/.venv/bin/python" ]; then
    VENV_PY="$SCRIPT_DIR/pdfnotes/.venv/bin/python"
    WORK_DIR="$SCRIPT_DIR/pdfnotes"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    VENV_PY="$SCRIPT_DIR/.venv/bin/python"
    WORK_DIR="$SCRIPT_DIR"
else
    echo "Virtual environment (.venv) not found. Setting it up now..."
    python3 -m venv "$SCRIPT_DIR/pdfnotes/.venv"
    "$SCRIPT_DIR/pdfnotes/.venv/bin/pip" install -e "$SCRIPT_DIR/pdfnotes"
    VENV_PY="$SCRIPT_DIR/pdfnotes/.venv/bin/python"
    WORK_DIR="$SCRIPT_DIR/pdfnotes"
fi

cd "$WORK_DIR"

if [ $# -eq 0 ]; then
    exec "$VENV_PY" -m pdfnotes.interactive
else
    exec "$VENV_PY" -m pdfnotes "$@"
fi
