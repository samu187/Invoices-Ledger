"""Invoice input validation, without database or exchange-rate requests."""

from datetime import date, timedelta
from decimal import Decimal
import unittest

from pydantic import ValidationError

from app.schemas import InvoiceCreate


class InvoiceSchemaTests(unittest.TestCase):
    def data(self, **changes):
        return {"supplier_id": 1, "invoice_number": " INV-001 ", "invoice_date": "2026-01-01",
                "currency": "USD", "expense_account_code": "5400", "total_amount": "120.00", **changes}

    def test_valid_input_uses_decimal_and_trims_number(self):
        invoice = InvoiceCreate(**self.data())
        self.assertEqual(invoice.invoice_number, "INV-001")
        self.assertEqual(invoice.total_amount, Decimal("120.00"))
        self.assertEqual(invoice.vat_rate, Decimal("20.00"))
        self.assertEqual(invoice.invoice_date, date(2026, 1, 1))
        self.assertEqual(InvoiceCreate(**self.data(vat_rate="0")).vat_rate, Decimal("0"))
        self.assertEqual(InvoiceCreate(**self.data(vat_rate="5")).vat_rate, Decimal("5"))

    def test_date_defaults_to_today_when_omitted(self):
        data = self.data()
        del data["invoice_date"]
        self.assertEqual(InvoiceCreate(**data).invoice_date, date.today())

    def test_invalid_invoice_input(self):
        cases = [
            {"supplier_id": 0}, {"invoice_number": " "}, {"expense_account_code": ""},
            {"currency": "JPY"}, {"invoice_date": date.today() + timedelta(days=1)},
            {"total_amount": "-1"}, {"vat_rate": "-1"}, {"total_amount": "0"},
            {"total_amount": "1.001"}, {"total_amount": "NaN"}, {"vat_rate": "Infinity"},
            {"total_amount": "10000000000000000.00"}, {"vat_rate": "100.01"},
            {"exchange_rate": "0.85"}, {"net_amount": "100.00"}, {"vat_amount": "20.00"},
            {"base_total_amount": "102.00"}, {"base_net_amount": "85.00"}, {"base_vat_amount": "17.00"},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                InvoiceCreate(**self.data(**change))

    def test_total_and_currency_are_required(self):
        for field in ("total_amount", "currency"):
            data = self.data()
            del data[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                InvoiceCreate(**data)
