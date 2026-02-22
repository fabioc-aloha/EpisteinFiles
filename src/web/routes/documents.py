"""Document viewer — read documents, see redactions, entity annotations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Document, EntityMention
from src.db.session import get_db

router = APIRouter(prefix="/docs", tags=["documents"])


@router.get("/{doc_id}")
async def document_detail(
    request: Request,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """View a single document with annotations."""
    templates = request.app.state.templates

    query = (
        select(Document)
        .where(Document.id == doc_id)
        .options(selectinload(Document.mentions).selectinload(EntityMention.entity))
    )
    doc = (await db.execute(query)).scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return templates.TemplateResponse(
        "document.html",
        {
            "request": request,
            "doc": doc,
            "mentions": doc.mentions,
        },
    )
