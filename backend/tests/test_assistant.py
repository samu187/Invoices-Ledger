"""Assistant wiring checks without OpenAI calls or database writes."""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openai import OpenAIError
from typer.testing import CliRunner

from app.assistant.agent import query_assistant
from app.assistant.tools import TOOLS, reference_context, run_tool
from app.cli import app as cli
from app.main import app
from app.schemas import AssistantReply


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
            self.assertIn("GBP 2 FX loss", answer.reply)
            self.assertEqual(answer.created_count, 0)
            tool.assert_called_once_with("payments_show", {"payment_id": 4})
            follow_up = client.return_value.responses.create.call_args_list[1].kwargs["input"]
            self.assertEqual(follow_up[-1]["type"], "function_call_output")
            self.assertEqual(follow_up[-1]["call_id"], "call-1")

    def test_multiple_creates_are_reported_after_final_model_answer(self):
        calls = [SimpleNamespace(type="function_call", name="create_invoice",
                                 arguments=json.dumps({"invoice_number": f"A-{number}"}), call_id=f"call-{number}")
                 for number in (1, 2, 3)]
        responses = [SimpleNamespace(output=[call], output_text="") for call in calls]
        responses.append(SimpleNamespace(output=[], output_text="I recorded all three invoices."))
        outputs = [json.dumps({"invoice_id": number, "journal_id": number + 10}) for number in (1, 2, 3)]
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", side_effect=outputs) as tool, \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.side_effect = responses
            answer = query_assistant("Create three invoices")
            self.assertEqual(answer.created_count, 3)
            self.assertIn("Invoice #1, journal #11", answer.reply)
            self.assertIn("Invoice #3, journal #13", answer.reply)
            self.assertIn("I recorded all three invoices.", answer.reply)
            self.assertEqual(tool.call_count, 3)
            self.assertEqual(client.return_value.responses.create.call_count, 4)

    def test_model_failure_after_create_still_reports_saved_record(self):
        call = SimpleNamespace(type="function_call", name="create_supplier",
                               arguments='{"name":"Demo"}', call_id="call-1")
        response = SimpleNamespace(output=[call], output_text="")
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", return_value='{"id":7,"name":"Demo"}'), \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.side_effect = [response, OpenAIError("connection lost")]
            answer = query_assistant("Create supplier Demo")
            self.assertEqual(answer.created_count, 1)
            self.assertIn("Supplier #7: Demo", answer.reply)
            self.assertIn("could not finish", answer.reply)

    def test_partial_failure_and_duplicate_create(self):
        first = SimpleNamespace(type="function_call", name="create_invoice",
                                arguments='{"invoice_number":"A-1"}', call_id="call-1")
        duplicate = SimpleNamespace(type="function_call", name="create_invoice",
                                    arguments='{"invoice_number":"A-1"}', call_id="call-2")
        failed = SimpleNamespace(type="function_call", name="create_invoice",
                                 arguments='{"invoice_number":"A-2"}', call_id="call-3")
        responses = [SimpleNamespace(output=[call], output_text="") for call in (first, duplicate, failed)]
        responses.append(SimpleNamespace(output=[], output_text="The second invoice could not be saved."))
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", side_effect=['{"invoice_id":1,"journal_id":11}', ValueError("Duplicate invoice")]) as tool, \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.side_effect = responses
            answer = query_assistant("Create two invoices")
            self.assertEqual(answer.created_count, 1)
            self.assertIn("Invoice #1, journal #11", answer.reply)
            self.assertIn("Failed attempts (1)", answer.reply)
            self.assertIn("Invoice A-2: Duplicate invoice", answer.reply)
            self.assertIn("Duplicate invoice", answer.reply)
            self.assertEqual(tool.call_count, 2)

    def test_create_limit_prevents_sixth_write(self):
        responses = [SimpleNamespace(output=[SimpleNamespace(
            type="function_call", name="create_supplier", arguments=json.dumps({"name": f"Supplier {number}"}),
            call_id=f"call-{number}")], output_text="") for number in range(6)]
        responses.append(SimpleNamespace(output=[], output_text="Five suppliers were saved."))
        outputs = [json.dumps({"id": number + 1, "name": f"Supplier {number}"}) for number in range(5)]
        with patch("app.assistant.agent.reference_context", return_value="Current lists"), \
             patch("app.assistant.agent.run_tool", side_effect=outputs) as tool, \
             patch("app.assistant.agent.OpenAI") as client:
            client.return_value.responses.create.side_effect = responses
            answer = query_assistant("Create six suppliers")
            self.assertEqual(answer.created_count, 5)
            self.assertIn("Supplier name 'Supplier 5': Limit of 5", answer.reply)
            self.assertEqual(tool.call_count, 5)

    def test_api_exposes_reply_and_created_count(self):
        with patch.dict("os.environ", {"ADMIN_USERNAME": "test", "ADMIN_PASSWORD": "test"}), \
             patch("app.api.routes.query_assistant", return_value=AssistantReply(reply="Saved", created_count=2)):
            response = TestClient(app).post("/api/assistant/query", json={"query": "Create records"}, auth=("test", "test"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"reply": "Saved", "created_count": 2})

    def test_cli_prints_assistant_reply(self):
        with patch("app.cli.query_assistant", return_value=AssistantReply(reply="Saved two invoices.", created_count=2)):
            result = CliRunner().invoke(cli, ["assistant", "Create two invoices"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Saved two invoices.", result.output)
