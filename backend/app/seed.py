"""Explicit reference seeding. Accounts and demo transactions come later."""

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert

from app.models import Company


def seed_company(engine: Engine) -> bool:
    """Insert the demo company once without overwriting an existing company."""
    statement = (
        insert(Company)
        .values(id=1, name="Northbridge Demo Ltd", base_currency="GBP")
        .on_conflict_do_nothing(index_elements=[Company.id])
        .returning(Company.id)
    )
    with engine.begin() as connection:
        created = connection.execute(statement).scalar_one_or_none() is not None
    return created
