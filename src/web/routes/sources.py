"""Sources — data source status and ingestion progress."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document, ProcessingJob
from src.db.session import get_db

router = APIRouter(prefix="/sources", tags=["sources"])

# Known data sources
DATA_SOURCES = [
    {
        "name": "DOJ Epstein Files",
        "key": "doj",
        "url": "https://www.justice.gov/epstein",
        "total_docs": 1_401_320,
        "description": "Department of Justice released documents",
    },
    {
        "name": "House Oversight Committee",
        "key": "oversight",
        "url": "https://oversight.house.gov",
        "total_docs": 8_624,
        "description": "Congressional oversight releases",
    },
    {
        "name": "Court Records",
        "key": "court",
        "url": "https://www.documentcloud.org",
        "total_docs": 2_155,
        "description": "Court filings, depositions, and legal documents",
    },
    {
        "name": "FBI Vault",
        "key": "fbi",
        "url": "https://vault.fbi.gov/jeffrey-epstein",
        "total_docs": None,
        "description": "FBI FOIA releases",
    },
    {
        "name": "Estate Production",
        "key": "estate",
        "url": "https://couriernewsroom.com",
        "total_docs": 92,
        "description": "Documents from Epstein estate proceedings",
    },
]


@router.get("")
async def sources_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Data source status overview."""
    templates = request.app.state.templates

    # Ingested counts per source
    ingested_query = select(
        Document.source, func.count(Document.id)
    ).group_by(Document.source)
    ingested_rows = (await db.execute(ingested_query)).all()
    ingested = {row[0]: row[1] for row in ingested_rows}

    # Processing status per source
    status_query = select(
        Document.source,
        Document.processing_status,
        func.count(Document.id),
    ).group_by(Document.source, Document.processing_status)
    status_rows = (await db.execute(status_query)).all()
    status_by_source = {}
    for source, status, count in status_rows:
        if source not in status_by_source:
            status_by_source[source] = {}
        status_by_source[source][status] = count

    # Enrich sources with live data
    sources = []
    for src in DATA_SOURCES:
        src_data = {
            **src,
            "ingested": ingested.get(src["key"], 0),
            "statuses": status_by_source.get(src["key"], {}),
        }
        sources.append(src_data)

    return templates.TemplateResponse(
        "sources.html",
        {"request": request, "sources": sources},
    )
