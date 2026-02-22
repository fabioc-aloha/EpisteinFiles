"""Entity explorer — browse people, orgs, places."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Entity, EntityMention, Relationship
from src.db.session import get_db

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("")
async def entity_list(
    request: Request,
    entity_type: str = Query(default="", description="Filter by entity type"),
    q: str = Query(default="", description="Name search"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Browse all entities with filters."""
    templates = request.app.state.templates

    query = select(Entity)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if q:
        query = query.where(Entity.canonical.ilike(f"%{q}%"))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch sorted by mention count
    query = query.order_by(Entity.mention_count.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    entities = (await db.execute(query)).scalars().all()

    # Entity types for filter
    type_query = select(Entity.entity_type).distinct()
    entity_types = (await db.execute(type_query)).scalars().all()

    return templates.TemplateResponse(
        "entities.html",
        {
            "request": request,
            "entities": entities,
            "total": total,
            "entity_type": entity_type,
            "q": q,
            "page": page,
            "per_page": per_page,
            "entity_types": entity_types,
        },
    )


@router.get("/{entity_id}")
async def entity_profile(
    request: Request,
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Entity profile with all document mentions and connections."""
    templates = request.app.state.templates

    entity = (
        await db.execute(
            select(Entity)
            .where(Entity.id == entity_id)
            .options(selectinload(Entity.mentions).selectinload(EntityMention.document))
        )
    ).scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Connections
    connections_query = (
        select(Relationship)
        .where(
            (Relationship.entity_a_id == entity_id) | (Relationship.entity_b_id == entity_id)
        )
        .order_by(Relationship.strength.desc())
        .limit(50)
    )
    connections = (await db.execute(connections_query)).scalars().all()

    # Load connected entities
    connected_ids = set()
    for conn in connections:
        connected_ids.add(
            conn.entity_b_id if conn.entity_a_id == entity_id else conn.entity_a_id
        )
    connected_entities = {}
    if connected_ids:
        ce_query = select(Entity).where(Entity.id.in_(connected_ids))
        for e in (await db.execute(ce_query)).scalars().all():
            connected_entities[e.id] = e

    return templates.TemplateResponse(
        "entity_profile.html",
        {
            "request": request,
            "entity": entity,
            "mentions": entity.mentions[:100],  # Limit for page load
            "connections": connections,
            "connected_entities": connected_entities,
        },
    )
