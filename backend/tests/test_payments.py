"""Payment accounting checks with mock sessions; no live database access."""

from datetime import date
from decimal import Decimal as D
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from app.cli import app
from app.models import Account, Company, Invoice, Supplier
from app.schemas import PaymentCreate
from app.services.payments import create_payment


class PaymentTests(unittest.TestCase):
    def data(self, **changes):
        return PaymentCreate(**(dict(invoice_id=1, currency="GBP", amount="40") | changes))

    def session(self, currency="GBP", total="100", original="100", paid="0", remaining=None):
        db = MagicMock()
        invoice = Invoice(id=1, supplier_id=1, invoice_number="INV1", currency=currency,
                          total_amount=D(total), invoice_date=date(2026, 1, 1))
        db.scalar.side_effect = [invoice, None, D(paid), None, D(original), D(remaining or original)]
        db.get.side_effect = [Supplier(company_id=1), Company(id=1, base_currency="GBP")]
        db.scalars.return_value.all.return_value = [
            Account(id=int(code), code=code, account_type=kind) for code, kind in
            (("1000", "asset"), ("2000", "liability"), ("5200", "expense"),
             ("5900", "expense"), ("4900", "income"))]
        def flush():
            for i, call in enumerate(db.add.call_args_list, 1):
                call.args[0].id = i
        db.flush.side_effect = flush
        return db

    def postings(self, db):
        journal = db.add.call_args_list[-1].args[0]
        self.assertEqual(sum(line.debit for line in journal.lines), sum(line.credit for line in journal.lines))
        self.assertTrue(all((line.debit > 0) != (line.credit > 0) for line in journal.lines))
        return {line.account_id: (line.debit, line.credit) for line in journal.lines}

    def test_gbp_defaults_and_fees(self):
        db = self.session()
        result = create_payment(db, self.data(bank_fees="2"))
        self.assertEqual(self.postings(db), {1000: (0, D("42")), 2000: (D("40"), 0), 5200: (D("2"), 0)})
        payment = db.add.call_args_list[0].args[0]
        self.assertEqual(payment.exchange_rate, 1)
        self.assertEqual(payment.base_amount, 40)
        self.assertEqual(result["bank_total"], 42)
        self.assertEqual(db.add.call_args_list[1].args[0].payment_id, payment.id)
        self.assertIn("FOR UPDATE", str(db.scalar.call_args_list[0].args[0]))

    def test_foreign_partial_loss_and_fee_separate(self):
        db = self.session(currency="USD", original="85")
        create_payment(db, self.data(currency="USD", exchange_rate="0.875", bank_fees="2"))
        self.assertEqual(self.postings(db), {1000: (0, D("37")), 2000: (D("34"), 0),
                                           5200: (D("2"), 0), 5900: (D("1"), 0)})

    def test_foreign_gain(self):
        db = self.session(currency="EUR", original="85")
        create_payment(db, self.data(currency="EUR", exchange_rate="0.8"))
        self.assertEqual(self.postings(db), {1000: (0, D("32")), 2000: (D("34"), 0), 4900: (0, D("2"))})

    def test_tiny_liability_release_omits_zero_journal_line(self):
        db = self.session(currency="USD", total="100", original="1")
        create_payment(db, self.data(currency="USD", amount="0.01", exchange_rate="1"))
        self.assertEqual(self.postings(db), {1000: (0, D("0.01")), 5900: (D("0.01"), 0)})

    def test_cumulative_rounding_final_payment_clears_liability(self):
        remaining = D("1.00")
        for paid, expected in (("0", "0.33"), ("1", "0.34"), ("2", "0.33")):
            db = self.session(currency="USD", total="3", original="1", paid=paid, remaining=str(remaining))
            create_payment(db, self.data(currency="USD", amount="1", exchange_rate="0.34"))
            released = self.postings(db)[2000][0]
            self.assertEqual(released, D(expected))
            remaining -= released
        self.assertEqual(remaining, 0)

    def test_invalid_currency_rate_overpayment_dates(self):
        for changes, currency, paid, message in (
            ({"currency": "USD"}, "GBP", "0", "must match"),
            ({"exchange_rate": "2"}, "GBP", "0", "rate 1"),
            ({"currency": "USD"}, "USD", "0", "Supply --exchange-rate"),
            ({}, "GBP", "80", "exceeds"),
            ({"payment_date": "2025-12-31"}, "GBP", "0", "before"),
        ):
            db = self.session(currency=currency, paid=paid)
            with self.assertRaisesRegex(ValueError, message):
                create_payment(db, self.data(**changes))
            db.add.assert_not_called()

    def test_duplicate_request_rejected(self):
        db = self.session()
        invoice = db.scalar.side_effect.__next__()
        db.scalar.side_effect = [invoice, 99]
        with self.assertRaisesRegex(ValueError, "already been recorded"):
            create_payment(db, self.data())
        db.add.assert_not_called()

    def test_schema_invalid_amount_fee_bank(self):
        for changes in ({"amount": "0"}, {"bank_fees": "-1"}, {"bank_account_code": "1100"}, {"amount": "1.001"}):
            with self.assertRaises(ValidationError):
                self.data(**changes)

    def test_failure_exits_transaction_with_error(self):
        db = self.session()
        db.flush.side_effect = [None, IntegrityError("journal", {}, Exception("failure"))]
        with self.assertRaises(IntegrityError):
            create_payment(db, self.data())
        self.assertIs(db.begin.return_value.__exit__.call_args.args[0], IntegrityError)
        db.commit.assert_not_called()

    @patch("app.db.SessionLocal")
    @patch("app.cli.create_payment", return_value={"payment_id": 1, "journal_id": 2, "bank_total": D("40")})
    def test_cli(self, create, sessions):
        result = CliRunner().invoke(app, ["payments", "add", "--invoice", "1", "--currency", "gbp", "--amount", "40"])
        self.assertEqual(result.exit_code, 0, result.output)
        data = create.call_args.args[1]
        self.assertEqual(data.bank_fees, 0)
        self.assertEqual(data.bank_account_code, "1000")
        self.assertIsNone(data.exchange_rate)
        self.assertIn("Paid from HSBC: GBP 40.00", result.output)
