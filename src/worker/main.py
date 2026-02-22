"""Background worker — polls for processing jobs and executes them."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Document, ProcessingJob
from src.db.session import get_db, init_db
from src.nlp.extractor import extract_text_from_pdf
from src.nlp.ner import extract_entities
from src.nlp.embedder import generate_embeddings
from src.nlp.redaction import detect_redactions

logger = logging.getLogger(__name__)

# Job handlers
JOB_HANDLERS = {
    "extract_text": extract_text_from_pdf,
    "ner": extract_entities,
    "embed": generate_embeddings,
    "detect_redaction": detect_redactions,
}


async def process_job(job: ProcessingJob, db: AsyncSession):
    """Execute a single processing job."""
    handler = JOB_HANDLERS.get(job.job_type)
    if not handler:
        logger.error(f"Unknown job type: {job.job_type}")
        return

    # Mark running
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        await handler(job.document_id, db)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        logger.info(f"Job {job.id} ({job.job_type}) completed for doc {job.document_id}")
    except Exception as e:
        job.status = "failed"
        job.error = str(e)[:500]
        job.completed_at = datetime.now(timezone.utc)
        logger.exception(f"Job {job.id} ({job.job_type}) failed: {e}")

    await db.commit()


async def worker_loop():
    """Main worker loop — poll for queued jobs."""
    settings = get_settings()
    await init_db()

    logger.info(f"Worker started (max concurrent: {settings.max_concurrent_jobs})")

    while True:
        try:
            async for db in get_db():
                # Fetch next queued job
                query = (
                    select(ProcessingJob)
                    .where(ProcessingJob.status == "queued")
                    .order_by(ProcessingJob.priority.asc(), ProcessingJob.created_at.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                job = (await db.execute(query)).scalar_one_or_none()

                if job:
                    await process_job(job, db)
                else:
                    # No jobs — sleep
                    await asyncio.sleep(5)

        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(10)


def main():
    """Entry point for the worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
