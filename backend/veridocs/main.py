"""
Main FastAPI application entry point for VeriDocs.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from veridocs.api.routes.health import router as health_router
from veridocs.config.settings import settings
from veridocs.utils.logging import correlation_id_ctx, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle handler."""
    logger.info("Initializing VeriDocs engine...")
    settings.ensure_directories()
    logger.info(f"Storage paths validated: {settings.data_dir}, {settings.cache_dir}")
    yield
    logger.info("VeriDocs engine shutdown complete.")


app = FastAPI(
    title="VeriDocs API",
    description="Grounded Financial Intelligence Engine for SEC 10-K/10-Q Filings",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware for local React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Assign or extract request correlation ID and log request timing."""
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    token = correlation_id_ctx.set(cid)
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.2f}ms)")
        return response
    finally:
        correlation_id_ctx.reset(token)


# Include health and status routes
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "service": "VeriDocs API",
        "status": "operational",
        "docs_url": "/docs",
    }
