"""Search — full-text and semantic search across the corpus."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document
from src.db.session import get_db

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_page(
    request: Request,
    q: str = Query(default="", description="Search query"),
    source: str = Query(default="", description="Filter by source"),
    doc_type: str = Query(default="", description="Filter by document type"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search with filters."""
    templates = request.app.state.templates

    results = []
    total = 0
    search_time_ms = 0

    if q:
        import time

        start = time.monotonic()

        # PostgreSQL full-text search
        ts_query = func.plainto_tsquery("english", q)
        search_filter = text("text_search @@ plainto_tsquery('english', :query)").bindparams(
            query=q
        )

        query = select(Document).where(search_filter)

        # Apply filters
        if source:
            query = query.where(Document.source == source)
        if doc_type:
            query = query.where(Document.doc_type == doc_type)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        # Fetch page
        query = query.order_by(Document.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        results = (await db.execute(query)).scalars().all()

        search_time_ms = round((time.monotonic() - start) * 1000, 1)

    # Get filter options
    sources = (
        (await db.execute(select(Document.source).distinct())).scalars().all()
    )
    doc_types = (
        (await db.execute(select(Document.doc_type).distinct().where(Document.doc_type.isnot(None))))
        .scalars()
        .all()
    )

    is_htmx = request.headers.get("HX-Request") == "true"
    template = "search_results.html" if is_htmx else "search.html"

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "q": q,
            "source": source,
            "doc_type": doc_type,
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
            "search_time_ms": search_time_ms,
            "sources": sources,
            "doc_types": doc_types,
        },
    )
