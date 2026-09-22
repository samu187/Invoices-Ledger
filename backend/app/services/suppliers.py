"""Supplier workflows. Each call owns its session and transaction."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Company, Supplier
from app.schemas import SupplierCreate, SupplierRead


class CompanyNotConfiguredError(ValueError):
    """The demo company must be explicitly seeded before creating suppliers."""


def create_supplier(engine: Engine, data: SupplierCreate) -> SupplierRead:
    with Session(engine) as session, session.begin():
        if session.get(Company, 1) is None:
            raise CompanyNotConfiguredError("Company is missing. Run 'app seed' first.")
        supplier = Supplier(company_id=1, name=data.name)
        session.add(supplier)
        session.flush()
        result = SupplierRead.model_validate(supplier)
    # Only return success after the transaction commits.
    return result


def list_suppliers(engine: Engine) -> list[SupplierRead]:
    with Session(engine) as session:
        suppliers = session.scalars(
            select(Supplier).where(Supplier.company_id == 1).order_by(Supplier.name, Supplier.id)
        )
        return [SupplierRead.model_validate(supplier) for supplier in suppliers]
