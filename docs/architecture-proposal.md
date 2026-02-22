# Epstein Files Analyzer — Architecture Proposal

## Project Summary

A web application deployed to Azure under **correax.com** that ingests, stores, and semantically analyzes the Epstein files corpus (1.4M+ documents, 2.4M pages, 1M+ emails, 300GB+ raw data).

---

## Dataset Profile

| Metric | Value |
|---|---|
| Total files | 1,412,250 |
| Total pages | 2,474,242 |
| Total emails | 1,038,603 |
| DOJ documents | 1,401,320 |
| House Oversight docs | 8,624 |
| Court records | 2,155 |
| DOJ disclosures | 57 |
| Estate production | 92 |
| Raw data size (est.) | 300GB+ (PDFs, images, videos) |
| Extracted text (est.) | 15-30GB |
| Key people tracked | 12+ high-profile, 1000s+ minor |

### Data Sources

| Source | URL | Status |
|---|---|---|
| DOJ Epstein files | justice.gov/epstein | Auth-gated (401) |
| Jmail archive | jmail.world | Public, browsable |
| DocumentCloud (Black Books) | documentcloud.org | Public PDFs |
| House Oversight Committee | oversight.house.gov | Public releases |
| FBI Vault | vault.fbi.gov/jeffrey-epstein | Public |
| Zeteo searchable DB | zeteo.com | Searchable 26K docs |
| Courier Newsroom DB | couriernewsroom.com | Searchable 20K estate docs |

---

## Decision 1: Compute & Hosting

### Option A: Azure Container Apps + FastAPI ⭐ RECOMMENDED

