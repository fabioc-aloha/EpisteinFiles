"""ASGI entry point for uvicorn."""

from src.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    from src.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
