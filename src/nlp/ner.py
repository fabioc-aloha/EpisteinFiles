"""Named Entity Recognition using spaCy."""

import logging
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document, Entity, EntityMention

logger = logging.getLogger(__name__)

# Lazy-loaded spaCy model
_nlp = None


def get_nlp():
    """Lazy-load the spaCy model."""
    global _nlp
    if _nlp is None:
        import spacy
        from src.config import get_settings

        settings = get_settings()
        _nlp = spacy.load(settings.spacy_model)
    return _nlp


# Entity types we care about
RELEVANT_TYPES = {"PERSON", "ORG", "GPE", "FAC", "NORP", "EVENT", "DATE"}

# Minimum entity name length
MIN_NAME_LENGTH = 2


def normalize_name(name: str) -> str:
    """Normalize an entity name to canonical form."""
    # Strip whitespace and common artifacts
    name = name.strip()
    # Remove leading/trailing punctuation
    name = name.strip(".,;:!?()[]{}\"'")
    # Collapse internal whitespace
    name = " ".join(name.split())
    return name


async def extract_entities(document_id: UUID, db: AsyncSession):
    """Job handler: extract named entities from document text using spaCy.

    Groups entities by canonical name, creates Entity and EntityMention records.
    """
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one()

    if not doc.extracted_text:
        logger.warning(f"Doc {document_id}: no extracted text, skipping NER")
        return

    nlp = get_nlp()

    # Process text in chunks (spaCy has limits on text size)
    text = doc.extracted_text
    max_len = nlp.max_length
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]

    # Collect all entity mentions
    entity_mentions = defaultdict(list)  # canonical -> list of (span_text, char_offset, context)

    offset = 0
    for chunk in chunks:
        spacy_doc = nlp(chunk)
        for ent in spacy_doc.ents:
            if ent.label_ not in RELEVANT_TYPES:
                continue
            name = normalize_name(ent.text)
            if len(name) < MIN_NAME_LENGTH:
                continue

            # Extract context (50 chars before and after)
            start = max(0, ent.start_char - 50)
            end = min(len(chunk), ent.end_char + 50)
            context = chunk[start:end]

            entity_mentions[(name, ent.label_)].append(
                {
                    "span_text": ent.text,
                    "char_offset": offset + ent.start_char,
                    "context": context,
                }
            )
        offset += len(chunk)

    # Create/update entity records
    for (canonical, entity_type), mentions in entity_mentions.items():
        # Find or create entity
        existing = (
            await db.execute(
                select(Entity).where(
                    Entity.canonical == canonical, Entity.entity_type == entity_type
                )
            )
        ).scalar_one_or_none()

        if existing:
            entity = existing
            entity.mention_count = (entity.mention_count or 0) + len(mentions)
        else:
            entity = Entity(
                name=canonical,
                canonical=canonical,
                entity_type=entity_type,
                mention_count=len(mentions),
            )
            db.add(entity)
            await db.flush()  # Get the ID

        # Create mention records
        for m in mentions:
            mention = EntityMention(
                entity_id=entity.id,
                document_id=document_id,
                char_offset=m["char_offset"],
                context=m["context"],
                confidence=1.0,
            )
            db.add(mention)

    await db.commit()
    logger.info(
        f"Doc {document_id}: extracted {len(entity_mentions)} unique entities, "
        f"{sum(len(m) for m in entity_mentions.values())} total mentions"
    )
