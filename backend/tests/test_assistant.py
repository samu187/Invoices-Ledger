"""Assistant wiring checks without OpenAI calls or database writes."""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.assistant.agent import query_assistant
from app.assistant.tools import TOOLS, reference_context, run_tool


class AssistantTests(unittest.TestCase):
    def test_reference_context_includes_debit_credit_balances(self):
        rows = [
            {"code": "1000", "name": "HSBC GBP", "account_type": "asset", "balance": Decimal("1234.50")},
            {"code": "2000", "name": "Accounts payable", "account_type": "liability", "balance": Decimal("-80.00")},
            {"code": "1100", "name": "Input VAT", "account_type": "asset", "balance": Decimal("0.00")},
        ]
        with patch("app.assistant.tools.SessionLocal"), \
             patch("app.assistant.tools.suppliers.list_suppliers", return_value=[SimpleNamespace(id=2, name="Demo")]), \
             patch("app.assistant.tools.accounts.list_accounts", return_value=rows):
            context = reference_context()
        self.assertIn("#2 Demo", context)
        self.assertIn("1000 HSBC GBP (asset), GBP 1,234.50 Dr", context)
        self.assertIn("2000 Accounts payable (liability), GBP 80.00 Cr", context)
        self.assertIn("1100 Input VAT (asset), GBP 0.00", context)

    def test_tool_order_and_invoice_validation(self):
        self.assertEqual([tool["name"] for tool in TOOLS], [
            "create_supplier", "create_invoice", "create_payment",
            "list_accounts", "show_account", "show_journal",
            "invoices_list", "invoices_outstanding", "invoices_show", "invoices_payments",
            "payments_list", "payments_show", "list_suppliers", "get_fx_rates",
        ])
        with patch("app.assistant.tools.SessionLocal") as sessions, \
             patch("app.assistant.tools.invoices.create_invoice", return_value={"invoice_id": 5, "journal_id": 9}) as create:
            output = run_tool("create_invoice", {
                "supplier_id": 2, "invoice_number": "A-7", "currency": "GBP",
                "total_amount": "120.00", "expense_account_code": "5000",
            })
            self.assertEqual(json.loads(output), {"invoice_id": 5, "journal_id": 9})
            data = create.call_args.args[1]
            self.assertEqual(data.total_amount.as_tuple().exponent, -2)
            self.assertEqual(data.vat_rate, 20)
            self.assertIs(create.call_args.args[0], sessions.return_value.__enter__.return_value)

    def test_payment_and_read_tools_use_existing_services(self):
        with patch("app.assistant.tools.SessionLocal"), \
             patch("app.assistant.tools.payments.create_payment", return_value={"payment_id": 4}) as create, \
             patch("app.assistant.tools.payments.get_payment", return_value={"id": 4}) as show:
            self.assertEqual(json.loads(run_tool("create_payment", {
                "invoice_id": 1, "currency": "EUR", "amount": "40.00", "exchange_rate": "0.85",
            })), {"payment_id": 4})
            self.assertEqual(create.call_args.args[1].exchange_rate.as_tuple().exponent, -2)
            self.assertEqual(json.loads(run_tool("payments_show", {"payment_id": 4})), {"id": 4})
            show.assert_called_once()
        with self.assertRaises(ValueError):
            run_tool("payments_show", {"payment_id": 0})

    def test_read_tools_dispatch_to_existing_services(self):
        cases = [
            ("list_accounts", {}, "accounts.list_accounts", ()),
            ("show_account", {"code": "1000"}, "accounts.get_account_activity", ("1000",)),
            ("show_journal", {"journal_id": 3}, "journals.get_journal", (3,)),
            ("invoices_list", {}, "invoices.list_invoices", ()),
            ("invoices_outstanding", {}, "invoices.get_outstanding_invoices", ()),
            ("invoices_show", {"invoice_id": 3}, "invoices.get_invoice", (3,)),
            ("invoices_payments", {"invoice_id": 3}, "invoices.get_invoice_payments", (3,)),
            ("payments_list", {}, "payments.list_payments", ()),
            ("payments_show", {"payment_id": 3}, "payments.get_payment", (3,)),
            ("list_suppliers", {}, "suppliers.list_suppliers", ()),
            ("get_fx_rates", {"requested_date": "2026-01-02"}, "fx_rates.get_rates", (date(2026, 1, 2),)),
        ]
        with patch("app.assistant.tools.SessionLocal") as sessions:
            db = sessions.return_value.__enter__.return_value
            for name, arguments, service, expected in cases:
                with self.subTest(name=name), patch("app.assistant.tools." + service,
                                                    return_value={"amount": Decimal("1.23")}) as call:
                    self.assertEqual(json.loads(run_tool(name, arguments)), {"amount": "1.23"})
                    call.assert_called_once_with(db, *expected)

    def test_model_tool_loop_returns_final_answer(self):
        call = SimpleNamespace(type="function_call", name="payments_show",
                               arguments='{"payment_id":4}', call_id="call-1")
        first = SimpleNamespace(output=[call], output_text="")
        second = SimpleNamespace(output=[], output_text="Payment #4 has a GBP 2 FX loss.")
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", return_value='{"id":4,"fx_loss":"2.00"}') as tool, \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.side_effect = [first, second]
            answer = query_assistant("FX on payment 4?", [{"role": "user", "content": "Earlier question"}])
            self.assertIn("GBP 2 FX loss", answer)
            tool.assert_called_once_with("payments_show", {"payment_id": 4})
            follow_up = client.return_value.responses.create.call_args_list[1].kwargs["input"]
            self.assertEqual(follow_up[-1]["type"], "function_call_output")
            self.assertEqual(follow_up[-1]["call_id"], "call-1")

    def test_committed_write_returns_receipt_without_another_model_call(self):
        call = SimpleNamespace(type="function_call", name="create_invoice",
                               arguments='{"supplier_id":2}', call_id="call-2")
        response = SimpleNamespace(output=[call], output_text="")
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", return_value='{"invoice_id":5,"journal_id":9}'), \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.return_value = response
            self.assertEqual(query_assistant("Create invoice"), "Created invoice #5 and journal #9.")
            client.return_value.responses.create.assert_called_once()
