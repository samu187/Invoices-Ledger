"""HTTP input/output; services own the accounting and write transactions."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, Invoice, JournalEntry, Payment
from app.schemas import (
    InvoiceCreate, InvoiceCreated, InvoiceDetail, InvoicePaymentsRead, InvoiceRead,
    PaymentCreate, PaymentCreated, SupplierCreate, SupplierRead,
    AccountRead, AccountDetail, JournalHeader, JournalRead, OutstandingRead,
    PaymentRead, PaymentDetail, TrialBalanceRead, ProfitLossRead,
    InputVatMonthRead,
)
from app.services import accounts, invoices, journals, payments, suppliers

router = APIRouter()


@router.post("/suppliers", response_model=SupplierRead, status_code=201)
def supplier_create(data: SupplierCreate, db: Session = Depends(get_db)):
    return suppliers.create_supplier(db, data)


@router.get("/suppliers", response_model=list[SupplierRead])
def supplier_list(db: Session = Depends(get_db)):
    return suppliers.list_suppliers(db)


@router.post("/invoices", response_model=InvoiceCreated, status_code=201)
def invoice_create(data: InvoiceCreate, db: Session = Depends(get_db)):
    return invoices.create_invoice(db, data)


@router.get("/invoices", response_model=list[InvoiceRead])
def invoice_list(company_id: int = Query(1, gt=0), db: Session = Depends(get_db)):
    return invoices.list_invoices(db, company_id)


@router.get("/invoices/outstanding", response_model=OutstandingRead)
def invoice_outstanding(db: Session = Depends(get_db)):
    return invoices.get_outstanding_invoices(db)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def invoice_detail(invoice_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    if db.get(Invoice, invoice_id) is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoices.get_invoice(db, invoice_id)


@router.get("/invoices/{invoice_id}/payments", response_model=InvoicePaymentsRead)
def invoice_payments(invoice_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    if db.get(Invoice, invoice_id) is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoices.get_invoice_payments(db, invoice_id)


@router.post("/payments", response_model=PaymentCreated, status_code=201)
def payment_create(data: PaymentCreate, db: Session = Depends(get_db)):
    return payments.create_payment(db, data)


@router.get("/payments", response_model=list[PaymentRead])
def payment_list(db: Session = Depends(get_db)):
    return payments.list_payments(db)


@router.get("/payments/{payment_id}", response_model=PaymentDetail)
def payment_detail(payment_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    if db.get(Payment, payment_id) is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return payments.get_payment(db, payment_id)


@router.get("/journals", response_model=list[JournalHeader])
def journal_list(db: Session = Depends(get_db)):
    return journals.list_journals(db)


@router.get("/journals/{journal_id}", response_model=JournalRead)
def journal_detail(journal_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    if db.get(JournalEntry, journal_id) is None:
        raise HTTPException(status_code=404, detail="Journal not found.")
    return journals.get_journal(db, journal_id)


@router.get("/accounts", response_model=list[AccountRead])
def account_list(db: Session = Depends(get_db)):
    return accounts.list_accounts(db)


@router.get("/accounts/trial-balance", response_model=TrialBalanceRead)
def trial_balance(db: Session = Depends(get_db)):
    return accounts.get_trial_balance(db)


@router.get("/accounts/pnl", response_model=ProfitLossRead)
def profit_and_loss(start: date = Query(..., alias="from"), end: date = Query(..., alias="to"),
                    db: Session = Depends(get_db)):
    return accounts.get_profit_and_loss(db, start, end)


@router.get("/accounts/input-vat", response_model=InputVatMonthRead)
def input_vat_month(month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                    db: Session = Depends(get_db)):
    return accounts.get_input_vat_month(db, date.fromisoformat(f"{month}-01"))


@router.get("/accounts/{code}", response_model=AccountDetail)
def account_detail(code: str, db: Session = Depends(get_db)):
    if db.scalar(select(Account.id).where(Account.company_id == 1, Account.code == code)) is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    return accounts.get_account_activity(db, code)
