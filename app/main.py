"""
app/main.py
-----------
FastAPI application factory.

Owns:
  - App instantiation with metadata.
  - Lifespan context: validates all required env vars at startup so the
    server crashes immediately with a clear error rather than at request time.
  - CORS middleware.
  - Global exception handler for unhandled errors.
  - Health check endpoint.
  - Router mounting under /api/v1.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup validation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs before the server starts accepting requests.

    Calling `get_settings()` here triggers pydantic-settings validation.
    If any required env var is missing, the server fails fast with a
    `ValidationError` that names the exact missing field.
    """
    settings = get_settings()   # Raises ValidationError on bad config
    logger.info("✅  Configuration validated — model: %s", settings.GEMINI_MODEL)
    logger.info("🚀  AI Coding Assistant API is ready to serve requests.")
    yield
    logger.info("🛑  AI Coding Assistant API is shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.APP_TITLE,
        description=(
            "A production-ready microservice that exposes six Gemini-powered "
            "endpoints for code generation, explanation, complexity analysis, "
            "rubber-duck debugging, language conversion, and docstring generation.\n\n"
            "**All prompts are environment-driven** — zero hardcoded strings in Python.\n\n"
            "Explore the interactive docs below, or visit `/redoc` for the ReDoc UI."
        ),
        version=settings.APP_VERSION,
        contact={
            "name": "AI Coding Assistant",
            "url": "https://github.com/your-org/ai-coding-assistant",
        },
        license_info={"name": "MIT"},
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # -----------------------------------------------------------------------
    # CORS — open for development.
    # In production: replace ["*"] with your real frontend origin(s).
    # -----------------------------------------------------------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Global exception handler — catch anything not already handled
    # -----------------------------------------------------------------------
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected internal server error occurred.",
                "type": type(exc).__name__,
            },
        )

    # -----------------------------------------------------------------------
    # Health check — useful for container liveness probes
    # -----------------------------------------------------------------------
    @application.get(
        "/health",
        tags=["Health"],
        summary="Liveness / health check",
        response_description="Service is running",
    )
    async def health():
        """Returns `200 OK` when the service is running and configured."""
        return {
            "status": "ok",
            "service": settings.APP_TITLE,
            "version": settings.APP_VERSION,
        }

    # -----------------------------------------------------------------------
    # Mount all AI route endpoints under /api/v1
    # -----------------------------------------------------------------------
    application.include_router(router, prefix="/api/v1")

    return application


app = create_app()
