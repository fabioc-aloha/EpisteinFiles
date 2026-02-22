"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment / .env file."""

    # App
    app_name: str = "Epstein Files Analyzer"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/epstein"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/epstein"

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "documents"

    # Azure Queue Storage
    azure_queue_connection_string: str = ""
    azure_queue_name: str = "processing-jobs"

    # NLP
    spacy_model: str = "en_core_web_sm"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Processing
    chunk_size: int = 512  # tokens per embedding chunk
    chunk_overlap: int = 64
    max_concurrent_jobs: int = 4

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
