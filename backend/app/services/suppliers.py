"""Supplier workflows. Callers supply sessions; write services own transactions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Supplier
from app.schemas import SupplierCreate, SupplierRead


def create_supplier(db: Session, data: SupplierCreate) -> SupplierRead:
    with db.begin():
        if db.get(Company, 1) is None:
            raise ValueError("Company is missing. Run 'app seed' first.")
        supplier = Supplier(company_id=1, name=data.name)
        db.add(supplier)
        db.flush()
        result = SupplierRead.model_validate(supplier)
    # Only return success after the transaction commits.
    return result


def list_suppliers(db: Session) -> list[SupplierRead]:
    suppliers = db.scalars(
        select(Supplier).where(Supplier.company_id == 1).order_by(Supplier.name, Supplier.id)
    )
    return [SupplierRead.model_validate(supplier) for supplier in suppliers]
