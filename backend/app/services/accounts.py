"""Read-only account reports. All amounts are GBP; balance = debits - credits."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, JournalEntry, JournalLine


def list_accounts(db: Session) -> list[dict]:
    statement = (
        select(
            Account.code, Account.name, Account.account_type,
            func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0).label("balance"),
        )
        .outerjoin(JournalLine, JournalLine.account_id == Account.id)
        .where(Account.company_id == 1)
        .group_by(Account.id)
        .order_by(Account.code)
    )
    return [dict(row) for row in db.execute(statement).mappings()]


def get_account_activity(db: Session, code: str) -> dict:
    account = db.scalar(select(Account).where(Account.company_id == 1, Account.code == code))
    if account is None:
        raise ValueError(f"Account {code} not found. Use 'app accounts list' to see account codes.")

    statement = (
        select(
            JournalEntry.id.label("entry_id"), JournalEntry.posting_date,
            JournalEntry.description, JournalEntry.invoice_id, JournalEntry.payment_id,
            JournalLine.debit, JournalLine.credit,
        )
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account.id)
        .order_by(JournalEntry.posting_date, JournalEntry.id, JournalLine.id)
    )
    balance = Decimal("0.00")
    transactions = []
    for row in db.execute(statement).mappings():
        balance += row["debit"] - row["credit"]
        transactions.append({**row, "balance": balance})
    return {"code": account.code, "name": account.name, "account_type": account.account_type,
            "balance": balance, "transactions": transactions}
