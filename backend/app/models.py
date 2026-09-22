"""SQLAlchemy table definitions. Importing this module never connects to a database."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass



class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    name: Mapped[str] = mapped_column(String(200))
    base_currency: Mapped[str] = mapped_column(String(3), default="GBP")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=1)
    name: Mapped[str] = mapped_column(String(200))


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("account_type IN ('asset', 'liability', 'equity', 'income', 'expense')", name="valid_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), default=1)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(20))


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("supplier_id", "invoice_number"),
        CheckConstraint("currency IN ('GBP', 'EUR', 'USD')", name="valid_currency"),
        CheckConstraint("total_amount > 0", name="positive_total"),
        CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="valid_vat_rate"),
        CheckConstraint("exchange_rate > 0 AND (currency <> 'GBP' OR exchange_rate = 1)", name="valid_rate"),
        CheckConstraint("rate_date <= invoice_date", name="rate_not_future"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(100))
    invoice_date: Mapped[date]
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20.00"))
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    rate_date: Mapped[date]
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", passive_deletes="all")


class Payment(Base):
    __tablename__ = "payments"
    # Currency comes from the linked invoice; no second currency field to disagree.
    __table_args__ = (
        UniqueConstraint("id", "invoice_id"),
        CheckConstraint("amount > 0 AND base_amount > 0 AND exchange_rate > 0 AND bank_fee >= 0", name="valid_amounts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    payment_date: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))
    bank_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    reference: Mapped[str | None] = mapped_column(String(200))
    request_id: Mapped[UUID] = mapped_column(unique=True, default=uuid4)
    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        ForeignKeyConstraint(["payment_id", "invoice_id"], ["payments.id", "payments.invoice_id"]),
        Index("uq_journal_entries_invoice_posting", "invoice_id", unique=True, postgresql_where=text("kind = 'invoice'")),
        CheckConstraint("(kind = 'invoice' AND invoice_id IS NOT NULL AND payment_id IS NULL) OR (kind = 'payment' AND invoice_id IS NOT NULL AND payment_id IS NOT NULL) OR (kind = 'opening' AND invoice_id IS NULL AND payment_id IS NULL)", name="valid_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    posting_date: Mapped[date] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(20))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    payment_id: Mapped[int | None] = mapped_column(unique=True)
    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry", passive_deletes="all")


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="one_positive_side"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("currency", "base_currency", "rate_date"),
        CheckConstraint("currency IN ('GBP', 'EUR', 'USD') AND base_currency = 'GBP'", name="valid_currencies"),
        CheckConstraint("rate > 0 AND (currency <> 'GBP' OR rate = 1)", name="valid_rate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    currency: Mapped[str] = mapped_column(String(3))
    base_currency: Mapped[str] = mapped_column(String(3), default="GBP")
    rate_date: Mapped[date]
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10))


class SeedRun(Base):
    __tablename__ = "seed_runs"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
