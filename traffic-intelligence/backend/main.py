"""
FastAPI application entrypoint for the Traffic Intelligence backend.

Start locally:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Or via Docker Compose (see docker-compose.yml).
"""
import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.traffic import router as traffic_router
from backend.api.routes  import router as routes_router

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)

APP_VERSION = "1.0.0"
_START_TIME = time.time()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Traffic Intelligence API",
    description=(
        "Real-Time Traffic Congestion Monitoring and Alternative Route Recommendation System.\n\n"
        "**Note:** GPS and sensor data are simulated for demonstration purposes."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(traffic_router)
app.include_router(routes_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"], summary="Health check")
async def health():
    """Returns application health and uptime."""
    return {
        "status":          "ok",
        "version":         APP_VERSION,
        "uptime_seconds":  round(time.time() - _START_TIME, 1),
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["System"], summary="API root")
async def root():
    return {
        "message": "Traffic Intelligence API",
        "docs":    "/docs",
        "health":  "/api/health",
    }
