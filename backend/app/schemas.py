"""Validated data shared by CLI commands and future API routes."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    created_at: datetime


class InvoiceCreate(BaseModel):
    """Invoice facts; GBP amounts and the expense account are recorded in journal lines."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_id: int = Field(default=1, gt=0)
    supplier_id: int = Field(gt=0)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date = Field(default_factory=date.today)
    currency: Literal["GBP", "EUR", "USD"]
    expense_account_code: str = Field(min_length=1, max_length=30)
    total_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2, description="VAT-inclusive total in invoice currency")
    vat_rate: Decimal = Field(default=Decimal("20.00"), ge=0, le=100, decimal_places=2, description="Percentage points: 20 means 20%")

    @field_validator("invoice_date")
    @classmethod
    def check_invoice_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Invoice date cannot be in the future.")
        return value


class PaymentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    invoice_id: int = Field(gt=0)
    currency: Literal["GBP", "EUR", "USD"]
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_date: date = Field(default_factory=date.today)
    bank_account_code: Literal["1000"] = "1000"
    exchange_rate: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=10)
    bank_fees: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=18, decimal_places=2)
    reference: str | None = Field(default=None, max_length=200)
    request_id: UUID = Field(default_factory=uuid4)

    @field_validator("payment_date")
    @classmethod
    def check_payment_date(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Payment date cannot be in the future.")
        return value


class InvoiceCreated(BaseModel):
    invoice_id: int
    journal_id: int


class PaymentCreated(BaseModel):
    payment_id: int
    journal_id: int
    bank_total: Decimal


class JournalLineRead(BaseModel):
    code: str
    name: str
    debit: Decimal
    credit: Decimal


class JournalRead(BaseModel):
    id: int
    posting_date: date
    kind: str
    description: str
    invoice_id: int | None
    payment_id: int | None
    lines: list[JournalLineRead]
    total_debit: Decimal
    total_credit: Decimal


class InvoiceRead(BaseModel):
    id: int
    number: str
    date: date
    supplier: str
    company_id: int
    currency: str
    total: Decimal
    paid: Decimal
    balance: Decimal
    vat_rate: Decimal
    exchange_rate: Decimal
    rate_date: date
    base_currency: str
    base_net: Decimal
    base_vat: Decimal
    base_total: Decimal
    base_balance: Decimal
    expense_accounts: list[str]
    has_invoice_posting: bool


class InvoiceDetail(InvoiceRead):
    journals: list[JournalRead]


class InvoicePaymentRow(BaseModel):
    date: date
    reference: str
    amount: Decimal
    balance: Decimal
    payables: Decimal
    base_balance: Decimal


class InvoicePaymentsRead(BaseModel):
    id: int
    number: str
    currency: str
    total: Decimal
    base_currency: str
    rows: list[InvoicePaymentRow]
    balance: Decimal
    base_balance: Decimal


class JournalHeader(BaseModel):
    id: int
    posting_date: date
    kind: str
    description: str
    invoice_id: int | None
    payment_id: int | None


class PaymentRead(BaseModel):
    id: int
    payment_date: date
    invoice_id: int
    invoice_number: str
    supplier: str
    currency: str
    amount: Decimal
    bank_code: str
    bank_name: str
    exchange_rate: Decimal
    base_amount: Decimal
    bank_fee: Decimal
    bank_total: Decimal
    reference: str | None


class PaymentDetail(PaymentRead):
    journal: JournalRead


class OutstandingRead(BaseModel):
    rows: list[InvoiceRead]
    currency_totals: dict[str, Decimal]
    base_total: Decimal
    payables: Decimal
    difference: Decimal


class AccountRead(BaseModel):
    code: str
    name: str
    account_type: str
    balance: Decimal


class AccountTransaction(BaseModel):
    entry_id: int
    posting_date: date
    description: str
    invoice_id: int | None
    payment_id: int | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class AccountDetail(AccountRead):
    transactions: list[AccountTransaction]


class TrialBalanceRow(AccountRead):
    debit: Decimal
    credit: Decimal


class TrialBalanceRead(BaseModel):
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool


class ProfitLossRow(BaseModel):
    code: str
    name: str
    account_type: str
    profit: Decimal


class ProfitLossRead(BaseModel):
    rows: list[ProfitLossRow]
    profit: Decimal
