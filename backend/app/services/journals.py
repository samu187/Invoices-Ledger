"""Read-only journal summaries and complete entries in GBP."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, JournalEntry, JournalLine


def list_journals(db: Session) -> list[dict]:
    statement = select(
        JournalEntry.id, JournalEntry.posting_date, JournalEntry.kind,
        JournalEntry.description, JournalEntry.invoice_id, JournalEntry.payment_id,
    ).order_by(JournalEntry.posting_date, JournalEntry.id)
    return [dict(row) for row in db.execute(statement).mappings()]


def get_journal(db: Session, entry_id: int) -> dict:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise ValueError(f"Journal entry {entry_id} not found. Use 'app journals list' to see entry IDs.")

    statement = (
        select(Account.code, Account.name, JournalLine.debit, JournalLine.credit)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .where(JournalLine.entry_id == entry_id)
        .order_by(JournalLine.id)
    )
    lines = [dict(row) for row in db.execute(statement).mappings()]
    total_debit = sum((line["debit"] for line in lines), Decimal("0.00"))
    total_credit = sum((line["credit"] for line in lines), Decimal("0.00"))
    return {
        "id": entry.id, "posting_date": entry.posting_date, "kind": entry.kind,
        "description": entry.description, "invoice_id": entry.invoice_id,
        "payment_id": entry.payment_id, "lines": lines,
        "total_debit": total_debit, "total_credit": total_credit,
    }
