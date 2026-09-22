"""Read-only payment statement checks without a live database."""

from datetime import date
from decimal import Decimal as D
import unittest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from app.cli import app
from app.models import Company, Invoice, Supplier, Payment
from app.services.invoices import get_invoice_payments


class InvoicePaymentTests(unittest.TestCase):
    def session(self, payments=True):
        db = MagicMock()
        db.get.side_effect = [Invoice(id=8, supplier_id=1, invoice_number="INV-8", invoice_date=date(2026, 1, 1), currency="USD", total_amount=D("100")),
                              Supplier(company_id=1), Company(id=1, base_currency="GBP")]
        postings = [{"kind": "invoice", "payment_id": None, "movement": D("85")}]
        rows = []
        if payments:
            postings += [{"kind": "payment", "payment_id": 3, "movement": D("-42.50")},
                         {"kind": "payment", "payment_id": 4, "movement": D("-42.50")}]
            rows = [Payment(id=3, payment_date=date(2026, 1, 2), amount=D("50"), base_amount=D("43")),
                    Payment(id=4, payment_date=date(2026, 1, 3), amount=D("50"), base_amount=D("44"))]
        db.execute.return_value.mappings.return_value = postings
        db.scalars.return_value.all.return_value = rows
        return db

    def test_full_settlement_uses_payables_not_cash(self):
        db = self.session()
        report = get_invoice_payments(db, 8)
        self.assertEqual([r['balance'] for r in report['rows']], [D('100'), D('50'), D('0')])
        self.assertEqual([r['base_balance'] for r in report['rows']], [D('85'), D('42.50'), D('0')])
        self.assertEqual([r['payables'] for r in report['rows']], [D('85'), D('-42.50'), D('-42.50')])
        db.commit.assert_not_called()
        sql = str(db.scalars.call_args.args[0])
        self.assertIn('ORDER BY payments.payment_date, payments.id', sql)

    def test_unpaid_invoice_still_has_initial_row(self):
        report = get_invoice_payments(self.session(False), 8)
        self.assertEqual(len(report['rows']), 1)
        self.assertEqual(report['balance'], D('100'))
        self.assertEqual(report['base_balance'], D('85'))

    def test_partial_payment(self):
        db = self.session()
        db.scalars.return_value.all.return_value = db.scalars.return_value.all.return_value[:1]
        report = get_invoice_payments(db, 8)
        self.assertEqual(report['balance'], D('50'))
        self.assertEqual(report['base_balance'], D('42.50'))

    def test_missing_invoice(self):
        db = MagicMock()
        db.get.return_value = None
        with self.assertRaisesRegex(ValueError, 'Invoice 99 not found'):
            get_invoice_payments(db, 99)

    def test_zero_rounded_release_keeps_base_balance(self):
        db = self.session()
        db.execute.return_value.mappings.return_value = [
            {"kind": "invoice", "payment_id": None, "movement": D("85")},
            {"kind": "payment", "payment_id": 3, "movement": D("0")},
        ]
        db.scalars.return_value.all.return_value = [Payment(id=3, payment_date=date(2026, 1, 2), amount=D("0.01"))]
        report = get_invoice_payments(db, 8)
        self.assertEqual(report["balance"], D("99.99"))
        self.assertEqual(report["base_balance"], D("85"))
        self.assertEqual(report["rows"][-1]["payables"], 0)

    def test_missing_journal_is_not_silently_zero(self):
        for postings in ([], [{"kind": "invoice", "payment_id": None, "movement": D("85")}]):
            db = self.session()
            db.execute.return_value.mappings.return_value = postings
            with self.assertRaisesRegex(ValueError, 'posting is missing'):
                get_invoice_payments(db, 8)

    @patch('app.db.SessionLocal')
    @patch('app.cli.get_invoice_payments')
    def test_cli_table_and_final_balance(self, get, sessions):
        get.return_value = get_invoice_payments(self.session(), 8)
        result = CliRunner().invoke(app, ['invoices', 'payments', '8'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('Payment #3', result.output)
        self.assertIn('Payables', result.output)
        self.assertIn('Final balance: 0.00 USD | Base payables: 0.00 GBP', result.output)
