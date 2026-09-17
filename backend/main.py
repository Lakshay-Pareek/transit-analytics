"""
FastAPI application entry point for the
Public Transport Feedback & Service Analytics Platform.
"""
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import engine, Base
from backend.routers import analytics, classify, feedback, routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Create tables
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Transit Analytics Platform",
    description=(
        "Public Transport Feedback & Service Analytics Platform. "
        "Passengers submit ratings; administrators analyse complaints by route, "
        "time, category and severity."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Allow the frontend (served from any origin in dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(routes.router)
app.include_router(feedback.router)
app.include_router(analytics.router)
app.include_router(classify.router)

# Serve the frontend static assets and pages
import os
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    # Mount CSS, JS, and any sub-folders explicitly so they work
    # whether the page is served from / or /admin
    css_dir = os.path.join(frontend_dir, "css")
    js_dir  = os.path.join(frontend_dir, "js")
    if os.path.isdir(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.isdir(js_dir):
        app.mount("/js",  StaticFiles(directory=js_dir),  name="js")
    # Serve index page images / extra assets if any
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    def serve_passenger_portal():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/admin", include_in_schema=False)
    def serve_admin_dashboard():
        return FileResponse(os.path.join(frontend_dir, "admin.html"))


# ---------------------------------------------------------------------------
# Startup: run data ingestion in background thread
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Transit Analytics Platform starting up…")

    def ingest():
        try:
            from backend.data_ingestion import run_ingestion
            run_ingestion()
        except Exception as exc:
            logger.error(f"Data ingestion failed: {exc}")

    # Run ingestion in a background thread so it doesn't block startup
    thread = threading.Thread(target=ingest, daemon=True)
    thread.start()
