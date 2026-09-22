"""Minimal web application: database startup, API router, and frontend files."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import SessionLocal, engine, initialize_database, seed_database

    try:
        initialize_database()
        with SessionLocal() as db:
            seed_database(db)  # Existing seed marker means no changes. Never reset.
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Invoice Ledger", lifespan=lifespan)


@app.exception_handler(ValueError)
async def business_error(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Record conflicts with existing data or database constraints."})


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Database operation failed."})


app.include_router(router, prefix="/api")
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse("<h1>Invoice Ledger</h1><p>The frontend will be added here.</p>")
