"""Application configuration and settings."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProcessingConfig:
    """Holds all processing settings for a run."""

    source_dir: Path = field(default_factory=lambda: Path("."))
    output_dir: Path | None = None
    recursive: bool = False
    resume: bool = False
    ocr_lang: str = "eng"
    image_format: str = "png"
    image_dpi: int = 200
    tesseract_cmd: str | None = None
    ocr_timeout: int = 120  # seconds per page
    ocr_psm: int = 3  # Tesseract page segmentation mode
    debug: bool = False
    preprocess: bool = True  # Enable image preprocessing for OCR
    combined_size_warn_mb: float = 100.0  # Warn if combined MD exceeds this

    @property
    def resolved_output_dir(self) -> Path:
        """Return the effective output directory."""
        if self.output_dir is not None:
            return self.output_dir
        return self.source_dir / "Result"

    @property
    def ocr_dir(self) -> Path:
        return self.resolved_output_dir / "OCR"

    @property
    def images_dir(self) -> Path:
        return self.resolved_output_dir / "Images"

    @property
    def report_path(self) -> Path:
        return self.resolved_output_dir / "report.json"

    @property
    def log_path(self) -> Path:
        return self.resolved_output_dir / "processing.log"

    @property
    def state_db_path(self) -> Path:
        return self.resolved_output_dir / ".pdfnotes_state.db"

    def to_dict(self) -> dict:
        """Serialize config to a JSON-compatible dict."""
        d = asdict(self)
        d["source_dir"] = str(self.source_dir)
        d["output_dir"] = str(self.output_dir) if self.output_dir else None
        return d

    @staticmethod
    def get_platform_info() -> dict:
        """Return platform details for diagnostics."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
        }
