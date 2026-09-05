"""Generates a dummy CV PDF for manually testing the Documents module upload flow.

Not part of the application - a throwaway test fixture. Safe to delete after use.
Run: python scripts/generate_dummy_cv.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
    HRFlowable,
)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "dummy-cv.pdf"

styles = getSampleStyleSheet()

name_style = ParagraphStyle(
    "Name", parent=styles["Title"], fontSize=22, leading=26, spaceAfter=2
)
contact_style = ParagraphStyle(
    "Contact", parent=styles["Normal"], fontSize=9.5, textColor=colors.HexColor("#555555")
)
section_style = ParagraphStyle(
    "Section",
    parent=styles["Heading2"],
    fontSize=12,
    spaceBefore=14,
    spaceAfter=6,
    textColor=colors.HexColor("#1a1a2e"),
)
body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)
job_title_style = ParagraphStyle(
    "JobTitle", parent=styles["Normal"], fontSize=10.5, leading=14, spaceBefore=8
)
job_title_style.fontName = "Helvetica-Bold"


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        title="Jamie Rivera - CV",
    )

    story = []

    story.append(Paragraph("Jamie Rivera", name_style))
    story.append(
        Paragraph(
            "jamie.rivera.test@example.com &nbsp;|&nbsp; +1 (555) 019-2847 "
            "&nbsp;|&nbsp; Austin, TX &nbsp;|&nbsp; linkedin.com/in/jamierivera-test",
            contact_style,
        )
    )
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))

    story.append(Paragraph("SUMMARY", section_style))
    story.append(
        Paragraph(
            "Backend-leaning software engineer with 6 years of experience building "
            "async APIs, data pipelines, and internal tooling. Comfortable across "
            "Python, TypeScript, and Postgres, with a focus on shipping reliable "
            "systems and clean documentation. (This is a dummy CV generated for "
            "testing document upload/parsing.)",
            body_style,
        )
    )

    story.append(Paragraph("EXPERIENCE", section_style))

    story.append(Paragraph("Senior Backend Engineer &mdash; Northwind Data Co.", job_title_style))
    story.append(Paragraph("Austin, TX &nbsp;|&nbsp; Mar 2022 - Present", contact_style))
    story.append(
        ListFlowable(
            [
                ListItem(Paragraph(
                    "Designed and shipped an async document-processing pipeline "
                    "(FastAPI + RQ + Postgres) handling CV/resume ingestion, OCR, "
                    "and structured-data extraction for ~40k documents/month.",
                    body_style,
                )),
                ListItem(Paragraph(
                    "Cut p95 API latency by 38% by moving heavy enrichment work off "
                    "the request path and into background workers with SSE-based "
                    "status streaming to the frontend.",
                    body_style,
                )),
                ListItem(Paragraph(
                    "Mentored 2 junior engineers and led migration of a legacy "
                    "sync-only job queue to an async, retry-safe architecture.",
                    body_style,
                )),
            ],
            bulletType="bullet",
            leftIndent=14,
            spaceBefore=4,
            bulletFontSize=8,
        )
    )

    story.append(Paragraph("Software Engineer &mdash; Fenwick Analytics", job_title_style))
    story.append(Paragraph("Remote &nbsp;|&nbsp; Jul 2019 - Feb 2022", contact_style))
    story.append(
        ListFlowable(
            [
                ListItem(Paragraph(
                    "Built internal REST APIs and a React dashboard used by ~200 "
                    "analysts daily to review enrichment and matching results.",
                    body_style,
                )),
                ListItem(Paragraph(
                    "Implemented vector-similarity search over candidate documents "
                    "using embeddings, improving semantic search relevance.",
                    body_style,
                )),
            ],
            bulletType="bullet",
            leftIndent=14,
            spaceBefore=4,
            bulletFontSize=8,
        )
    )

    story.append(Paragraph("EDUCATION", section_style))
    story.append(Paragraph("B.S. in Computer Science &mdash; University of Texas at Austin", job_title_style))
    story.append(Paragraph("Graduated May 2019", contact_style))

    story.append(Paragraph("SKILLS", section_style))
    story.append(
        Paragraph(
            "Python, TypeScript/Next.js, FastAPI, PostgreSQL, Redis/RQ, SQLAlchemy, "
            "React Query, Docker, pytest/vitest, REST &amp; async API design.",
            body_style,
        )
    )

    doc.build(story)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
