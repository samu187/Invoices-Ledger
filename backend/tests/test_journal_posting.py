"""Shared posting guard; no database connection needed."""

from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from app.models import JournalEntry, JournalLine
from app.services.journals import add_journal
from app.schemas import InvoiceCreate
from app.services.invoices import create_invoice


class JournalPostingTests(unittest.TestCase):
    def test_balanced_decimal_entry_is_added_without_commit(self):
        db = MagicMock()
        entry = JournalEntry(lines=[
            JournalLine(debit=Decimal("0.10")),
            JournalLine(debit=Decimal("0.20")),
            JournalLine(credit=Decimal("0.30")),
        ])
        add_journal(db, entry)
        db.add.assert_called_once_with(entry)
        db.commit.assert_not_called()

    def test_empty_and_one_penny_imbalance_rejected(self):
        for lines in ([], [JournalLine(debit=Decimal("100.00")),
                          JournalLine(credit=Decimal("99.99"))]):
            db = MagicMock()
            with self.assertRaises(ValueError):
                add_journal(db, JournalEntry(lines=lines))
            db.add.assert_not_called()

    def test_invoice_guard_failure_exits_entire_transaction(self):
        from app.models import Account, Company, Supplier

        db = MagicMock()
        db.get.side_effect = [Company(id=1, base_currency="GBP"), Supplier(company_id=1, name="Demo")]
        db.scalar.side_effect = [None, Account(id=1, account_type="expense"),
                                 Account(id=2, account_type="liability"), Account(id=3, account_type="asset")]
        data = InvoiceCreate(supplier_id=1, invoice_number="TEST", currency="GBP",
                             total_amount="120", expense_account_code="5000")
        with patch("app.services.invoices.add_journal", side_effect=ValueError("Unbalanced")):
            with self.assertRaisesRegex(ValueError, "Unbalanced"):
                create_invoice(db, data)
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], ValueError)
        db.commit.assert_not_called()
