"""Local file importer — bulk import PDFs from a local directory."""

import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document, ProcessingJob

logger = logging.getLogger(__name__)

# Source detection by path patterns
SOURCE_PATTERNS = {
    "doj": ["doj", "dataset", "justice.gov", "efta"],
    "court": ["court", "filing", "deposition", "indictment"],
    "oversight": ["oversight", "house", "committee"],
    "estate": ["estate"],
    "fbi": ["fbi", "vault"],
}


def detect_source(path: str) -> str:
    """Guess document source from file path."""
    path_lower = path.lower()
    for source, keywords in SOURCE_PATTERNS.items():
        if any(kw in path_lower for kw in keywords):
            return source
    return "unknown"


def detect_doc_type(filename: str) -> str:
    """Guess document type from filename."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    elif lower.endswith((".jpg", ".jpeg", ".png", ".tiff", ".bmp")):
        return "image"
    elif lower.endswith((".mp4", ".avi", ".mov")):
        return "video"
    elif lower.endswith(".txt"):
        return "text"
    return "unknown"


async def import_directory(
    directory: str,
    db: AsyncSession,
    source: str | None = None,
    recursive: bool = True,
) -> int:
    """Import all supported files from a local directory.

    Creates Document records and queues processing jobs.
    Returns the number of documents imported.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    extensions = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".txt"}
    pattern = "**/*" if recursive else "*"
    files = [
        f for f in dir_path.glob(pattern) if f.is_file() and f.suffix.lower() in extensions
    ]

    imported = 0
    for file_path in files:
        file_source = source or detect_source(str(file_path))
        doc_type = detect_doc_type(file_path.name)

        doc = Document(
            source=file_source,
            source_path=str(file_path),
            filename=file_path.name,
            doc_type=doc_type,
            processing_status="pending",
        )
        db.add(doc)
        await db.flush()

        # Queue processing jobs
        job_types = ["extract_text"]
        if doc_type == "pdf":
            job_types.append("detect_redaction")

        for i, job_type in enumerate(job_types):
            job = ProcessingJob(
                document_id=doc.id,
                job_type=job_type,
                priority=5 + i,  # Text extraction first, then redaction
            )
            db.add(job)

        imported += 1

        # Batch commit every 100 documents
        if imported % 100 == 0:
            await db.commit()
            logger.info(f"Imported {imported} documents...")

    await db.commit()
    logger.info(f"Import complete: {imported} documents from {directory}")
    return imported
