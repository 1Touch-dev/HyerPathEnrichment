"""Magic-byte sniffing for uploaded documents (do not trust client Content-Type)."""

from __future__ import annotations

import zipfile
from io import BytesIO

# OLE Compound File (legacy .doc)
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_DOC = "application/msword"


def sniff_document_mime(data: bytes) -> str | None:
    """Return a canonical document MIME from magic bytes, or None if unknown."""
    if not data:
        return None
    if data.startswith(b"%PDF"):
        return MIME_PDF
    if data.startswith(_OLE_MAGIC):
        return MIME_DOC
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                names = {name.replace("\\", "/") for name in zf.namelist()}
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names and any(name.startswith("word/") for name in names):
            return MIME_DOCX
    return None


def claimed_mime_matches_bytes(claimed_mime: str | None, data: bytes) -> bool:
    """True when sniffed type equals the client-declared MIME (both required)."""
    if not claimed_mime:
        return False
    sniffed = sniff_document_mime(data)
    return sniffed is not None and sniffed == claimed_mime
