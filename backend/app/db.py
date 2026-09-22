"""Database connection, sessions, and explicit table creation."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert

from app.models import Base, Company, Account, Supplier, JournalEntry, JournalLine, SeedRun

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "")

try:
    url = make_url(DATABASE_URL)
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"} or not url.host or not url.database:
        raise ValueError
except (ArgumentError, ValueError):
    raise ValueError("Set DATABASE_URL to a valid PostgreSQL URL with host and database name.") from None

engine = create_engine(
    url.set(drivername="postgresql+psycopg"),
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Provide a session to future FastAPI routes."""
    with SessionLocal() as db:
        yield db


def initialize_database():
    """Create missing tables without deleting data or seeding."""
    with engine.begin() as connection:
        Base.metadata.create_all(connection)


def seed_database(db: Session, reset: bool = False) -> bool:
    """Seed once, optionally clearing all application rows in the same transaction."""
    with db.begin():
        if reset:
            # Delete children before parents to respect foreign keys.
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())

        # Reserving the marker in the same transaction also makes repeat runs safe.
        marker = db.execute(
            insert(SeedRun).values(name="reference_data_v1")
            .on_conflict_do_nothing(index_elements=[SeedRun.name])
            .returning(SeedRun.name)
        ).scalar_one_or_none()
        if marker is None:
            return False

        company = db.get(Company, 1)
        if company is None:
            company = Company(id=1, name="Northbridge Demo Ltd", base_currency="GBP")
            db.add(company)
            db.flush()
        elif company.base_currency != "GBP":
            raise ValueError("The demo seed requires company 1 to use GBP.")

        accounts = {}
        for code, name, account_type in [
            ("1000", "HSBC GBP", "asset"),
            ("1100", "Input VAT", "asset"),
            ("2000", "Accounts payable", "liability"),
            ("3000", "Opening equity", "equity"),
            ("4900", "Realised FX gains", "income"),
            ("5000", "General expenses", "expense"),
            ("5100", "Cost of goods sold", "expense"),
            ("5200", "Bank fees", "expense"),
            ("5300", "Office supplies", "expense"),
            ("5400", "Software licenses", "expense"),
            ("5500", "Services", "expense"),
            ("5900", "Realised FX losses", "expense"),
        ]:
            
            account = db.scalar(select(Account).where(Account.code == code))
            if account is None:
                account = Account(company_id=1, code=code, name=name, account_type=account_type)
                db.add(account)
            elif account.company_id != 1 or account.account_type != account_type:
                raise ValueError(f"Account {code} conflicts with the demo chart of accounts.")
            accounts[code] = account
        db.flush()

        for name in ["Acme Office Supplies", "Alpine Design Studio", "Hudson Software"]:
            existing = db.scalar(select(Supplier).where(Supplier.company_id == 1, Supplier.name == name))
            if existing is None:
                db.add(Supplier(company_id=1, name=name))

        # Starting funds are equity, not income: both sides of the journal balance.
        funding = Decimal("50000.00")
        opening = JournalEntry(
            posting_date=date(2026, 1, 1),
            description="Demo opening bank funding",
            kind="opening",
            lines=[
                JournalLine(account_id=accounts["1000"].id, debit=funding, credit=Decimal("0.00")),
                JournalLine(account_id=accounts["3000"].id, debit=Decimal("0.00"), credit=funding),
            ],
        )
        db.add(opening)
    return True
