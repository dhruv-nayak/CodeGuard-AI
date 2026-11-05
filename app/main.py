import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.auth_routes import router as auth_router
from app.api.collaboration_routes import router as collaboration_router
from app.api.github_routes import router as github_router
from app.api.routes import router
from app.api.security_routes import router as security_router
from app.core.config import csv_env, validate_runtime_config
from app.core.middleware import SecurityAndRateLimitMiddleware
from app.db.database import SessionLocal, engine, init_db
from app.services.auth_service import seed_admin

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger("codeguard.startup")

    try:
        logger.info("Validating runtime configuration")
        validate_runtime_config()

        logger.info("Starting database migrations")
        init_db()

        logger.info("Database migrations completed successfully")

        with SessionLocal() as db:
            logger.info("Seeding administrator")
            seed_admin(db)

        logger.info("Application startup completed")

    except Exception:
        logger.exception("APPLICATION STARTUP FAILED")
        raise

    yield

app = FastAPI(
    title="CodeGuard AI",
    description="AI-assisted code review, GitHub collaboration and review history platform.",
    version="0.8.0",
    docs_url=None if ENVIRONMENT == "production" else "/docs",
    redoc_url=None if ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if ENVIRONMENT == "production" else "/openapi.json",
    lifespan=lifespan,
)

origins = csv_env("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
trusted_hosts = csv_env("TRUSTED_HOSTS")
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
app.add_middleware(
    SecurityAndRateLimitMiddleware,
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")),
    auth_requests_per_minute=int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "30")),
    max_body_bytes=int(os.getenv("MAX_REQUEST_BODY_BYTES", "1000000")),
    enable_hsts=os.getenv("ENABLE_HSTS", "false").lower() in {"true", "1", "yes"},
)


@app.get("/api/v1/health/live", tags=["operations"])
async def liveness():
    return {"status": "ok", "service": "CodeGuard AI", "version": "0.8.0"}


@app.get("/api/v1/health/ready", tags=["operations"])
async def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse({"status": "not_ready", "database": "unavailable"}, status_code=503)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(collaboration_router, prefix="/api/v1")
app.include_router(github_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
