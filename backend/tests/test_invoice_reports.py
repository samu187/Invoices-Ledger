"""Invoice balances and journal detail, without live database access."""

from datetime import date
from decimal import Decimal as D
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from app.cli import app
from app.models import Company, Invoice, Supplier
from app.services.invoices import invoice_summary, get_invoice, list_invoices


class InvoiceReportTests(unittest.TestCase):
    def summary(self, paid="50.00"):
        db = MagicMock()
        db.get.side_effect = [Supplier(company_id=1, name="Acme"), Company(id=1, base_currency="GBP")]
        db.scalar.return_value = D(paid)
        db.execute.return_value.mappings.return_value = [
            dict(kind=kind, code=code, name=name, account_type=type_, debit=D(debit), credit=D(credit))
            for kind, code, name, type_, debit, credit in [
                ("invoice", "5400", "Software", "expense", "85", "0"),
                ("invoice", "1100", "VAT", "asset", "17", "0"),
                ("invoice", "2000", "Payables", "liability", "0", "102"),
                ("payment", "2000", "Payables", "liability", "42.50", "0"),
                ("payment", "5900", "FX loss", "expense", "0.50", "0"),
                ("payment", "1000", "HSBC", "asset", "0", "43"),
            ]
        ]
        invoice = Invoice(id=8, supplier_id=1, invoice_number="INV-8", invoice_date=date(2026, 1, 1),
                          currency="USD", total_amount=D("120"), vat_rate=D("20"), exchange_rate=D("0.85"), rate_date=date(2026, 1, 1))
        return invoice_summary(db, invoice)

    def test_foreign_balance_uses_payments_and_base_uses_journals(self):
        report = self.summary()
        self.assertEqual(report['paid'], D("50"))
        self.assertEqual(report['balance'], D("70"))
        self.assertEqual(report['base_balance'], D("59.50"))
        self.assertEqual(report['base_total'], D("102"))
        self.assertEqual(report['base_net'], D("85"))  # Does not include payment FX expense.
        self.assertEqual(report['base_vat'], D("17"))
        self.assertEqual(report['expense_accounts'], ["5400 - Software"])

    def test_unpaid_and_fully_paid_original_balances(self):
        self.assertEqual(self.summary("0")['balance'], D("120"))
        self.assertEqual(self.summary("120")['balance'], D("0"))

    def test_missing_invoice(self):
        db = MagicMock()
        db.get.return_value = None
        with self.assertRaisesRegex(ValueError, "Invoice 99 not found"):
            get_invoice(db, 99)

    @patch('app.services.invoices.invoice_summary')
    @patch('app.services.journals.get_journal')
    def test_detail_includes_each_linked_journal(self, journal, summary):
        db = MagicMock()
        summary.return_value = {'id': 8}
        db.scalars.return_value.all.return_value = [4, 9]
        journal.side_effect = [{'id': 4}, {'id': 9}]
        report = get_invoice(db, 8)
        self.assertEqual(report['journals'], [{'id': 4}, {'id': 9}])
        sql = str(db.scalars.call_args.args[0])
        self.assertIn('journal_entries.invoice_id =', sql)
        db.commit.assert_not_called()

    @patch('app.db.SessionLocal')
    @patch('app.cli.list_invoices')
    def test_list_summary_has_balances_without_lines(self, listing, sessions):
        listing.return_value = [self.summary()]
        result = CliRunner().invoke(app, ['invoices', 'list'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('balance 70.00', result.output)
        self.assertIn('net 85.00', result.output)
        self.assertNotIn('Debit GBP', result.output)

    @patch('app.db.SessionLocal')
    @patch('app.cli.get_invoice')
    def test_show_renders_journal_lines(self, get, sessions):
        report = self.summary()
        report['journals'] = [dict(id=4, posting_date=date(2026, 1, 1), kind='invoice', description='INV-8', invoice_id=8, payment_id=None,
            lines=[dict(code='5400', name='Software', debit=D('85'), credit=D('0'))], total_debit=D('85'), total_credit=D('0'))]
        get.return_value = report
        result = CliRunner().invoke(app, ['invoices', 'show', '8'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('Journal #4', result.output)
        self.assertIn('Debit GBP', result.output)
        self.assertIn('TOTAL', result.output)

    def test_empty_list(self):
        db = MagicMock()
        db.scalars.return_value.all.return_value = []
        self.assertEqual(list_invoices(db), [])
