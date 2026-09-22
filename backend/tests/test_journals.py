"""Offline journal report checks."""

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from app.cli import app
from app.models import JournalEntry
from app.services.journals import get_journal, list_journals


class JournalTests(unittest.TestCase):
    def session(self):
        db = MagicMock()
        db.get.return_value = JournalEntry(id=7, posting_date=date(2026, 1, 1), kind="opening", description="Opening funding")
        db.execute.return_value.mappings.return_value = [
            {"code": "1000", "name": "HSBC GBP", "debit": Decimal("50000.00"), "credit": Decimal("0.00")},
            {"code": "3000", "name": "Opening equity", "debit": Decimal("0.00"), "credit": Decimal("50000.00")},
        ]
        return db

    def test_full_entry_includes_both_sides_and_totals(self):
        db = self.session()
        report = get_journal(db, 7)
        self.assertEqual(len(report["lines"]), 2)
        self.assertEqual(report["total_debit"], Decimal("50000.00"))
        self.assertEqual(report["total_credit"], Decimal("50000.00"))
        db.commit.assert_not_called()

    def test_missing_entry(self):
        db = self.session()
        db.get.return_value = None
        with self.assertRaisesRegex(ValueError, "Journal entry 99 not found"):
            get_journal(db, 99)
        db.execute.assert_not_called()

    @patch("app.db.SessionLocal")
    @patch("app.cli.get_journal")
    def test_show_outputs_full_entry(self, get, factory):
        get.return_value = get_journal(self.session(), 7)
        result = CliRunner().invoke(app, ["journals", "show", "7"])
        self.assertEqual(result.exit_code, 0, result.output)
        for text in ("HSBC GBP", "Opening equity", "TOTAL", "Balanced."):
            self.assertIn(text, result.output)

    @patch("app.db.SessionLocal")
    @patch("app.cli.list_journals")
    def test_list_only_shows_headers(self, listing, factory):
        listing.return_value = [{"id": 7, "posting_date": date(2026, 1, 1), "kind": "opening", "description": "Opening funding", "invoice_id": None, "payment_id": None}]
        result = CliRunner().invoke(app, ["journals", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Opening funding", result.output)
        for text in ("HSBC GBP", "Debit GBP", "TOTAL"):
            self.assertNotIn(text, result.output)

    def test_list_query_does_not_load_lines(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value = []
        self.assertEqual(list_journals(db), [])
        self.assertNotIn("journal_lines", str(db.execute.call_args.args[0]))

    @patch("app.db.SessionLocal")
    @patch("app.cli.get_journal")
    def test_empty_and_unbalanced_entries_not_labelled_balanced(self, get, factory):
        for lines in ([], [{"code": "1000", "name": "HSBC GBP", "debit": Decimal("1.00"), "credit": Decimal("0.00")}]):
            db = self.session()
            db.execute.return_value.mappings.return_value = lines
            get.return_value = get_journal(db, 7)
            result = CliRunner().invoke(app, ["journals", "show", "7"])
            self.assertEqual(result.exit_code, 0)
            self.assertNotIn("Balanced.", result.output)
