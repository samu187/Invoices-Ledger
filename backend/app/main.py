"""Web application: authentication, database startup, API, and frontend files."""

import base64
import binascii
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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


@app.middleware("http")
async def require_admin(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    expected_username = os.getenv("ADMIN_USERNAME")
    expected_password = os.getenv("ADMIN_PASSWORD")
    if not expected_username or not expected_password:
        return JSONResponse(status_code=503, content={"detail": "Application login is not configured."})

    scheme = ""
    try:
        scheme, encoded = request.headers["Authorization"].split(" ", 1)
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (KeyError, ValueError, UnicodeDecodeError, binascii.Error):
        username = password = ""

    valid_username = secrets.compare_digest(username.encode(), expected_username.encode())
    valid_password = secrets.compare_digest(password.encode(), expected_password.encode())
    if scheme.lower() != "basic" or not (valid_username and valid_password):
        return Response(
            content="Authentication required",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Invoice Ledger"'},
        )

    return await call_next(request)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


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
