"""Read-only reporting checks without live database access."""
from decimal import Decimal as D
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from app.cli import app
from app.services.accounts import get_trial_balance
from app.services.invoices import get_outstanding_invoices
from app.services.payments import get_payment, list_payments


class AddedReportTests(unittest.TestCase):
    @patch("app.services.accounts.list_accounts")
    def test_trial_balance_splits_debit_credit_and_detects_difference(self, accounts):
        accounts.return_value = [dict(code="1000", name="Bank", balance=D("90")),
                                 dict(code="5000", name="Expense", balance=D("10")),
                                 dict(code="3000", name="Equity", balance=D("-100"))]
        result = get_trial_balance(MagicMock())
        self.assertEqual(result["total_debit"], 100)
        self.assertEqual(result["total_credit"], 100)
        self.assertTrue(result["balanced"])
        accounts.return_value[-1]["balance"] = D("-99")
        self.assertFalse(get_trial_balance(MagicMock())["balanced"])

    @patch("app.services.accounts.get_account_activity")
    @patch("app.services.invoices.list_invoices")
    def test_outstanding_groups_currencies_and_reconciles_carrying_not_cash(self, invoices, account):
        invoices.return_value = [dict(currency=ccy, balance=D(amount), base_balance=D(base), has_invoice_posting=True)
                                for ccy, amount, base in [("USD", "50", "42.50"), ("EUR", "10", "8"),
                                                         ("USD", "20", "17"), ("GBP", "0", "0")]]
        account.return_value = {"balance": D("-67.50")}
        result = get_outstanding_invoices(MagicMock())
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["currency_totals"], {"USD": D("70"), "EUR": D("10")})
        self.assertEqual(result["base_total"], D("67.50"))
        self.assertEqual(result["difference"], 0)
        account.return_value = {"balance": D("-68.50")}
        self.assertEqual(get_outstanding_invoices(MagicMock())["difference"], -1)

    @patch("app.services.accounts.get_account_activity", return_value={"balance": D("-0.01")})
    @patch("app.services.invoices.list_invoices")
    def test_foreign_settled_invoice_with_base_residual_stays_visible(self, invoices, account):
        invoices.return_value = [dict(currency="USD", balance=D("0"), base_balance=D("0.01"), has_invoice_posting=True)]
        self.assertEqual(len(get_outstanding_invoices(MagicMock())["rows"]), 1)

    def test_payment_list_query_is_read_only_and_deterministic(self):
        db = MagicMock()
        db.execute.return_value.mappings.return_value = [{"id": 3}]
        self.assertEqual(list_payments(db), [{"id": 3}])
        self.assertIn("ORDER BY payments.payment_date, payments.id", str(db.execute.call_args.args[0]))
        db.commit.assert_not_called()
        db.add.assert_not_called()

    @patch("app.services.journals.get_journal", return_value={"id": 7, "lines": ["all lines"]})
    @patch("app.services.payments.list_payments", return_value=[{"id": 3}])
    def test_payment_detail_includes_full_journal_and_checks_missing(self, payments, journal):
        db = MagicMock()
        db.scalar.return_value = 7
        result = get_payment(db, 3)
        self.assertEqual(result["journal"]["lines"], ["all lines"])
        journal.assert_called_once_with(db, 7)
        with self.assertRaisesRegex(ValueError, "not found"):
            get_payment(db, 99)
        db.scalar.return_value = None
        with self.assertRaisesRegex(ValueError, "journal is missing"):
            get_payment(db, 3)

    @patch("app.db.SessionLocal")
    @patch("app.cli.get_trial_balance", return_value={"rows": [], "total_debit": D("0"), "total_credit": D("0"), "balanced": True})
    def test_trial_balance_cli(self, report, sessions):
        result = CliRunner().invoke(app, ["accounts", "trial-balance"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Balanced.", result.output)

    @patch("app.db.SessionLocal")
    @patch("app.cli.list_payments", return_value=[])
    def test_empty_payments_cli(self, report, sessions):
        result = CliRunner().invoke(app, ["payments", "list"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No payments found.", result.output)

    @patch("app.db.SessionLocal")
    @patch("app.cli.get_outstanding_invoices", return_value={"rows": [], "currency_totals": {}, "base_total": D("0"), "payables": D("1"), "difference": D("-1")})
    def test_empty_invoice_report_still_flags_unallocated_payables(self, report, sessions):
        result = CliRunner().invoke(app, ["invoices", "outstanding"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("NOT RECONCILED", result.output)
