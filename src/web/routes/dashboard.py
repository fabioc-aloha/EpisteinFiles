"""Dashboard — home page with stats and processing status."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document, Entity, ProcessingJob, Relationship
from src.db.session import get_db

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard with corpus statistics."""
    templates = request.app.state.templates

    # Gather stats
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    entity_count = (await db.execute(select(func.count(Entity.id)))).scalar() or 0
    relationship_count = (await db.execute(select(func.count(Relationship.id)))).scalar() or 0

    # Processing status breakdown
    status_query = select(
        Document.processing_status, func.count(Document.id)
    ).group_by(Document.processing_status)
    status_rows = (await db.execute(status_query)).all()
    processing_stats = {row[0]: row[1] for row in status_rows}

    # Source breakdown
    source_query = select(Document.source, func.count(Document.id)).group_by(Document.source)
    source_rows = (await db.execute(source_query)).all()
    source_stats = {row[0]: row[1] for row in source_rows}

    # Recent documents
    recent_query = (
        select(Document)
        .order_by(Document.created_at.desc())
        .limit(10)
    )
    recent_docs = (await db.execute(recent_query)).scalars().all()

    # Active jobs
    jobs_query = (
        select(ProcessingJob)
        .where(ProcessingJob.status.in_(["queued", "running"]))
        .order_by(ProcessingJob.created_at.desc())
        .limit(20)
    )
    active_jobs = (await db.execute(jobs_query)).scalars().all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "doc_count": doc_count,
            "entity_count": entity_count,
            "relationship_count": relationship_count,
            "processing_stats": processing_stats,
            "source_stats": source_stats,
            "recent_docs": recent_docs,
            "active_jobs": active_jobs,
        },
    )
