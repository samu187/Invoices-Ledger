"""Explicit PostgreSQL configuration and schema initialization; no import-time I/O."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.models import Base


class DatabaseConfigurationError(ValueError):
    """Missing or unsupported database configuration."""


def database_url() -> URL:
    # Resolve the backend .env independently of the terminal working directory.
    # Explicit environment variables (e.g. Railway) always win.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseConfigurationError("Set DATABASE_URL in your environment or project .env file.")
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise DatabaseConfigurationError("DATABASE_URL is not a valid PostgreSQL connection URL.") from None
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise DatabaseConfigurationError("DATABASE_URL must use PostgreSQL (postgresql+psycopg://).")
    if not url.host or not url.database:
        raise DatabaseConfigurationError("DATABASE_URL must include a database host and database name.")
    return url.set(drivername="postgresql+psycopg")


def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_session(engine: Engine) -> Session:
    """Caller owns the transaction; use `with get_session(engine) as session`."""
    return Session(engine)


def initialize_database(engine: Engine) -> None:
    """Create missing tables atomically, preserving existing tables and rows."""
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
