"""Invoice posting checks with mock sessions; no live database writes."""

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from app.cli import app
from app.models import Account, Company, Invoice, JournalEntry, Supplier
from app.schemas import InvoiceCreate
from app.services.invoices import create_invoice


class InvoiceTests(unittest.TestCase):
    def data(self, **changes):
        return InvoiceCreate(**dict(
            supplier_id=1, invoice_number="INV-001", currency="GBP",
            total_amount="120.00", expense_account_code="5400", **changes,
        ))

    def session(self):
        db = MagicMock()
        db.get.side_effect = [Company(id=1, base_currency="GBP"), Supplier(id=1, company_id=1, name="Acme")]
        db.scalar.side_effect = [None, Account(id=5, account_type="expense"),
                                 Account(id=2, account_type="liability"), Account(id=3, account_type="asset")]
        def assign_ids():
            for i, call in enumerate(db.add.call_args_list, 1):
                call.args[0].id = i
        db.flush.side_effect = assign_ids
        return db

    def test_posts_total_net_vat_and_links_invoice(self):
        db = self.session()
        data = self.data()
        result = create_invoice(db, data)
        invoice, journal = [call.args[0] for call in db.add.call_args_list]
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.exchange_rate, Decimal("1"))
        self.assertEqual(invoice.rate_date, data.invoice_date)
        self.assertEqual(journal.invoice_id, invoice.id)
        self.assertEqual(result, {"invoice_id": 1, "journal_id": 2})
        self.assertEqual([(line.account_id, line.debit, line.credit) for line in journal.lines],
                         [(5, Decimal("100"), Decimal("0")), (3, Decimal("20"), Decimal("0")),
                          (2, Decimal("0"), Decimal("120"))])
        db.begin.assert_called_once()

    def test_zero_vat_omits_vat_line(self):
        db = self.session()
        create_invoice(db, self.data(vat_rate="0"))
        journal = db.add.call_args.args[0]
        self.assertEqual(len(journal.lines), 2)
        self.assertEqual(journal.lines[0].debit, Decimal("120.00"))

    def test_rounding_stays_balanced(self):
        db = self.session()
        data = self.data().model_copy(update={"total_amount": Decimal("0.01")})
        create_invoice(db, data)
        journal = db.add.call_args.args[0]
        self.assertEqual(sum(line.debit for line in journal.lines), sum(line.credit for line in journal.lines))
        self.assertTrue(all(line.debit > 0 or line.credit > 0 for line in journal.lines))

    @patch("app.services.invoices.get_rates")
    def test_foreign_invoice_uses_invoice_date_and_stores_applied_rate(self, rates):
        for currency, rate in (("EUR", "0.8"), ("USD", "0.75")):
            db = self.session()
            data = self.data().model_copy(update={"currency": currency, "invoice_date": date(2026, 1, 4)})
            rates.return_value = {"rates": {currency: Decimal(rate)}, "rate_date": date(2026, 1, 2)}
            create_invoice(db, data)
            rates.assert_called_with(db, date(2026, 1, 4))
            invoice, journal = [call.args[0] for call in db.add.call_args_list]
            self.assertEqual(invoice.exchange_rate, Decimal(rate))
            self.assertEqual(invoice.rate_date, date(2026, 1, 2))
            self.assertEqual(invoice.total_amount, Decimal("120"))
            total = Decimal("120") * Decimal(rate)
            self.assertEqual(journal.lines[-1].credit, total)
            self.assertEqual(journal.lines[0].debit, total / Decimal("1.2"))
            self.assertEqual(sum(line.debit for line in journal.lines), total)

    @patch("app.services.invoices.get_rates")
    def test_gbp_never_fetches_rates(self, rates):
        create_invoice(self.session(), self.data())
        rates.assert_not_called()

    @patch("app.services.invoices.get_rates", side_effect=ValueError("FX unavailable"))
    def test_failed_rate_lookup_does_not_save_invoice(self, rates):
        db = self.session()
        with self.assertRaisesRegex(ValueError, "FX unavailable"):
            create_invoice(db, self.data().model_copy(update={"currency": "USD"}))
        db.add.assert_not_called()
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], ValueError)

    def test_compares_company_base_not_hardcoded_currency(self):
        db = self.session()
        db.get.side_effect = [Company(id=2, base_currency="EUR"), Supplier(id=1, company_id=2, name="Acme")]
        data = self.data().model_copy(update={"company_id": 2, "currency": "EUR"})
        create_invoice(db, data)
        self.assertEqual(db.add.call_args_list[0].args[0].exchange_rate, Decimal("1"))

    def test_company_and_supplier_checks(self):
        for records in ([None], [Company(id=1, base_currency="GBP"), None],
                        [Company(id=1, base_currency="GBP"), Supplier(company_id=2)]):
            db = self.session()
            db.get.side_effect = records
            with self.assertRaises(ValueError):
                create_invoice(db, self.data())
            db.add.assert_not_called()

    def test_duplicate_or_wrong_account_rejected(self):
        for results in ([99], [None, Account(account_type="asset"), Account(account_type="liability")],
                        [None, Account(account_type="expense"), None],
                        [None, Account(account_type="expense"), Account(account_type="liability"), None]):
            db = self.session()
            db.scalar.side_effect = results
            with self.assertRaises(ValueError):
                create_invoice(db, self.data())
            db.add.assert_not_called()

    def test_journal_failure_rolls_back_same_transaction(self):
        db = self.session()
        db.flush.side_effect = [None, IntegrityError("journal", {}, Exception("failure"))]
        with self.assertRaises(IntegrityError):
            create_invoice(db, self.data())
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], IntegrityError)
        db.commit.assert_not_called()

    @patch("app.db.SessionLocal")
    @patch("app.cli.create_invoice", return_value={"invoice_id": 8, "journal_id": 12})
    def test_cli_defaults_and_links(self, create, sessions):
        result = CliRunner().invoke(app, ["invoices", "add", "--supplier", "1", "--number", "INV-001",
                                        "--currency", "GBP", "--total", "120", "--expense-account", "5400"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(create.call_args.args[1].company_id, 1)
        self.assertEqual(create.call_args.args[1].vat_rate, Decimal("20"))
        self.assertIn("invoice #8 and journal #12", result.output)
