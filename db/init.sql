-- Enable pgvector extension
CREATE EXTENSION
IF NOT EXISTS vector;

-- Document metadata and extracted text
CREATE TABLE
IF NOT EXISTS documents
(
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    source          VARCHAR
(50) NOT NULL,
    source_path     TEXT NOT NULL,
    filename        TEXT NOT NULL,
    doc_type        VARCHAR
(30),
    page_count      INTEGER,
    extracted_text  TEXT,
    text_search     TSVECTOR GENERATED ALWAYS AS
(to_tsvector
('english', COALESCE
(extracted_text, ''))) STORED,
    metadata        JSONB DEFAULT '{}',
    source_url      TEXT,
    redaction_score FLOAT DEFAULT 0,
    redaction_details JSONB DEFAULT '{}',
    ocr_applied     BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR
(20) DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT NOW
(),
    updated_at      TIMESTAMPTZ DEFAULT NOW
()
);

CREATE INDEX
IF NOT EXISTS idx_documents_text_search ON documents USING GIN
(text_search);
CREATE INDEX
IF NOT EXISTS idx_documents_source ON documents
(source);
CREATE INDEX
IF NOT EXISTS idx_documents_type ON documents
(doc_type);
CREATE INDEX
IF NOT EXISTS idx_documents_status ON documents
(processing_status);
CREATE INDEX
IF NOT EXISTS idx_documents_metadata ON documents USING GIN
(metadata);

-- Named entities
CREATE TABLE
IF NOT EXISTS entities
(
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    name        TEXT NOT NULL,
    canonical   TEXT NOT NULL,
    entity_type VARCHAR
(20) NOT NULL,
    aliases     TEXT[] DEFAULT '{}',
    metadata    JSONB DEFAULT '{}',
    mention_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW
()
);

CREATE UNIQUE INDEX
IF NOT EXISTS idx_entities_canonical ON entities
(canonical, entity_type);

-- Entity mentions in documents
CREATE TABLE
IF NOT EXISTS entity_mentions
(
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    entity_id   UUID REFERENCES entities
(id) ON
DELETE CASCADE,
    document_id UUID
REFERENCES documents
(id) ON
DELETE CASCADE,
    page_number INTEGER,
    char_offset INTEGER,
    context     TEXT,
    confidence  FLOAT
DEFAULT 1.0
);

CREATE INDEX
IF NOT EXISTS idx_mentions_entity ON entity_mentions
(entity_id);
CREATE INDEX
IF NOT EXISTS idx_mentions_document ON entity_mentions
(document_id);

-- Relationships between entities
CREATE TABLE
IF NOT EXISTS relationships
(
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    entity_a_id     UUID REFERENCES entities
(id) ON
DELETE CASCADE,
    entity_b_id     UUID
REFERENCES entities
(id) ON
DELETE CASCADE,
    relationship_type VARCHAR(50),
    strength        FLOAT
DEFAULT 1.0,
    evidence_count  INTEGER DEFAULT 1,
    first_seen      TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX
IF NOT EXISTS idx_relationships_entities ON relationships
(entity_a_id, entity_b_id);

-- Document chunk embeddings
CREATE TABLE
IF NOT EXISTS embeddings
(
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    document_id UUID REFERENCES documents
(id) ON
DELETE CASCADE,
    chunk_index INTEGER,
    chunk_text  TEXT
NOT NULL,
    embedding   vector
(384) NOT NULL,
    metadata    JSONB DEFAULT '{}'
);

CREATE INDEX
IF NOT EXISTS idx_embeddings_vector ON embeddings USING hnsw
(embedding vector_cosine_ops);
CREATE INDEX
IF NOT EXISTS idx_embeddings_document ON embeddings
(document_id);

-- Processing jobs
CREATE TABLE
IF NOT EXISTS processing_jobs
(
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid
(),
    document_id UUID REFERENCES documents
(id) ON
DELETE CASCADE,
    job_type    VARCHAR(30)
NOT NULL,
    status      VARCHAR
(20) DEFAULT 'queued',
    priority    INTEGER DEFAULT 5,
    error       TEXT,
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW
()
);

CREATE INDEX
IF NOT EXISTS idx_jobs_status ON processing_jobs
(status);
CREATE INDEX
IF NOT EXISTS idx_jobs_document ON processing_jobs
(document_id);
