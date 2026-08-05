"""Document storage service for CV and cover letter uploads.

Handles file uploads to R2 or local cache with deduplication and metadata tracking.
Reuses R2StorageClient pattern for consistent storage behavior.
"""

from __future__ import annotations

import hashlib
import logging
from uuid import uuid4

from app.storage.r2 import R2StorageClient

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


class DocumentStorageError(Exception):
    """Raised when document storage operations fail."""


def compute_file_hash(file_data: bytes) -> str:
    """Compute SHA256 hash of file data for deduplication."""
    return hashlib.sha256(file_data).hexdigest()


def validate_file_size(file_size: int) -> None:
    """Validate file size is within acceptable limits."""
    if file_size > MAX_FILE_SIZE_BYTES:
        raise DocumentStorageError(
            f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes"
        )


def validate_mime_type(mime_type: str) -> str:
    """Validate MIME type and return file extension."""
    normalized = mime_type.split(";")[0].strip().lower()
    if normalized not in ALLOWED_MIME_TYPES:
        raise DocumentStorageError(
            f"Unsupported file type: {normalized}. Allowed: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )
    return ALLOWED_MIME_TYPES[normalized]


def generate_storage_key(user_id: str, document_type: str, extension: str) -> str:
    """Generate unique storage key for document."""
    document_id = uuid4().hex[:12]
    return f"documents/{user_id}/{document_type}/{document_id}.{extension}"


class DocumentStorageClient:
    """Upload and manage candidate documents with security validation and deduplication."""

    def __init__(self) -> None:
        self._storage = R2StorageClient()

    async def upload_document(
        self,
        file_data: bytes,
        original_filename: str,
        mime_type: str,
        user_id: str,
        document_type: str,
    ) -> tuple[str, str, int]:
        """Upload document to storage with validation and deduplication.

        Args:
            file_data: Raw file bytes
            original_filename: Original filename from upload
            mime_type: MIME type from upload
            user_id: User ID uploading the document
            document_type: Type of document (cv, cover_letter)

        Returns:
            Tuple of (storage_path, file_hash, file_size_bytes)

        Raises:
            DocumentStorageError: If validation fails or upload fails
        """
        # Security validation
        file_size = len(file_data)
        validate_file_size(file_size)
        extension = validate_mime_type(mime_type)

        # Check for corrupted files (basic validation)
        if file_size < 100:
            raise DocumentStorageError("File appears to be corrupted or empty")

        # Compute hash for deduplication
        file_hash = compute_file_hash(file_data)

        # Generate storage key and upload
        storage_key = generate_storage_key(user_id, document_type, extension)

        try:
            await self._storage.upload_bytes(
                storage_key,
                file_data,
                content_type=mime_type,
            )
            logger.info(
                "Uploaded document",
                extra={
                    "user_id": user_id[:8],
                    "document_type": document_type,
                    "file_size": file_size,
                    "file_hash": file_hash[:12],
                    "storage_key": storage_key,
                },
            )
            return storage_key, file_hash, file_size
        except Exception as exc:
            logger.error(
                "Failed to upload document",
                exc_info=True,
                extra={
                    "user_id": user_id[:8],
                    "document_type": document_type,
                    "error": str(exc),
                },
            )
            raise DocumentStorageError(f"Upload failed: {exc}") from exc

    async def delete_document(self, storage_path: str) -> bool:
        """Delete document from storage.

        Args:
            storage_path: Storage path/key from upload

        Returns:
            True if deleted, False if not found
        """
        try:
            return await self._storage.delete_object(storage_path)
        except Exception as exc:
            logger.warning(
                "Failed to delete document",
                exc_info=True,
                extra={"storage_path": storage_path[:32], "error": str(exc)},
            )
            return False
