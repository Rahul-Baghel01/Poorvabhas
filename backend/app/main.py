import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import get_settings, validate_production_settings
from app.db import check_db
from app.routers import admin, analytics, auth, imports, reports, review

log = logging.getLogger("poorvabhas")

# Fail fast (before serving anything) if production is configured with a published secret.
validate_production_settings(get_settings())


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if not os.environ.get("VERCEL"):
        from app.nlp.normalize import sentence_segments

        sentence_segments("Warm-up sentence. Loads the spaCy sentencizer once.")
    if s.auto_seed and not os.environ.get("VERCEL"):
        try:
            from app.seed.seed import seed_all

            seed_all(verbose=True)
        except Exception as e:  # database may not be up yet; /api/health reports it
            log.error("Startup seed failed: %s", e)
    yield


app = FastAPI(title="Poorvabhas API", version="1.0.0", description="SIF-precursor decision support. Demo environment - synthetic safety data.", lifespan=lifespan)
if not os.environ.get("VERCEL"):
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(OperationalError)
async def db_down(_: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "Database connection unavailable"})


@app.get("/api/health")
def health():
    s = get_settings()
    ok = check_db()
    body = {"status": "ok" if ok else "degraded", "database": "up" if ok else "unavailable", "environment": s.environment, "demo_mode": s.demo_mode}
    return JSONResponse(status_code=200 if ok else 503, content=body)


for r in (auth.router, reports.router, review.router, analytics.router, imports.router, admin.router):
    app.include_router(r)
