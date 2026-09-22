"""Record settlement and its journal in one transaction."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Company, Invoice, JournalEntry, JournalLine, Payment, Supplier
from app.schemas import PaymentCreate
from app.services.journals import add_journal


def create_payment(db: Session, data: PaymentCreate) -> dict:
    with db.begin():
        # Serialize payments for this invoice before checking its remaining balance.
        invoice = db.scalar(select(Invoice).where(Invoice.id == data.invoice_id).with_for_update())
        if invoice is None:
            raise ValueError("Invoice not found.")
        if data.currency != invoice.currency:
            raise ValueError("Payment currency must match invoice currency.")
        if data.payment_date < invoice.invoice_date:
            raise ValueError("Payment date cannot be before the invoice date.")
        if db.scalar(select(Payment.id).where(Payment.request_id == data.request_id)) is not None:
            raise ValueError("This payment request has already been recorded.")
        supplier = db.get(Supplier, invoice.supplier_id)
        company = db.get(Company, supplier.company_id)
        if company.base_currency != "GBP":
            raise ValueError("Payments currently support companies with GBP base currency only.")

        accounts = {account.code: account for account in db.scalars(
            select(Account).where(Account.company_id == company.id)
        ).all()}
        for code, kind in ((data.bank_account_code, "asset"), ("2000", "liability")):
            if code not in accounts or accounts[code].account_type != kind:
                raise ValueError(f"Account {code} is missing or has the wrong type.")

        bank_currency = "GBP"  # Account 1000 (HSBC GBP) is the only bank in this demo.
        if data.currency == bank_currency:
            if data.exchange_rate is not None and data.exchange_rate != 1:
                raise ValueError("Same-currency payments must use exchange rate 1.")
            rate = Decimal("1")
        else:
            if data.exchange_rate is None:
                raise ValueError("Supply --exchange-rate as GBP per one unit of payment currency.")
            rate = data.exchange_rate

        paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice.id,
        ))
        if paid + data.amount > invoice.total_amount:
            raise ValueError("Payment exceeds the invoice's outstanding balance.")
        latest_date = db.scalar(select(func.max(Payment.payment_date)).where(Payment.invoice_id == invoice.id))
        if latest_date is not None and data.payment_date < latest_date:
            raise ValueError("Record payments in date order for this invoice.")

        payable_query = select(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0)).join(
            JournalEntry, JournalEntry.id == JournalLine.entry_id,
        ).where(JournalEntry.invoice_id == invoice.id, JournalLine.account_id == accounts["2000"].id)
        original = db.scalar(payable_query.where(JournalEntry.kind == "invoice"))
        remaining = db.scalar(payable_query)
        if original <= 0 or not 0 <= remaining <= original:
            raise ValueError("Invoice payable postings are missing or inconsistent.")

        penny = Decimal("0.01")
        # Cumulative rounding makes the final payment clear the original liability exactly.
        cumulative_release = (original * (paid + data.amount) / invoice.total_amount).quantize(penny, rounding=ROUND_HALF_UP)
        released = cumulative_release - (original - remaining)
        if released < 0 or released > remaining:
            raise ValueError("Invoice payable balance is inconsistent with its payments.")
        base_amount = (data.amount * rate).quantize(penny, rounding=ROUND_HALF_UP)
        bank_total = base_amount + data.bank_fees
        if base_amount <= 0 or bank_total >= Decimal("10000000000000000"):
            raise ValueError("Converted payment must be at least GBP 0.01 and fit the account amount limit.")
        fx = base_amount - released
        lines = [JournalLine(account_id=accounts[data.bank_account_code].id, debit=0, credit=bank_total)]
        if released > 0:
            lines.append(JournalLine(account_id=accounts["2000"].id, debit=released, credit=0))
        for code, kind, debit, credit in (
            ("5200", "expense", data.bank_fees, Decimal("0")),
            ("5900", "expense", max(fx, Decimal("0")), Decimal("0")),
            ("4900", "income", Decimal("0"), max(-fx, Decimal("0"))),
        ):
            if debit or credit:
                if code not in accounts or accounts[code].account_type != kind:
                    raise ValueError(f"Account {code} is missing or has the wrong type.")
                lines.append(JournalLine(account_id=accounts[code].id, debit=debit, credit=credit))

        payment = Payment(invoice_id=invoice.id, payment_date=data.payment_date, amount=data.amount,
                          base_amount=base_amount, exchange_rate=rate, bank_fee=data.bank_fees,
                          bank_account_id=accounts[data.bank_account_code].id, reference=data.reference,
                          request_id=data.request_id)
        db.add(payment)
        db.flush()
        journal = JournalEntry(posting_date=data.payment_date, kind="payment", invoice_id=invoice.id,
                               payment_id=payment.id, description=f"Payment for invoice {invoice.invoice_number}", lines=lines)
        add_journal(db, journal)
        db.flush()
        result = {"payment_id": payment.id, "journal_id": journal.id, "bank_total": bank_total}
    return result
