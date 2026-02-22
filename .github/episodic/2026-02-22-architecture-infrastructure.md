# Meditation: Epstein Files Platform — Architecture & Infrastructure Session
**Date**: 2026-02-22
**Type**: Topic Deep-Dive
**Duration**: ~15 minutes

## Focus
Reflecting on the first major session of the Epstein Files analytical platform — from research through scaffolding to Azure infrastructure provisioning.

## Key Learnings

1. **Semantic Index Over External Corpus** (→ stored in global knowledge GI-semantic-index-over-external-corpus-patt-2026-02-22)
   - When analyzing large public datasets you don't own, build a semantic layer with source_url references instead of mirroring raw files
   - Eliminates storage tier, reduces legal concerns, cuts costs significantly
   - Tradeoff: dependency on external source availability

2. **Azure PostgreSQL pgvector Provisioning Friction** (→ stored in global knowledge GI-azure-postgresql-pgvector-provisioning-f-2026-02-22)
   - Flexible Server has undocumented region restrictions (eastus, eastus2 both blocked)
   - Cosmos DB for PostgreSQL doesn't expose azure.extensions via CLI — Portal manual step required
   - Lesson: test provisioning first before committing architecture

3. **NLP Pipeline Design Rationale** (→ project-specific, preserved in codebase)
   - Stream-extract-discard: no raw PDF storage
   - Quoted-printable artifact cleaning: handles government email-to-PDF conversion
   - Redaction detection via PDF drawing inspection: catches faulty redactions
   - FOR UPDATE SKIP LOCKED: concurrent job safety without double-processing

## Updates Made
- Global insight: Semantic Index Over External Corpus Pattern
- Global insight: Azure PostgreSQL pgvector Provisioning Friction
- Session record: this file

## Open Questions
- Will Cosmos DB for PostgreSQL's Citus extensions cause any SQL compatibility issues with our SQLAlchemy models? (Entity table uses UNIQUE index that may need Citus distribution column consideration)
- Should we add a local SQLite fallback for development without Azure PostgreSQL?
- At what ingestion volume does the single-coordinator Burstable node become a bottleneck? (1 vCore, 32GB)
- The DOJ 401 auth gate — is this temporary rate limiting or permanent? Need to retest periodically.

## Infrastructure State
| Resource | Status |
|----------|--------|
| rg-epstein-files | ✅ Ready |
| log-epstein-files | ✅ Ready |
| cae-epstein-files | ✅ Ready |
| psql-epstein-files | ⚠️ Needs Portal pgvector step |
| Blob Storage | ❌ Eliminated (architecture pivot) |
| Container App | ⏳ Not yet deployed |
