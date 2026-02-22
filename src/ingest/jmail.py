"""Jmail archive scraper — index and download from jmail.world."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

JMAIL_BASE = "https://jmail.world"
JMAIL_DRIVE = f"{JMAIL_BASE}/drive"


@dataclass
class JmailDocument:
    """A document entry from the Jmail archive."""

    efta_id: str
    filename: str
    source: str  # 'doj', 'oversight', 'court', etc.
    dataset: str  # Dataset number
    url: str
    page_count: int | None = None


async def fetch_document_index(
    client: httpx.AsyncClient,
    dataset: str = "1",
    offset: int = 0,
    limit: int = 100,
) -> list[dict]:
    """Fetch document index from Jmail API.

    Note: This is a placeholder — the actual Jmail API structure
    needs to be discovered by inspecting their frontend requests.
    """
    # Try the browsable interface
    url = f"{JMAIL_DRIVE}"
    try:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text  # Parse HTML to extract document links
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch Jmail index: {e}")
        return []


async def download_document(
    client: httpx.AsyncClient,
    doc_url: str,
    output_path: str,
) -> bool:
    """Download a single document from Jmail or DOJ."""
    try:
        async with client.stream("GET", doc_url, timeout=60) as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
        return True
    except httpx.HTTPError as e:
        logger.error(f"Failed to download {doc_url}: {e}")
        return False
