"""Create invoices and their journals together, preserving applied FX rates."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Company, Invoice, JournalEntry, JournalLine, Supplier
from app.schemas import InvoiceCreate
from app.services.journals import add_journal
from app.services.fx_rates import get_rates


def create_invoice(db: Session, data: InvoiceCreate) -> dict:
    with db.begin():
        company = db.get(Company, data.company_id)
        if company is None:
            raise ValueError("Company not found. Run the seed first or check company ID.")

        supplier = db.get(Supplier, data.supplier_id)
        if supplier is None or supplier.company_id != data.company_id:
            raise ValueError("Supplier not found for this company.")

        existing = db.scalar(select(Invoice.id).where(
            Invoice.supplier_id == data.supplier_id, Invoice.invoice_number == data.invoice_number,
        ))
        if existing is not None:
            raise ValueError("This supplier already has an invoice with that number.")

        expense = db.scalar(select(Account).where(
            Account.company_id == data.company_id, Account.code == data.expense_account_code,
        ))
        payables = db.scalar(select(Account).where(
            Account.company_id == data.company_id, Account.code == "2000",
        ))
        if expense is None or expense.account_type != "expense":
            raise ValueError("Choose an expense account belonging to this company.")
        if payables is None or payables.account_type != "liability":
            raise ValueError("Payables account 2000 is missing or has the wrong type.")

        rate = Decimal("1")
        rate_date = data.invoice_date
        if data.currency != company.base_currency:
            if company.base_currency != "GBP":
                raise ValueError("Foreign invoices currently require a GBP base currency.")
            rates = get_rates(db, data.invoice_date)
            rate = rates["rates"][data.currency]
            rate_date = rates["rate_date"]
        base_total = (data.total_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if base_total <= 0 or base_total >= Decimal("10000000000000000"):
            raise ValueError("Converted invoice total must be at least 0.01 and fit the amount limit.")
        base_net = (base_total / (1 + data.vat_rate / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_vat = base_total - base_net

        lines = [JournalLine(account_id=expense.id, debit=base_net, credit=Decimal("0.00"))]
        if base_vat > 0:
            vat_account = db.scalar(select(Account).where(
                Account.company_id == data.company_id, Account.code == "1100",
            ))
            if vat_account is None or vat_account.account_type != "asset":
                raise ValueError("Input VAT account 1100 is missing or has the wrong type.")
            lines.append(JournalLine(account_id=vat_account.id, debit=base_vat, credit=Decimal("0.00")))
        lines.append(JournalLine(account_id=payables.id, debit=Decimal("0.00"), credit=base_total))

        invoice = Invoice(
            supplier_id=data.supplier_id, invoice_number=data.invoice_number,
            invoice_date=data.invoice_date, currency=data.currency,
            total_amount=data.total_amount, vat_rate=data.vat_rate,
            exchange_rate=rate, rate_date=rate_date,
        )
        db.add(invoice)
        db.flush()  # Get the invoice ID for the journal link.
        
        journal = JournalEntry(
            posting_date=data.invoice_date, kind="invoice", invoice_id=invoice.id,
            description=f"Invoice {data.invoice_number} - {supplier.name}", lines=lines,
        )
        add_journal(db, journal)
        db.flush()
        result = {"invoice_id": invoice.id, "journal_id": journal.id}
    return result


def invoice_summary(db: Session, invoice: Invoice) -> dict:
    """Combine invoice facts, paid original amounts, and posted base amounts."""
    from sqlalchemy import func
    from app.models import Payment

    supplier = db.get(Supplier, invoice.supplier_id)
    company = db.get(Company, supplier.company_id)
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.invoice_id == invoice.id,
    ))
    # Query separately from payments so multiple journal lines cannot multiply paid totals.
    postings = db.execute(
        select(JournalEntry.kind, Account.code, Account.name, Account.account_type,
               JournalLine.debit, JournalLine.credit)
        .select_from(JournalEntry)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.invoice_id == invoice.id)
        .order_by(JournalEntry.posting_date, JournalEntry.id, JournalLine.id)
    ).mappings()
    base_net = base_vat = base_total = base_balance = Decimal("0.00")
    expense_accounts = []
    has_invoice_posting = False
    for line in postings:
        if line["code"] == "2000":
            base_balance += line["credit"] - line["debit"]
        if line["kind"] != "invoice":
            continue
        has_invoice_posting = True
        if line["account_type"] == "expense":
            base_net += line["debit"] - line["credit"]
            label = f"{line['code']} - {line['name']}"
            if label not in expense_accounts:
                expense_accounts.append(label)
        elif line["code"] == "1100":
            base_vat += line["debit"] - line["credit"]
        elif line["code"] == "2000":
            base_total += line["credit"] - line["debit"]
    return {
        "id": invoice.id, "number": invoice.invoice_number, "date": invoice.invoice_date,
        "supplier": supplier.name, "company_id": company.id, "currency": invoice.currency,
        "total": invoice.total_amount, "paid": paid, "balance": invoice.total_amount - paid,
        "vat_rate": invoice.vat_rate, "exchange_rate": invoice.exchange_rate,
        "rate_date": invoice.rate_date, "base_currency": company.base_currency,
        "base_net": base_net, "base_vat": base_vat, "base_total": base_total,
        "base_balance": base_balance, "expense_accounts": expense_accounts,
        "has_invoice_posting": has_invoice_posting,
    }


def list_invoices(db: Session, company_id: int = 1) -> list[dict]:
    invoices = db.scalars(select(Invoice).join(Supplier).where(
        Supplier.company_id == company_id,
    ).order_by(Invoice.invoice_date, Invoice.id)).all()
    return [invoice_summary(db, invoice) for invoice in invoices]


def get_invoice(db: Session, invoice_id: int) -> dict:
    from app.services.journals import get_journal

    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found. Use 'invoice-ledger invoices list' to see IDs.")
    report = invoice_summary(db, invoice)
    journal_ids = db.scalars(select(JournalEntry.id).where(
        JournalEntry.invoice_id == invoice_id,
    ).order_by(JournalEntry.posting_date, JournalEntry.id)).all()
    report["journals"] = [get_journal(db, entry_id) for entry_id in journal_ids]
    return report


def get_invoice_payments(db: Session, invoice_id: int) -> dict:
    """Running original-currency debt and base payables, using actual postings."""
    from sqlalchemy import case, func
    from app.models import Payment

    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found.")
    supplier = db.get(Supplier, invoice.supplier_id)
    company = db.get(Company, supplier.company_id)

    # Include payment journals even when their liability release rounds to zero.
    postings = db.execute(
        select(JournalEntry.kind, JournalEntry.payment_id,
               func.sum(case((Account.code == "2000", JournalLine.credit - JournalLine.debit),
                             else_=0)).label("movement"))
        .select_from(JournalEntry)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.invoice_id == invoice_id,
               Account.company_id == company.id)
        .group_by(JournalEntry.kind, JournalEntry.payment_id)
    ).mappings()
    movements = {(row["kind"], row["payment_id"]): row["movement"] for row in postings}
    if movements.get(("invoice", None), 0) <= 0:
        raise ValueError("Invoice payable posting is missing; cannot show a reliable base balance.")

    balance = invoice.total_amount
    base_balance = movements[("invoice", None)]
    rows = [{"date": invoice.invoice_date, "reference": f"Invoice #{invoice.id}",
             "amount": invoice.total_amount, "balance": balance,
             "payables": base_balance, "base_balance": base_balance}]
    payments = db.scalars(select(Payment).where(Payment.invoice_id == invoice_id)
                          .order_by(Payment.payment_date, Payment.id)).all()
    for payment in payments:
        key = ("payment", payment.id)
        if key not in movements:
            raise ValueError(f"Payment {payment.id} payable posting is missing; cannot show a reliable base balance.")
        balance -= payment.amount
        base_balance += movements[key]
        rows.append({"date": payment.payment_date, "reference": f"Payment #{payment.id}",
                     "amount": -payment.amount, "balance": balance,
                     "payables": movements[key], "base_balance": base_balance})
    return {"id": invoice.id, "number": invoice.invoice_number, "currency": invoice.currency,
            "total": invoice.total_amount, "base_currency": company.base_currency,
            "rows": rows, "balance": balance, "base_balance": base_balance}
