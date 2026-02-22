"""PDF text extraction using PyMuPDF."""

import logging
from uuid import UUID

import fitz  # PyMuPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document

logger = logging.getLogger(__name__)


def extract_text_pymupdf(pdf_path: str) -> tuple[str, int]:
    """Extract text from a PDF file using PyMuPDF.

    Returns:
        Tuple of (extracted_text, page_count)
    """
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)
    page_count = len(doc)
    doc.close()
    return "\n\n--- PAGE BREAK ---\n\n".join(pages), page_count


def extract_text_from_bytes(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text from PDF bytes in memory."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)
    page_count = len(doc)
    doc.close()
    return "\n\n--- PAGE BREAK ---\n\n".join(pages), page_count


def clean_extracted_text(text: str) -> str:
    """Clean common artifacts from PDF-to-text conversion.

    - Remove =XX hex encoding artifacts from email-to-PDF conversions
    - Normalize whitespace
    - Remove null bytes
    """
    import re

    # Remove quoted-printable artifacts (=XX hex patterns)
    text = re.sub(r"=([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), text)
    # Remove soft line breaks from quoted-printable
    text = text.replace("=\n", "")
    # Remove null bytes
    text = text.replace("\x00", "")
    # Normalize excessive whitespace but preserve paragraph structure
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


async def extract_text_from_pdf(document_id: UUID, db: AsyncSession):
    """Job handler: extract text from a document's PDF.

    Downloads from blob storage (or local path), extracts text,
    updates the document record.
    """
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one()

    # For now, try local file path. Later: download from Azure Blob.
    source_path = doc.source_path

    try:
        text, page_count = extract_text_pymupdf(source_path)
        text = clean_extracted_text(text)

        doc.extracted_text = text
        doc.page_count = page_count
        doc.processing_status = "text_extracted"

        # Check if OCR is needed (very little text extracted despite having pages)
        chars_per_page = len(text) / max(page_count, 1)
        if chars_per_page < 50 and page_count > 0:
            doc.ocr_applied = False  # Flag for OCR job
            logger.info(f"Doc {document_id}: low text density ({chars_per_page:.0f} chars/page), needs OCR")

        await db.commit()
        logger.info(f"Doc {document_id}: extracted {len(text)} chars from {page_count} pages")

    except Exception as e:
        doc.processing_status = "failed"
        await db.commit()
        raise