```
┌─────────────────────────────────────────────────┐
│  Azure Container Apps Environment               │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Web App      │  │  Worker (PDF/NLP jobs)  │  │
│  │  FastAPI      │  │  Celery / ARQ           │  │
│  │  Port 8000    │  │  Background processing  │  │
│  └──────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

| Aspect | Detail |
|---|---|
| **Cost** | ~$30-80/mo (scales to zero when idle) |
| **Scaling** | Auto-scale 0→N replicas based on HTTP load or queue depth |
| **Processing** | Separate worker container for heavy PDF/OCR/NLP jobs |
| **Deployment** | Docker containers via `az containerapp up` or GitHub Actions |
| **Custom domain** | Full support for correax.com with managed TLS |
| **Pros** | Best price-to-performance; scale-to-zero cuts idle costs; container isolation lets us install Tesseract, spaCy models; separate worker for heavy processing |
| **Cons** | Slightly more complex initial setup than App Service |

### Option B: Azure App Service + FastAPI

| Aspect | Detail |
|---|---|
| **Cost** | ~$15-55/mo (B1-S1 plans; no scale-to-zero on basic) |
| **Scaling** | Manual or auto-scale 1→N instances |
| **Processing** | WebJobs for background tasks, or pair with Azure Functions |
| **Deployment** | `az webapp up`, GitHub Actions, or ZIP deploy |
| **Custom domain** | Full support with managed certificates |
| **Pros** | Simplest PaaS deployment; built-in monitoring, slots, backups |
| **Cons** | Always-on cost even when idle; custom system deps (Tesseract) require custom container anyway; limited control over runtime |

### Option C: Azure Static Web Apps + Functions

| Aspect | Detail |
|---|---|
| **Cost** | ~$0-9/mo for frontend + Functions consumption |
| **Scaling** | Serverless auto-scale |
| **Processing** | Cold starts; 10-minute execution timeout on Consumption plan |
| **Pros** | Cheapest; great for simple apps |
| **Cons** | **Totally inadequate** for this workload — 300GB corpus processing, NLP pipelines, and long-running PDF jobs exceed Function limits. No persistent state in memory. Would need Durable Functions for orchestration, adding complexity without benefit |

### Verdict: **Azure Container Apps** (Option A)

The separate worker container is essential for processing millions of PDFs without blocking the web UI. Scale-to-zero minimizes cost when the site isn't actively being used.

---

## Decision 2: Database & Storage

Given the requirement to store the entire dataset in a database, here's the breakdown:

### Storage Layer: Azure Blob Storage (raw files) — Non-negotiable

Raw PDFs, images, and videos **must** go to Blob Storage regardless of DB choice. 300GB+ of binary files don't belong in any database.

- **Cost**: ~$6/mo for 300GB on Cool tier, ~$15/mo on Hot
- **Access**: Direct URL access, SAS tokens, CDN integration
- **Structure**: Container per source (doj/, court-records/, estate/, oversight/)

### Option A: Azure Database for PostgreSQL + pgvector ⭐ RECOMMENDED

```
┌───────────────────────────────────────────────────────────────┐
│  PostgreSQL 16 (Flexible Server)                              │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐│
│  │  documents    │ │  entities    │ │  embeddings (pgvector) ││
│  │  - id         │ │  - id        │ │  - doc_id              ││
│  │  - source     │ │  - name      │ │  - chunk_text          ││
│  │  - text       │ │  - type      │ │  - embedding vec(1536) ││
│  │  - metadata   │ │  - mentions  │ │  - metadata            ││
│  │  - redactions │ │  - relations │ └────────────────────────┘│
│  └──────────────┘ └──────────────┘                            │
│  Full-text search (tsvector) + Vector search (pgvector)       │
└───────────────────────────────────────────────────────────────┘
```

| Aspect | Detail |
|---|---|
| **Cost** | ~$30-50/mo (Burstable B1ms, 32GB storage) |
| **Full-text search** | Built-in tsvector/tsquery with ranking — excellent for document search |
| **Vector search** | pgvector extension for semantic/embedding search |
| **Scale** | Handles millions of rows easily; can scale up to 64 vCores |
| **Pros** | **Single database for everything**: relational data, full-text search, AND vector search. Joins across entities/documents are trivial. JSONB for flexible metadata. Mature, battle-tested. Cheapest combined solution. Azure-native with backups, HA, geo-replication |
| **Cons** | Vector search performance at 1M+ embeddings requires tuning (IVFFlat/HNSW indexes). Not as feature-rich as dedicated search services |

### Option B: Azure Cosmos DB (NoSQL)

| Aspect | Detail |
|---|---|
| **Cost** | ~$25/mo (1000 RU/s serverless) — **but scales unpredictably with heavy queries** |
| **Full-text search** | Limited. Would need Azure AI Search alongside it |
| **Vector search** | Built-in vector search (DiskANN) — excellent performance |
| **Pros** | Global distribution, guaranteed latency, flexible schema |
| **Cons** | **RU cost model is dangerous** for this workload — full-text search across millions of documents burns RUs fast. No SQL joins for relationship queries. Would need Cosmos DB + AI Search = two services to manage and pay for |

### Option C: Azure AI Search (standalone)

| Aspect | Detail |
|---|---|
| **Cost** | ~$75/mo (Basic tier, 15GB index) or ~$250/mo (Standard, 50GB) |
| **Full-text search** | World-class: BM25, facets, filters, suggestions, highlighting |
| **Vector search** | Built-in hybrid search (keyword + vector) |
| **Pros** | Best search experience by far. Faceted navigation, hit highlighting, "more like this". Purpose-built for exactly this use case |
| **Cons** | **Expensive** for the full corpus. Basic tier only supports 15GB index (~500K documents?). Standard tier at $250/mo is significant. Not a relational database — still need a DB for entity relationships, graph data |

### Option D: SQLite + ChromaDB (self-hosted in container)

| Aspect | Detail |
|---|---|
| **Cost** | $0 (bundled in app container) |
| **Full-text search** | SQLite FTS5 — fast, capable, but no ranking sophistication |
| **Vector search** | ChromaDB — good for dev, questionable at 1M+ docs in a container |
| **Pros** | Zero additional cost; zero external dependencies; works offline |
| **Cons** | **Not production-grade for this scale**. Container restarts lose ChromaDB data unless volume-mounted. No replication, no backups, no HA. SQLite write contention under concurrent users |

### Hybrid Recommendation: **PostgreSQL + Azure AI Search** (if budget allows) or **PostgreSQL alone** (MVP)

**MVP Path** (Phase 1): PostgreSQL with pgvector handles everything — relational data, full-text search, and vector search. Single bill, single connection string, simple ops.

**Scale Path** (Phase 2): Add Azure AI Search for superior search UX (facets, suggestions, highlighting) while keeping PostgreSQL as the system of record for entities, relationships, and graph data.

---

## Decision 3: Frontend Architecture

### Option A: FastAPI + Jinja2 + HTMX ⭐ RECOMMENDED

```
Browser ←→ FastAPI (server-rendered HTML)
             │
             ├── Jinja2 templates (pages)
             ├── HTMX (dynamic updates without JS framework)
             ├── Alpine.js (minimal client-side interactivity)
             └── D3.js (relationship graph visualization)
