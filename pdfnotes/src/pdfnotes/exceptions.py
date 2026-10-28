"""Application-specific exception classes."""


class PDFNotesError(Exception):
    """Base exception for all pdfnotes errors."""


class SourceFolderError(PDFNotesError):
    """The source folder is invalid, missing, or inaccessible."""


class OutputDirectoryError(PDFNotesError):
    """The output directory cannot be created or written to."""


class NoPDFsFoundError(PDFNotesError):
    """No PDF files were found in the source folder."""


class TesseractNotFoundError(PDFNotesError):
    """Tesseract OCR executable is not installed or not accessible."""


class TesseractLanguageError(PDFNotesError):
    """Requested OCR language data is not installed."""


class PDFReadError(PDFNotesError):
    """A PDF file could not be opened or read."""


class PDFPasswordError(PDFReadError):
    """A PDF file is password-protected."""


class PDFCorruptError(PDFReadError):
    """A PDF file is corrupt or unreadable."""


class PageRenderError(PDFNotesError):
    """A PDF page could not be rendered to an image."""


class OCRError(PDFNotesError):
    """OCR processing failed on a page."""


class OCRTimeoutError(OCRError):
    """OCR processing exceeded the allowed time limit."""


class ImageWriteError(PDFNotesError):
    """An image file could not be saved."""


class MarkdownWriteError(PDFNotesError):
    """A Markdown file could not be written."""


class StateError(PDFNotesError):
    """The processing state database is invalid or inaccessible."""


class DiskSpaceError(PDFNotesError):
    """Insufficient disk space for output."""
