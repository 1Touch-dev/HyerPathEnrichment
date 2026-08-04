"""Pydantic schemas for document API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response from document upload endpoint."""

    job_id: str = Field(..., description="Job ID for status polling")
    document_id: str = Field(..., description="Document ID")
    message: str = Field(default="Document uploaded successfully")


class JobStatusResponse(BaseModel):
    """Job status polling response."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status: pending, processing, completed, failed")
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    document_id: str | None = Field(None, description="Document ID when available")
    result: dict[str, Any] | None = Field(None, description="Job result when completed")
    error: str | None = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Job last update timestamp")


class SearchRequest(BaseModel):
    """Request for semantic document search."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    filters: dict[str, Any] | None = Field(None, description="Optional filters")


class SearchResponse(BaseModel):
    """Response from document search endpoint."""

    results: list[SearchResult] = Field(..., description="Search results")


class SearchResult(BaseModel):
    """Single search result."""

    document_id: str = Field(..., description="Document UUID")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    cv_data: dict[str, Any] = Field(..., description="Structured CV data")
    excerpt: str = Field(..., description="Relevant text excerpt")


class CVDataResponse(BaseModel):
    """Structured CV data response."""

    document_id: str = Field(..., description="Document UUID")
    extracted_data: dict[str, Any] = Field(..., description="Structured CV data")
    raw_text: str | None = Field(None, description="Raw extracted text")
    processing_status: str = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Document creation timestamp")
    updated_at: datetime = Field(..., description="Document last update timestamp")


class DocumentMetadata(BaseModel):
    """Document metadata for listings."""

    document_id: str = Field(..., description="Document UUID")
    document_type: str = Field(..., description="Document type: cv, cover_letter")
    original_filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    processing_status: str = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Upload timestamp")


class DocumentDetailResponse(BaseModel):
    """Detailed document information."""

    document_id: str = Field(..., description="Document UUID")
    document_type: str = Field(..., description="Document type: cv, cover_letter")
    original_filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    processing_status: str = Field(..., description="Processing status")
    raw_text: str | None = Field(None, description="Extracted raw text")
    extracted_data: dict[str, Any] | None = Field(None, description="Structured data")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