```

| Aspect | Detail |
|---|---|
| **Build complexity** | None — no npm, no webpack, no node_modules |
| **Performance** | Fast initial load; server does the rendering |
| **SEO** | Fully server-rendered = perfect indexability |
| **Interactivity** | HTMX handles search-as-you-type, infinite scroll, tab switching. Alpine.js for dropdowns/modals. D3.js for the network graph |
| **Development speed** | Fastest to build. Templates live alongside Python code |
| **Pros** | **Fastest path to a working product**. No separate frontend build. HTMX gives 90% of SPA feel with 10% of SPA complexity. Hot reload with FastAPI. Tailwind CSS via CDN for styling |
| **Cons** | Complex client-side state management (e.g., multi-filter search with graph interactions) can get awkward. No component reusability like React |

### Option B: React SPA + FastAPI API

```
Browser ←→ React (Vite) SPA ←→ FastAPI REST API
              │
              ├── React Query (data fetching)
              ├── React Router (navigation)
              ├── Tailwind CSS (styling)
              ├── React Force Graph (network visualization)
              └── ag-Grid (document tables)
```

| Aspect | Detail |
|---|---|
| **Build complexity** | Medium — Vite + npm, separate dev server |
| **Performance** | Client-side rendering; needs loading states everywhere |
| **Interactivity** | Full client-side state management; best for complex interactions |
| **Pros** | Rich component ecosystem (ag-Grid for huge tables, React Force Graph for networks). Better for complex multi-panel layouts. Easier to add features later |
| **Cons** | **Doubles development time**. Separate build pipeline. CORS configuration. Two things to deploy (SPA to Blob/CDN, API to Container Apps). More code to maintain |

### Option C: Next.js + Python API

| Aspect | Detail |
|---|---|
| **Build complexity** | High — Node.js server + Python API, two runtimes |
| **Pros** | SSR + client hydration. Good DX with file-based routing |
| **Cons** | **Worst of both worlds** for this project. Two runtime environments to maintain. Python API still needed for NLP. Next.js server is redundant overhead when FastAPI already serves HTML |

### Verdict: **FastAPI + Jinja2 + HTMX** (Option A)

For an analytical tool focused on search, document reading, and relationship exploration, server-rendered HTML with HTMX partial updates is the sweet spot. The only complex client-side component (the relationship graph) uses D3.js directly. If the UI needs evolve significantly, migrating specific pages to React components is always possible later.

---

## Recommended Architecture

```
                        ┌──────────────────────┐
                        │    correax.com        │
                        │   (Azure DNS / CDN)   │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Azure Container Apps Env    │
                    │                              │
                    │  ┌────────────────────────┐  │
                    │  │  web (FastAPI + HTMX)  │  │
                    │  │  - Search UI           │  │
                    │  │  - Document viewer     │  │
                    │  │  - Entity explorer     │  │
                    │  │  - Network graph       │  │
                    │  │  - Redaction analyzer  │  │
                    │  └───────────┬────────────┘  │
                    │              │                │
                    │  ┌───────────▼────────────┐  │
                    │  │  worker (processing)   │  │
                    │  │  - PDF text extraction │  │
                    │  │  - OCR (Tesseract)     │  │
                    │  │  - NER (spaCy)         │  │
                    │  │  - Embedding gen       │  │
                    │  │  - Redaction detection │  │
                    │  └───────────┬────────────┘  │
                    └──────────────┼───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
    ┌─────────▼──────────┐ ┌──────▼──────────┐ ┌───────▼────────┐
    │  Azure PostgreSQL   │ │  Azure Blob     │ │  Azure Queue   │
    │  (Flexible Server)  │ │  Storage        │ │  Storage       │
    │                     │ │                 │ │                │
    │  - documents table  │ │  - Raw PDFs     │ │  - Job queue   │
    │  - entities table   │ │  - Images       │ │  - Processing  │
    │  - relationships    │ │  - Videos       │ │    tasks       │
    │  - embeddings       │ │  - Thumbnails   │ │                │
    │    (pgvector)       │ │                 │ │                │
    │  - full-text index  │ │  Containers:    │ └────────────────┘
    │    (tsvector)       │ │  /doj           │
    │                     │ │  /court-records │
    └─────────────────────┘ │  /estate        │
                            │  /oversight     │
                            │  /fbi-vault     │
                            └─────────────────┘
