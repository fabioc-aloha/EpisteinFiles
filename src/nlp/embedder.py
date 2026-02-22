"""Document chunk embedding generation using sentence-transformers."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document, Embedding

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from src.config import get_settings

        settings = get_settings()
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


async def generate_embeddings(document_id: UUID, db: AsyncSession):
    """Job handler: generate embeddings for document text chunks.

    Splits text into overlapping chunks, generates embeddings, stores in DB.
    """
    from src.config import get_settings

    settings = get_settings()

    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one()

    if not doc.extracted_text:
        logger.warning(f"Doc {document_id}: no extracted text, skipping embeddings")
        return

    # Delete existing embeddings for this document (re-processing)
    existing = await db.execute(
        select(Embedding).where(Embedding.document_id == document_id)
    )
    for emb in existing.scalars().all():
        await db.delete(emb)

    # Chunk the text
    chunks = chunk_text(doc.extracted_text, settings.chunk_size, settings.chunk_overlap)

    if not chunks:
        logger.warning(f"Doc {document_id}: no chunks generated")
        return

    # Generate embeddings
    model = get_model()
    vectors = model.encode(chunks, show_progress_bar=False, batch_size=32)

    # Store in database
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        embedding = Embedding(
            document_id=document_id,
            chunk_index=i,
            chunk_text=chunk,
            embedding=vector.tolist(),
        )
        db.add(embedding)

    await db.commit()
    logger.info(f"Doc {document_id}: generated {len(chunks)} embeddings")
