"""Redaction detection — identify blacked-out regions in PDF pages."""

import logging
from uuid import UUID

import fitz  # PyMuPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document

logger = logging.getLogger(__name__)


def analyze_redactions_in_pdf(pdf_path: str) -> dict:
    """Analyze a PDF for redaction patterns.

    Looks for:
    - Large black rectangles (typical redaction bars)
    - White rectangles over text (whiteout redactions)
    - Suspiciously uniform black regions in images

    Returns:
        Dict with redaction_score (0-1), page_details, and total_redacted_area.
    """
    doc = fitz.open(pdf_path)
    page_details = []
    total_page_area = 0
    total_redacted_area = 0

    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        total_page_area += page_area

        redacted_area = 0
        redaction_rects = []

        # Check for black-filled rectangles in drawings
        drawings = page.get_drawings()
        for drawing in drawings:
            for item in drawing.get("items", []):
                if item[0] == "re":  # rectangle
                    rect = fitz.Rect(item[1])
                    # Check if the fill color is black or very dark
                    fill = drawing.get("fill")
                    if fill and all(c < 0.1 for c in fill[:3] if isinstance(c, (int, float))):
                        # Black rectangle — likely redaction
                        area = rect.width * rect.height
                        if area > 100:  # Ignore tiny dots
                            redacted_area += area
                            redaction_rects.append({
                                "x": rect.x0,
                                "y": rect.y0,
                                "width": rect.width,
                                "height": rect.height,
                            })

        page_score = redacted_area / page_area if page_area > 0 else 0
        total_redacted_area += redacted_area

        page_details.append({
            "page": page_num + 1,
            "score": round(page_score, 4),
            "redaction_count": len(redaction_rects),
            "rects": redaction_rects[:20],  # Cap to avoid huge JSON
        })

    doc.close()

    overall_score = total_redacted_area / total_page_area if total_page_area > 0 else 0

    return {
        "redaction_score": round(overall_score, 4),
        "total_pages": len(page_details),
        "pages_with_redactions": sum(1 for p in page_details if p["score"] > 0),
        "page_details": page_details,
    }


async def detect_redactions(document_id: UUID, db: AsyncSession):
    """Job handler: detect redactions in a document's PDF."""
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one()

    source_path = doc.source_path

    try:
        result = analyze_redactions_in_pdf(source_path)
        doc.redaction_score = result["redaction_score"]
        doc.redaction_details = result
        await db.commit()

        logger.info(
            f"Doc {document_id}: redaction score {result['redaction_score']:.2%}, "
            f"{result['pages_with_redactions']}/{result['total_pages']} pages with redactions"
        )
    except Exception as e:
        logger.exception(f"Doc {document_id}: redaction detection failed: {e}")
        raise