```

### Cost Estimate (Monthly)

| Service | Tier | Est. Cost |
|---|---|---|
| Container Apps (web) | 0.5 vCPU, 1GB RAM | $15-20 |
| Container Apps (worker) | 1 vCPU, 2GB RAM (scales to 0) | $10-30 |
| PostgreSQL Flexible | Burstable B1ms, 64GB | $35-50 |
| Blob Storage | Hot, 300GB + transactions | $15-20 |
| Queue Storage | Transactions only | $1-2 |
| **Total MVP** | | **$76-122/mo** |
| + Azure AI Search (Phase 2) | Basic, 15GB index | +$75 |

### Technology Stack

| Layer | Technology | Why |
|---|---|---|
| **Language** | Python 3.12 | Best NLP ecosystem (spaCy, transformers, PyMuPDF) |
| **Web framework** | FastAPI | Async, fast, auto-docs, type-safe |
| **Templates** | Jinja2 + HTMX + Alpine.js | Server-rendered with dynamic updates |
| **Styling** | Tailwind CSS (CDN) | Rapid, consistent UI |
| **Graphs** | D3.js force-directed | Interactive relationship networks |
| **PDF extraction** | PyMuPDF (fitz) | Fast, pure-Python, text + image extraction |
| **OCR** | Tesseract (pytesseract) | Open-source, handles scanned docs |
| **NER** | spaCy (en_core_web_trf) | PERSON, ORG, GPE, DATE extraction |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Fast, 384-dim, good quality |
| **Database** | PostgreSQL 16 + pgvector | Relational + full-text + vector search |
| **Blob storage** | Azure Blob Storage | Raw file storage |
| **Queue** | Azure Queue Storage | Job orchestration |
| **Container** | Docker + Azure Container Apps | Deployment |

---

## Data Model

### Core Tables

```sql
-- Document metadata and extracted text
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          VARCHAR(50) NOT NULL,      -- 'doj', 'court', 'estate', 'oversight', 'fbi'
    source_path     TEXT NOT NULL,              -- original path/URL
    filename        TEXT NOT NULL,
    doc_type        VARCHAR(30),               -- 'email', 'pdf', 'image', 'video', 'transcript'
    page_count      INTEGER,
    extracted_text  TEXT,                       -- full extracted text
    text_search     TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', COALESCE(extracted_text, ''))) STORED,
    metadata        JSONB DEFAULT '{}',        -- flexible: dates, subjects, from/to, etc.
    blob_url        TEXT,                       -- Azure Blob Storage URL
    thumbnail_url   TEXT,
    redaction_score FLOAT DEFAULT 0,           -- 0-1, how redacted the doc is
    redaction_details JSONB DEFAULT '{}',      -- page-by-page redaction info
    ocr_applied     BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_text_search ON documents USING GIN (text_search);
CREATE INDEX idx_documents_source ON documents (source);
CREATE INDEX idx_documents_type ON documents (doc_type);
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);

-- Named entities extracted from documents
CREATE TABLE entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    canonical   TEXT NOT NULL,                 -- normalized name (e.g., "Donald Trump" for all variants)
    entity_type VARCHAR(20) NOT NULL,          -- PERSON, ORG, GPE, DATE, MONEY, FAC
    aliases     TEXT[] DEFAULT '{}',
    metadata    JSONB DEFAULT '{}',            -- role, title, known info
    mention_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_entities_canonical ON entities (canonical, entity_type);

-- Entity mentions in documents (many-to-many with context)
CREATE TABLE entity_mentions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id   UUID REFERENCES entities(id),
    document_id UUID REFERENCES documents(id),
    page_number INTEGER,
    char_offset INTEGER,
    context     TEXT,                          -- surrounding text snippet
    confidence  FLOAT DEFAULT 1.0
);

CREATE INDEX idx_mentions_entity ON entity_mentions (entity_id);
CREATE INDEX idx_mentions_document ON entity_mentions (document_id);

-- Relationships between entities
CREATE TABLE relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_a_id     UUID REFERENCES entities(id),
    entity_b_id     UUID REFERENCES entities(id),
    relationship    VARCHAR(50),               -- 'communicated_with', 'employed_by', 'traveled_with', etc.
    strength        FLOAT DEFAULT 1.0,         -- co-occurrence weight
    evidence_count  INTEGER DEFAULT 1,
    first_seen      DATE,
    last_seen       DATE,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_relationships_entities ON relationships (entity_a_id, entity_b_id);

