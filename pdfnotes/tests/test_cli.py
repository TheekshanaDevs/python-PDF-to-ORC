"""Tests for CLI module."""

from __future__ import annotations

import pytest

from pdfnotes.cli import build_parser, main


class TestCLI:
    """Tests for CLI argument parsing and validation."""

    def test_help_returns_zero(self):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_flag(self):
        """--version should print version and exit."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_process_help(self):
        """process --help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["process", "--help"])
        assert exc_info.value.code == 0

    def test_no_command_shows_help(self, capsys):
        """No command should show help and return 0."""
        code = main([])
        assert code == 0

    def test_invalid_source_returns_error(self):
        """Missing source folder should return exit code 2."""
        code = main(["process", "/nonexistent/path/that/does/not/exist"])
        assert code == 2

    def test_parser_accepts_all_options(self):
        """Parser should accept all documented options without error."""
        parser = build_parser()
        args = parser.parse_args([
            "process", "/some/path",
            "--output", "/out/path",
            "--recursive",
            "--resume",
            "--lang", "eng+sin",
            "--image-format", "jpeg",
            "--dpi", "300",
            "--tesseract-cmd", "/usr/bin/tesseract",
            "--ocr-timeout", "60",
            "--ocr-psm", "6",
            "--no-preprocess",
            "--debug",
        ])

        assert args.source == "/some/path"
        assert args.output == "/out/path"
        assert args.recursive is True
        assert args.resume is True
        assert args.lang == "eng+sin"
        assert args.image_format == "jpeg"
        assert args.dpi == 300
        assert args.tesseract_cmd == "/usr/bin/tesseract"
        assert args.ocr_timeout == 60
        assert args.ocr_psm == 6
        assert args.no_preprocess is True
        assert args.debug is True

    def test_default_values(self):
        """Parser defaults should match requirements."""
        parser = build_parser()
        args = parser.parse_args(["process", "/some/path"])

        assert args.output is None
        assert args.recursive is False
        assert args.resume is False
        assert args.lang == "eng"
        assert args.image_format == "png"
        assert args.dpi == 200
        assert args.tesseract_cmd is None
        assert args.ocr_timeout == 120

    def test_paths_with_spaces(self):
        """Parser should handle paths with spaces."""
        parser = build_parser()
        args = parser.parse_args(["process", "/path/with spaces/folder"])
        assert args.source == "/path/with spaces/folder"

    def test_invalid_image_format(self):
        """Invalid image format should be rejected by argparse."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["process", "/path", "--image-format", "bmp"])
