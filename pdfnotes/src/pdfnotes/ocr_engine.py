"""OCR engine — Tesseract OCR integration with preprocessing and validation."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from pathlib import Path

import pytesseract
from PIL import Image

from pdfnotes.exceptions import (
    OCRError,
    OCRTimeoutError,
    TesseractLanguageError,
    TesseractNotFoundError,
)

logger = logging.getLogger("pdfnotes.ocr_engine")


def _get_install_instructions() -> str:
    """Return OS-specific Tesseract installation instructions."""
    system = platform.system()
    if system == "Linux":
        return (
            "Tesseract OCR is not installed or not found in PATH.\n\n"
            "Install on Ubuntu/Debian/KDE neon:\n"
            "  sudo apt update\n"
            "  sudo apt install tesseract-ocr\n\n"
            "Install English language data:\n"
            "  sudo apt install tesseract-ocr-eng\n\n"
            "Install Sinhala language data:\n"
            "  sudo apt install tesseract-ocr-sin\n\n"
            "For other distributions, use your package manager to install 'tesseract-ocr'."
        )
    elif system == "Windows":
        return (
            "Tesseract OCR is not installed or not found in PATH.\n\n"
            "Install on Windows:\n"
            "  1. Download the installer from:\n"
            "     https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  2. Run the installer (select additional languages if needed).\n"
            "  3. Add the Tesseract install directory to your PATH, or use\n"
            "     --tesseract-cmd to specify the full path to tesseract.exe.\n\n"
            "Example:\n"
            "  pdfnotes process ./notes --tesseract-cmd \"C:\\Program Files\\Tesseract-OCR\\tesseract.exe\"\n"
        )
    else:
        return (
            "Tesseract OCR is not installed or not found in PATH.\n"
            "Please install Tesseract OCR for your operating system.\n"
            "See: https://github.com/tesseract-ocr/tesseract"
        )


def find_tesseract(custom_path: str | None = None) -> str:
    """Locate the Tesseract executable.

    Args:
        custom_path: User-specified path to tesseract executable.

    Returns:
        Path to the tesseract executable.

    Raises:
        TesseractNotFoundError: If Tesseract cannot be found.
    """
    if custom_path:
        path = Path(custom_path)
        if path.is_file():
            return str(path)
        raise TesseractNotFoundError(
            f"Specified Tesseract path does not exist: {custom_path}\n\n"
            + _get_install_instructions()
        )

    # Try to find in PATH
    tess_path = shutil.which("tesseract")
    if tess_path:
        return tess_path

    # Windows common locations
    if platform.system() == "Windows":
        common_paths = [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
        for cp in common_paths:
            if cp.is_file():
                return str(cp)

    raise TesseractNotFoundError(_get_install_instructions())


def get_installed_languages(tesseract_cmd: str) -> list[str]:
    """Return the list of installed Tesseract language codes.

    Args:
        tesseract_cmd: Path to the tesseract executable.

    Returns:
        List of language codes (e.g., ['eng', 'osd', 'sin']).
    """
    try:
        result = subprocess.run(
            [tesseract_cmd, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.strip().split("\n") + result.stderr.strip().split("\n")
        langs = []
        skip_header = True
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if skip_header and ("list of" in line.lower() or ":" in line):
                skip_header = False
                continue
            if line and not line.startswith("List") and ":" not in line:
                langs.append(line)
        return langs
    except Exception as e:
        logger.warning("Could not list Tesseract languages: %s", e)
        return []


def validate_languages(tesseract_cmd: str, requested_langs: str) -> None:
    """Check that all requested OCR languages are installed.

    Args:
        tesseract_cmd: Path to the tesseract executable.
        requested_langs: Language string like "eng" or "eng+sin".

    Raises:
        TesseractLanguageError: If any requested language is missing.
    """
    installed = get_installed_languages(tesseract_cmd)
    if not installed:
        logger.warning("Could not verify installed languages; proceeding anyway.")
        return

    requested = [lang.strip() for lang in requested_langs.split("+")]
    missing = [lang for lang in requested if lang not in installed]

    if missing:
        system = platform.system()
        if system == "Linux":
            install_hint = "\n".join(
                f"  sudo apt install tesseract-ocr-{lang}" for lang in missing
            )
        elif system == "Windows":
            install_hint = (
                "Re-run the Tesseract installer and select the missing languages,\n"
                "or download the .traineddata files from:\n"
                "  https://github.com/tesseract-ocr/tessdata\n"
                "and place them in the Tesseract tessdata directory."
            )
        else:
            install_hint = "Install the missing language data for your system."

        raise TesseractLanguageError(
            f"Missing OCR language data: {', '.join(missing)}\n"
            f"Installed languages: {', '.join(installed)}\n\n"
            f"To install:\n{install_hint}"
        )

    logger.info("Validated OCR languages: %s", requested_langs)


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """Apply light preprocessing to improve OCR accuracy.

    Converts to grayscale and adjusts contrast. Does NOT modify the original image.

    Args:
        image: Input PIL Image.

    Returns:
        Preprocessed PIL Image suitable for OCR.
    """
    try:
        import cv2
        import numpy as np

        # Convert PIL to OpenCV
        img_array = np.array(image)

        # Convert to grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Light denoising
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

        # Adaptive threshold for better text contrast (only if image is mostly text-like)
        # Use OTSU binarization which is good for printed text
        # But return the denoised grayscale since full binarization can destroy diagrams
        # Instead, just enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        return Image.fromarray(enhanced)

    except ImportError:
        logger.debug("OpenCV not available; skipping preprocessing")
        # Fallback: just convert to grayscale
        return image.convert("L")
    except Exception as e:
        logger.debug("Preprocessing failed, using original: %s", e)
        return image.convert("L")


def run_ocr(
    image: Image.Image,
    lang: str = "eng",
    tesseract_cmd: str | None = None,
    timeout: int = 120,
    psm: int = 3,
    preprocess: bool = True,
) -> str:
    """Run Tesseract OCR on a PIL Image.

    Args:
        image: The page image to OCR.
        lang: Tesseract language string (e.g., "eng" or "eng+sin").
        tesseract_cmd: Path to tesseract executable.
        timeout: Maximum seconds for OCR on this page.
        psm: Page segmentation mode.
        preprocess: Whether to preprocess the image first.

    Returns:
        Extracted text string (may be empty).

    Raises:
        OCRError: If OCR fails unexpectedly.
        OCRTimeoutError: If OCR exceeds the timeout.
    """
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # Preprocess for better OCR
    ocr_image = preprocess_image_for_ocr(image) if preprocess else image

    config = f"--psm {psm}"

    try:
        text = pytesseract.image_to_string(
            ocr_image,
            lang=lang,
            config=config,
            timeout=timeout,
        )
        return text if text else ""

    except RuntimeError as e:
        if "timeout" in str(e).lower():
            raise OCRTimeoutError(f"OCR timed out after {timeout}s") from e
        raise OCRError(f"OCR failed: {e}") from e
    except pytesseract.TesseractError as e:
        raise OCRError(f"Tesseract error: {e}") from e
    except Exception as e:
        raise OCRError(f"Unexpected OCR error: {e}") from e