-- Document chunk embeddings for semantic search
CREATE TABLE embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    chunk_index INTEGER,
    chunk_text  TEXT NOT NULL,
    embedding   vector(384) NOT NULL,          -- all-MiniLM-L6-v2 output
    metadata    JSONB DEFAULT '{}'
);

CREATE INDEX idx_embeddings_vector ON embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_embeddings_document ON embeddings (document_id);

-- Processing job queue (supplement to Azure Queue)
CREATE TABLE processing_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    job_type    VARCHAR(30) NOT NULL,          -- 'extract_text', 'ocr', 'ner', 'embed', 'detect_redaction'
    status      VARCHAR(20) DEFAULT 'queued',  -- queued, running, completed, failed
    priority    INTEGER DEFAULT 5,
    error       TEXT,
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Processing Pipeline

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐
│ Ingest   │───→│ Extract Text │───→│ Detect       │───→│ Extract      │───→│ Generate  │
│ Document │    │ (PyMuPDF)    │    │ Redactions   │    │ Entities     │    │ Embeddings│
│          │    │ + OCR if     │    │ (black box   │    │ (spaCy NER)  │    │ (sentence │
│ → Blob   │    │   needed     │    │  detection)  │    │              │    │  transf.) │
│ → Queue  │    │              │    │              │    │ → entities   │    │           │
│          │    │ → documents  │    │ → redaction  │    │ → mentions   │    │ → embeds  │
│          │    │   .text      │    │   _score     │    │ → relations  │    │   table   │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘
```

Each stage is a separate job type, allowing:
- **Retry on failure** at any stage
- **Parallel processing** across documents
- **Incremental updates** (add new docs without reprocessing all)

---

## Web Application Pages

| Page | URL | Description |
|---|---|---|
| **Dashboard** | `/` | Stats, recent docs, processing status |
| **Search** | `/search` | Full-text + semantic search with filters |
| **Document Viewer** | `/docs/{id}` | Read document, see redactions highlighted, entities annotated |
| **Entity Explorer** | `/entities` | Browse all people, orgs, places; click to see all mentions |
| **Entity Profile** | `/entities/{id}` | All docs mentioning thisEntity, timeline, connections |
| **Network Graph** | `/graph` | Interactive D3 force-directed graph of entity relationships |
| **Redaction Analyzer** | `/redactions` | Documents sorted by redaction density; patterns in what's hidden |
| **Timeline** | `/timeline` | Chronological view of events, documents, relationships |
| **Sources** | `/sources` | Data source status, ingestion progress, statistics |

---

## Deployment

```yaml
# docker-compose.yml (local development)
services:
  web:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, worker]

  worker:
    build: .
    command: python -m src.worker
    depends_on: [db]

  db:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
```

```bash
# Azure deployment
az containerapp env create --name epstein-env --resource-group epstein-rg
az containerapp create --name web --image epstein-web:latest --target-port 8000
az containerapp create --name worker --image epstein-worker:latest
az postgres flexible-server create --name epstein-db --sku-name Standard_B1ms
```

---

## Phase Plan

### Phase 1: Foundation (MVP)
- [x] Architecture design
- [ ] Project scaffolding (FastAPI + Docker)
- [ ] PostgreSQL schema + pgvector
- [ ] Document ingestion from Jmail/public sources
- [ ] PDF text extraction pipeline
- [ ] Basic full-text search UI
- [ ] Docker Compose for local dev
- [ ] Azure Container Apps deployment

### Phase 2: Intelligence
- [ ] spaCy NER pipeline (people, places, orgs, dates)
- [ ] Redaction detection (black-box pixel analysis)
- [ ] Entity resolution (merge variants: "G. Maxwell" = "Ghislaine Maxwell")
- [ ] Relationship inference from co-occurrence
- [ ] Semantic search with embeddings

### Phase 3: Visualization
- [ ] Interactive network graph (D3.js force-directed)
- [ ] Timeline view
- [ ] Redaction pattern analysis
- [ ] Entity profile pages with document cross-references

### Phase 4: Scale & Polish
- [ ] Azure AI Search integration (facets, suggestions)
- [ ] Batch processing optimization
- [ ] CDN for document thumbnails
- [ ] User annotations and bookmarks
- [ ] Export capabilities (CSV, PDF reports)

---

## Next Step

Approve this architecture and I'll start building Phase 1 — the project scaffolding, database schema, web app skeleton, and document ingestion pipeline.
