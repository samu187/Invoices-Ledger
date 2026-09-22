"""HTTP contract checks; dependency overrides avoid live database access."""

from datetime import date, datetime, timezone
from decimal import Decimal as D
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        app.dependency_overrides[get_db] = lambda: self.db
        self.addCleanup(app.dependency_overrides.clear)
        # No lifespan: database startup is tested separately with mocks.
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def invoice(self):
        return dict(id=1, supplier_id=1, number="INV1", date=date(2026, 1, 2), supplier="Demo", company_id=1,
                    currency="USD", total=D("120.00"), paid=D("0"), balance=D("120.00"),
                    vat_rate=D("20"), exchange_rate=D("0.85"), rate_date=date(2026, 1, 2),
                    base_currency="GBP", base_net=D("85"), base_vat=D("17"), base_total=D("102"),
                    base_balance=D("102"), expense_accounts=["5000 - General expenses"], has_invoice_posting=True)

    def test_suppliers_create_and_list(self):
        supplier = dict(id=1, company_id=1, name="Demo", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with patch("app.api.routes.suppliers.create_supplier", return_value=supplier) as create:
            response = self.client.post("/api/suppliers", json={"name": "Demo"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(create.call_args.args[1].name, "Demo")
        with patch("app.api.routes.suppliers.list_suppliers", return_value=[supplier]):
            self.assertEqual(self.client.get("/api/suppliers").json()[0]["name"], "Demo")

    def test_invoice_create_preserves_supplied_date(self):
        with patch("app.api.routes.invoices.create_invoice", return_value={"invoice_id": 1, "journal_id": 2}) as create:
            response = self.client.post("/api/invoices", json=dict(supplier_id=1, invoice_number="INV1",
                invoice_date="2026-01-02", currency="USD", total_amount="120.00", expense_account_code="5000"))
            self.assertEqual(response.status_code, 201, response.text)
            data = create.call_args.args[1]
            self.assertEqual(data.invoice_date, date(2026, 1, 2))
            self.assertEqual(data.total_amount, D("120.00"))
            self.assertEqual(data.vat_rate, 20)

    def test_invoice_list_and_detail_decimal_serialization(self):
        with patch("app.api.routes.invoices.list_invoices", return_value=[self.invoice()]) as listing:
            response = self.client.get("/api/invoices?company_id=1")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()[0]["total"], "120.00")
            listing.assert_called_once_with(self.db, 1)
        with patch("app.api.routes.invoices.get_invoice", return_value={**self.invoice(), "journals": []}):
            response = self.client.get("/api/invoices/1")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["journals"], [])

    def test_invoice_payment_statement(self):
        report = dict(id=1, number="INV1", currency="USD", total=D("120"), base_currency="GBP",
                      rows=[dict(date=date(2026, 1, 2), reference="Invoice #1", amount=D("120"),
                                 balance=D("120"), payables=D("102"), base_balance=D("102"))],
                      balance=D("120"), base_balance=D("102"))
        with patch("app.api.routes.invoices.get_invoice_payments", return_value=report):
            response = self.client.get("/api/invoices/1/payments")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["rows"][0]["payables"], "102")

    def test_payment_create(self):
        with patch("app.api.routes.payments.create_payment", return_value=dict(payment_id=1, journal_id=2, bank_total=D("36.00"))) as create:
            response = self.client.post("/api/payments", json=dict(invoice_id=1, currency="USD", amount="40",
                                         exchange_rate="0.85", bank_fees="2"))
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["bank_total"], "36.00")
            self.assertEqual(create.call_args.args[1].bank_fees, D("2"))

    def test_validation_and_missing_invoice(self):
        with patch("app.api.routes.payments.create_payment") as create:
            self.assertEqual(self.client.post("/api/payments", json={"amount": -1}).status_code, 422)
            create.assert_not_called()
        self.assertEqual(self.client.get("/api/invoices/0").status_code, 422)
        self.db.get.return_value = None
        for url in ("/api/invoices/99", "/api/invoices/99/payments"):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_business_and_database_errors(self):
        with patch("app.api.routes.suppliers.list_suppliers", side_effect=ValueError("Company missing")):
            response = self.client.get("/api/suppliers")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], "Company missing")
        with patch("app.api.routes.suppliers.list_suppliers", side_effect=SQLAlchemyError("secret connection")):
            response = self.client.get("/api/suppliers")
            self.assertEqual(response.status_code, 500)
            self.assertNotIn("secret", response.text)

    def test_openapi_lists_report_operations(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertEqual(sum(len(methods) for methods in paths.values()), 17)

    def test_static_report_paths_and_empty_results(self):
        cases = [
            ("/api/invoices/outstanding", "invoices.get_outstanding_invoices",
             dict(rows=[], currency_totals={"USD": D("40")}, base_total=D("34"), payables=D("34"), difference=D("0"))),
            ("/api/accounts/trial-balance", "accounts.get_trial_balance",
             dict(rows=[], total_debit=D("0"), total_credit=D("0"), balanced=True)),
            ("/api/accounts", "accounts.list_accounts", []),
            ("/api/payments", "payments.list_payments", []),
            ("/api/journals", "journals.list_journals", []),
        ]
        for url, service, report in cases:
            with self.subTest(url=url), patch("app.api.routes." + service, return_value=report) as get:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.text)
                get.assert_called_once_with(self.db)
                if "outstanding" in url:
                    self.assertEqual(response.json()["currency_totals"]["USD"], "40")

    def test_journal_and_payment_details(self):
        journal = dict(id=2, posting_date=date(2026, 1, 2), kind="payment", description="Payment",
                       invoice_id=1, payment_id=1, total_debit=D("10"), total_credit=D("10"),
                       lines=[dict(code="2000", name="Payables", debit=D("10"), credit=D("0")),
                              dict(code="1000", name="HSBC", debit=D("0"), credit=D("10"))])
        payment = dict(id=1, payment_date=date(2026, 1, 2), invoice_id=1, invoice_number="INV1",
                       supplier="Demo", currency="GBP", amount=D("10"), bank_code="1000", bank_name="HSBC",
                       exchange_rate=D("1"), base_amount=D("10"), bank_fee=D("0"), bank_total=D("10"),
                       reference=None, journal=journal)
        with patch("app.api.routes.journals.get_journal", return_value=journal):
            response = self.client.get("/api/journals/2")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()["lines"]), 2)
        with patch("app.api.routes.payments.get_payment", return_value=payment):
            response = self.client.get("/api/payments/1")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["journal"]["total_credit"], "10")

    def test_account_detail_and_missing_resources(self):
        report = dict(code="1000", name="HSBC", account_type="asset", balance=D("50"), transactions=[])
        with patch("app.api.routes.accounts.get_account_activity", return_value=report):
            response = self.client.get("/api/accounts/1000")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["balance"], "50")
        self.db.get.return_value = None
        self.db.scalar.return_value = None
        for url in ("/api/accounts/missing", "/api/payments/99", "/api/journals/99"):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_pnl_date_validation(self):
        with patch("app.api.routes.accounts.get_profit_and_loss", return_value=dict(rows=[], profit=D("0"))) as get:
            response = self.client.get("/api/accounts/pnl?from=2026-01-01&to=2026-01-31")
            self.assertEqual(response.status_code, 200, response.text)
            get.assert_called_once_with(self.db, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(self.client.get("/api/accounts/pnl?from=bad&to=2026-01-31").status_code, 422)
        self.assertEqual(self.client.get("/api/accounts/pnl?from=2026-02-01&to=2026-01-31").status_code, 400)

    def test_input_vat_month_uses_static_path_and_serializes_balances(self):
        report = dict(month="2026-01", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
                      code="1100", name="Input VAT", account_type="asset", opening_balance=D("5"),
                      debits=D("20"), credits=D("0"), net_movement=D("20"), closing_balance=D("25"),
                      transactions=[])
        with patch("app.api.routes.accounts.get_input_vat_month", return_value=report) as get:
            response = self.client.get("/api/accounts/input-vat?month=2026-01")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["closing_balance"], "25")
            get.assert_called_once_with(self.db, date(2026, 1, 1))
        self.assertEqual(self.client.get("/api/accounts/input-vat?month=2026-13").status_code, 422)
