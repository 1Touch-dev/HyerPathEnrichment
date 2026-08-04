"""Document processing service for PDF and DOCX extraction.

Extracts text content from candidate documents with layout preservation
and token counting. Validates file integrity and handles corrupted files.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Raised when document processing fails."""


class DocumentProcessor:
    """Process PDF and DOCX documents with text extraction and validation."""

    def __init__(self) -> None:
        """Initialize document processor with lazy imports."""
        self._fitz = None  # PyMuPDF
        self._docx = None  # python-docx
        self._tiktoken = None

    def _import_fitz(self) -> Any:
        """Lazy import PyMuPDF for PDF processing."""
        if self._fitz is None:
            try:
                import fitz  # PyMuPDF

                self._fitz = fitz
            except ImportError as exc:
                raise DocumentProcessingError(
                    "PyMuPDF not installed. Install with: pip install PyMuPDF"
                ) from exc
        return self._fitz

    def _import_docx(self) -> Any:
        """Lazy import python-docx for DOCX processing."""
        if self._docx is None:
            try:
                import docx

                self._docx = docx
            except ImportError as exc:
                raise DocumentProcessingError(
                    "python-docx not installed. Install with: pip install python-docx"
                ) from exc
        return self._docx

    def _import_tiktoken(self) -> Any:
        """Lazy import tiktoken for token counting."""
        if self._tiktoken is None:
            try:
                import tiktoken

                self._tiktoken = tiktoken
            except ImportError as exc:
                raise DocumentProcessingError(
                    "tiktoken not installed. Install with: pip install tiktoken"
                ) from exc
        return self._tiktoken

    def extract_pdf_text(self, file_data: bytes) -> dict[str, Any]:
        """Extract text from PDF file with layout preservation.

        Args:
            file_data: Raw PDF bytes

        Returns:
            Dict with keys:
                - text: Extracted text content
                - page_count: Number of pages
                - metadata: PDF metadata (author, title, etc)
                - token_count: Approximate token count

        Raises:
            DocumentProcessingError: If PDF is corrupted or cannot be processed
        """
        fitz = self._import_fitz()
        tiktoken = self._import_tiktoken()

        try:
            # Open PDF from bytes
            doc = fitz.open(stream=file_data, filetype="pdf")

            if doc.page_count == 0:
                raise DocumentProcessingError("PDF has no pages")

            # Extract text from all pages with layout preservation
            text_parts = []
            for page_num in range(doc.page_count):
                page = doc[page_num]
                # Use layout mode to preserve formatting
                page_text = page.get_text("text", sort=True)
                if page_text.strip():
                    text_parts.append(page_text)

            full_text = "\n\n".join(text_parts)

            if not full_text.strip():
                raise DocumentProcessingError("PDF contains no extractable text")

            # Extract metadata before closing
            page_count = doc.page_count
            metadata = {
                "author": doc.metadata.get("author", ""),
                "title": doc.metadata.get("title", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
            }

            # Close document
            doc.close()

            # Count tokens (using cl100k_base encoding - GPT-3.5/GPT-4)
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(full_text))

            return {
                "text": full_text,
                "page_count": page_count,
                "metadata": metadata,
                "token_count": token_count,
            }

        except DocumentProcessingError:
            raise
        except Exception as exc:
            logger.error("PDF processing failed", exc_info=True)
            raise DocumentProcessingError(f"Failed to process PDF: {exc}") from exc

    def extract_docx_text(self, file_data: bytes) -> dict[str, Any]:
        """Extract text from DOCX file with layout preservation.

        Args:
            file_data: Raw DOCX bytes

        Returns:
            Dict with keys:
                - text: Extracted text content
                - paragraph_count: Number of paragraphs
                - metadata: Document metadata
                - token_count: Approximate token count

        Raises:
            DocumentProcessingError: If DOCX is corrupted or cannot be processed
        """
        docx = self._import_docx()
        tiktoken = self._import_tiktoken()

        try:
            # Open DOCX from bytes
            doc = docx.Document(BytesIO(file_data))

            # Extract text from paragraphs
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            if not paragraphs:
                raise DocumentProcessingError("DOCX contains no text")

            full_text = "\n\n".join(paragraphs)

            # Extract metadata from core properties
            metadata = {
                "author": doc.core_properties.author or "",
                "title": doc.core_properties.title or "",
                "subject": doc.core_properties.subject or "",
                "created": str(doc.core_properties.created) if doc.core_properties.created else "",
            }

            # Count tokens
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(full_text))

            return {
                "text": full_text,
                "paragraph_count": len(paragraphs),
                "metadata": metadata,
                "token_count": token_count,
            }

        except DocumentProcessingError:
            raise
        except Exception as exc:
            logger.error("DOCX processing failed", exc_info=True)
            raise DocumentProcessingError(f"Failed to process DOCX: {exc}") from exc

    def process_document(
        self,
        file_data: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        """Process document and extract text based on MIME type.

        Args:
            file_data: Raw file bytes
            mime_type: MIME type of file

        Returns:
            Extraction results dict with text, metadata, etc

        Raises:
            DocumentProcessingError: If processing fails or unsupported type
        """
        normalized_type = mime_type.split(";")[0].strip().lower()

        if normalized_type == "application/pdf":
            return self.extract_pdf_text(file_data)
        elif (
            normalized_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return self.extract_docx_text(file_data)
        else:
            raise DocumentProcessingError(f"Unsupported MIME type: {normalized_type}")
