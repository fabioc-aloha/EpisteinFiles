"""Network graph — D3 force-directed entity relationship visualization."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Entity, Relationship
from src.db.session import get_db

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
async def graph_page(request: Request):
    """Interactive network graph page."""
    templates = request.app.state.templates
    return templates.TemplateResponse("graph.html", {"request": request})


@router.get("/api/data")
async def graph_data(
    entity_id: UUID | None = Query(default=None, description="Center on entity"),
    min_strength: float = Query(default=2.0, description="Minimum relationship strength"),
    limit: int = Query(default=100, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Graph data as JSON for D3.js visualization."""
    query = select(Relationship).where(Relationship.strength >= min_strength)

    if entity_id:
        query = query.where(
            (Relationship.entity_a_id == entity_id) | (Relationship.entity_b_id == entity_id)
        )

    query = query.order_by(Relationship.strength.desc()).limit(limit)
    rels = (await db.execute(query)).scalars().all()

    # Collect entity IDs
    entity_ids = set()
    for r in rels:
        entity_ids.add(r.entity_a_id)
        entity_ids.add(r.entity_b_id)

    # Fetch entities
    entities = {}
    if entity_ids:
        e_query = select(Entity).where(Entity.id.in_(entity_ids))
        for e in (await db.execute(e_query)).scalars().all():
            entities[e.id] = e

    # Build D3 data
    nodes = [
        {
            "id": str(e.id),
            "name": e.canonical,
            "type": e.entity_type,
            "mentions": e.mention_count,
        }
        for e in entities.values()
    ]

    links = [
        {
            "source": str(r.entity_a_id),
            "target": str(r.entity_b_id),
            "type": r.relationship_type or "associated",
            "strength": r.strength,
            "evidence": r.evidence_count,
        }
        for r in rels
        if r.entity_a_id in entities and r.entity_b_id in entities
    ]

    return {"nodes": nodes, "links": links}
