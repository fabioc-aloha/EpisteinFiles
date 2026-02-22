# Epstein Files Analyzer

Analytical semantic tool for canvassing the Epstein files — a web application that ingests, indexes, and enables deep analysis of the 1.4M+ document corpus released by the DOJ and other sources.

## Architecture

- **Backend**: FastAPI (Python 3.12) with Jinja2 templates + HTMX
- **Database**: PostgreSQL 16 + pgvector (full-text search + vector search)
- **NLP**: spaCy (NER), PyMuPDF (PDF extraction), Tesseract (OCR), sentence-transformers (embeddings)
- **Frontend**: Server-rendered HTML, HTMX for dynamic updates, D3.js for network graphs
- **Deployment**: Azure Container Apps under correax.com

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development without Docker)

### Run with Docker

```bash
# Clone and start
docker compose up --build

# Open http://localhost:8000
```

### Run locally (without Docker)

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .
python -m spacy download en_core_web_sm

# Start PostgreSQL (must have pgvector extension)
# Apply schema: psql -f db/init.sql

# Copy and edit environment
copy .env.example .env

# Run web server
python -m src.main

# Run worker (separate terminal)
python -m src.worker.main
```

## Project Structure

```
src/
├── app.py              # FastAPI application factory
├── main.py             # ASGI entry point (uvicorn)
├── config.py           # Environment-based configuration
├── db/
│   ├── models.py       # SQLAlchemy models (Document, Entity, etc.)
│   └── session.py      # Database session management
├── web/
│   ├── routes/         # FastAPI route handlers
│   │   ├── dashboard.py
│   │   ├── search.py
│   │   ├── documents.py
│   │   ├── entities.py
│   │   ├── graph.py
│   │   └── sources.py
│   ├── templates/      # Jinja2 HTML templates
│   └── static/         # CSS, JS, images
├── nlp/
│   ├── extractor.py    # PDF text extraction (PyMuPDF)
│   ├── ner.py          # Named entity recognition (spaCy)
│   ├── embedder.py     # Chunk embedding generation
│   └── redaction.py    # Redaction detection
├── ingest/
│   ├── jmail.py        # Jmail archive scraper
│   └── local.py        # Local directory importer
└── worker/
    └── main.py         # Background job processor
db/
└── init.sql            # PostgreSQL schema with pgvector
docs/
└── architecture-proposal.md
```

## Data Sources

| Source | Documents | Status |
|---|---|---|
| DOJ Epstein Files | 1,401,320 | Auth-gated |
| Jmail Archive | 1,412,250 | Public |
| House Oversight | 8,624 | Public |
| Court Records | 2,155 | Public |
| FBI Vault | TBD | Public |

## Pages

- **Dashboard** (`/`) — Corpus statistics, processing status
- **Search** (`/search`) — Full-text + semantic search with filters
- **Document Viewer** (`/docs/{id}`) — Read documents, see redactions, entity annotations
- **Entity Explorer** (`/entities`) — Browse people, organizations, places
- **Entity Profile** (`/entities/{id}`) — All mentions, connections, timeline
- **Network Graph** (`/graph`) — Interactive D3 force-directed relationship visualization
- **Sources** (`/sources`) — Data source status and ingestion progress

## License

MIT
