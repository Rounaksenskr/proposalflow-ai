import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from proposal_bot.db.session import init_db
from proposal_bot.api.routes import router, conn

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables and verify storage
    logger.info("[Lifecycle] Starting ProposalFlow AI service...")
    init_db()
    logger.info("[Lifecycle] Relational database initialized.")
    yield
    # Shutdown: Cleanly close SQLite checkpointer connection
    logger.info("[Lifecycle] Shutting down ProposalFlow AI service...")
    try:
        conn.close()
        logger.info("[Lifecycle] SQLite checkpointer connection closed cleanly.")
    except Exception as exc:
        logger.warning("[Lifecycle] Error closing SQLite connection: %s", exc)


app = FastAPI(
    title="ProposalFlow AI — Agentic Automation System",
    description="Automated freelance lead-to-proposal system with reflection and human-in-the-loop sign-off.",
    version="1.0.0",
    lifespan=lifespan,
)

# Explicit allowed origins (avoids the forbidden wildcard + allow_credentials=True failure)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint for monitoring and uptime probes."""
    return {
        "status": "ok",
        "service": "ProposalFlow AI",
        "version": "1.0.0",
        "checkpointer": "sqlite_wal",
    }