"""Offline report calculations and CLI checks; no database connections."""

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import postgresql
from typer.testing import CliRunner

from app.cli import app, format_balance
from app.models import Account
from app.services.accounts import get_account_activity, list_accounts


class AccountTests(unittest.TestCase):
    def test_overview_includes_unused_accounts_via_outer_join(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value = [
            {"code": "2000", "name": "Payables", "account_type": "liability", "balance": Decimal("0.00")}
        ]
        result = list_accounts(db)
        self.assertEqual(result[0]["balance"], Decimal("0.00"))
        sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
        self.assertIn("LEFT OUTER JOIN", sql)
        self.assertIn("coalesce", sql)
        self.assertIn("ORDER BY accounts.code", sql)

    def test_running_balance_and_closing_balance(self):
        db = MagicMock()
        db.scalar.return_value = Account(id=1, code="1000", name="HSBC GBP", account_type="asset")
        db.execute.return_value.mappings.return_value = [
            {"entry_id": i, "posting_date": date(2026, 1, 1), "description": "Test",
             "invoice_id": None, "payment_id": None, "debit": Decimal(debit), "credit": Decimal(credit)}
            for i, debit, credit in [(1, "10000.00", "0.00"), (2, "0.00", "43.01"), (3, "0.00", "10000.00")]
        ]
        report = get_account_activity(db, "1000")
        self.assertEqual([row["balance"] for row in report["transactions"]],
                         [Decimal("10000.00"), Decimal("9956.99"), Decimal("-43.01")])
        self.assertEqual(report["balance"], Decimal("-43.01"))
        sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
        self.assertIn("ORDER BY journal_entries.posting_date, journal_entries.id, journal_lines.id", sql)
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_missing_account_is_clear(self):
        db = MagicMock()
        db.scalar.return_value = None
        with self.assertRaisesRegex(ValueError, "Account 9999 not found"):
            get_account_activity(db, "9999")
        db.execute.assert_not_called()

    def test_no_transactions_gives_zero_balance(self):
        db = MagicMock()
        db.scalar.return_value = Account(id=1, code="1000", name="HSBC GBP", account_type="asset")
        db.execute.return_value.mappings.return_value = []
        result = get_account_activity(db, "1000")
        self.assertEqual(result["balance"], Decimal("0.00"))
        self.assertEqual(result["transactions"], [])

    def test_debit_credit_labels(self):
        self.assertEqual(format_balance(Decimal("10000")), "10,000.00 Dr")
        self.assertEqual(format_balance(Decimal("-10000")), "10,000.00 Cr")
        self.assertEqual(format_balance(Decimal("0")), "0.00")

    @patch("app.db.SessionLocal")
    @patch("app.cli.list_accounts", return_value=[])
    def test_empty_overview(self, listing, session):
        result = CliRunner().invoke(app, ["accounts", "list"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("app seed", result.output)

    @patch("app.db.SessionLocal")
    @patch("app.cli.get_account_activity")
    def test_show_displays_opening_journal(self, activity, session):
        activity.return_value = {"code": "1000", "name": "HSBC GBP", "account_type": "asset", "balance": Decimal("10000"),
            "transactions": [{"posting_date": date(2026, 1, 1), "entry_id": 1, "debit": Decimal("10000"), "credit": Decimal("0"),
                              "balance": Decimal("10000"), "description": "Demo opening bank funding", "invoice_id": None, "payment_id": None}]}
        result = CliRunner().invoke(app, ["accounts", "show", "1000"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("2026-01-01", result.output)
        self.assertIn("Demo opening bank funding", result.output)
        self.assertIn("Closing balance: 10,000.00 Dr GBP", result.output)
