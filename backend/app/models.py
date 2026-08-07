"""SQLAlchemy models for the interview question bank.

Defines database models for:
- InterviewQuestion: Question bank with filtering and rotation
- InterviewAttempt: User attempts for recency tracking
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class InterviewQuestion(Base):
    """Interview question with metadata for smart selection."""

    __tablename__ = "interview_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    question_text = Column(Text, nullable=False)
    question_category = Column(String(50), nullable=False)  # behavioral, technical, system_design
    difficulty = Column(String(20), nullable=False)  # easy, medium, hard

    # For PostgreSQL: use ARRAY, for SQLite: use Text with JSON
    job_roles = Column(ARRAY(String), nullable=False)  # PostgreSQL
    technologies = Column(ARRAY(String), nullable=False)  # PostgreSQL

    sample_answer = Column(Text, nullable=True)
    scoring_rubric = Column(JSONB, nullable=True)  # PostgreSQL: JSONB, SQLite: Text
    source = Column(String(100), nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<InterviewQuestion(id={self.id}, category={self.question_category}, difficulty={self.difficulty})>"


class InterviewAttempt(Base):
    """Tracks user attempts to avoid repeating recent questions."""

    __tablename__ = "interview_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)  # Foreign key not enforced for now
    question_id = Column(UUID(as_uuid=True), ForeignKey("interview_questions.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<InterviewAttempt(id={self.id}, user_id={self.user_id}, question_id={self.question_id})>"
