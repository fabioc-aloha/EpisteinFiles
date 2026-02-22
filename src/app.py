"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    settings = get_settings()
    # Startup
    from src.db.session import init_db

    await init_db()
    yield
    # Shutdown
    from src.db.session import close_db

    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Static files
    static_dir = Path(__file__).parent / "web" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Templates
    templates_dir = Path(__file__).parent / "web" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    app.state.templates = Jinja2Templates(directory=str(templates_dir))

    # Register routes
    from src.web.routes import dashboard, documents, entities, graph, search, sources

    app.include_router(dashboard.router)
    app.include_router(search.router)
    app.include_router(documents.router)
    app.include_router(entities.router)
    app.include_router(graph.router)
    app.include_router(sources.router)

    return app
