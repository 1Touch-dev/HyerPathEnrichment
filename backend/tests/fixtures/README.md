# Test Fixtures for Foundation Week 1

This directory contains sample documents for testing the document processing pipeline.

## Files

### PDF Files
- **sample_cv.pdf** - Standard 2-page resume with complete information
- **sample_cv_minimal.pdf** - Resume with ~70% completeness (missing fields)
- **malformed.pdf** - Corrupted PDF file for error handling tests

### DOCX Files
- **sample_cv.docx** - Word format resume for DOCX parser testing

## Usage in Tests

```python
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_pdf_parsing():
    pdf_path = FIXTURES_DIR / "sample_cv.pdf"
    result = document_processor.process(pdf_path)
    assert result["raw_text"]
```

## Creating Real Test Fixtures

To create actual test files, run:

```bash
# Generate sample PDFs using ReportLab or similar
python backend/tests/fixtures/generate_test_cvs.py
```

## Placeholder Files

For now, these are placeholder descriptions. Actual binary files will be created by:
- Agent 1 during document worker implementation
- Or manually before testing begins
