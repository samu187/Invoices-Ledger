"""Assistant tool definitions and calls into existing accounting services."""

import json
from datetime import date

from pydantic import BaseModel

from app.db import SessionLocal
from app.schemas import InvoiceCreate, PaymentCreate, SupplierCreate
from app.services import accounts, fx_rates, invoices, journals, payments, suppliers


def _tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "type": "function", "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {},
                       "required": required or [], "additionalProperties": False},
        "strict": True,
    }


def _create_tool(name: str, description: str, schema: type[BaseModel]) -> dict:
    # The same Pydantic schema validates API, CLI and assistant writes. Defaults in
    # these models do not meet OpenAI's strict-tool requirements, so validate again locally.
    return {"type": "function", "name": name, "description": description,
            "parameters": schema.model_json_schema(), "strict": False}


_ID = {"type": "integer", "description": "Positive database record ID."}
_CODE = {"type": "string", "description": "Account code, for example 1000 or 5900."}

TOOLS = [
    # Create actions first.
    _create_tool("create_supplier", "Create a supplier. Only call when the user clearly asks to save one.", SupplierCreate),
    _create_tool("create_invoice", "Record a VAT-inclusive supplier invoice and its GBP journal. Use a supplier ID and expense account code from the current lists. Only call when required facts are known.", InvoiceCreate),
    _create_tool("create_payment", "Record a full or partial payment and its journal. Amount is in invoice currency; EUR/USD payments require the actual GBP-per-unit settlement rate. Only call when required facts are known.", PaymentCreate),
    # Accounts and journals.
    _tool("list_accounts", "List account codes, names, types and current GBP balances."),
    _tool("show_account", "Show dated account activity and running GBP balance.", {"code": _CODE}, ["code"]),
    _tool("show_journal", "Show every debit and credit line in a journal entry.", {"journal_id": _ID}, ["journal_id"]),
    # Invoice queries.
    _tool("invoices_list", "List invoices with supplier IDs, original amounts, rates, and balances."),
    _tool("invoices_outstanding", "Show outstanding invoices by currency and GBP payables reconciliation."),
    _tool("invoices_show", "Show an invoice and all linked journals.", {"invoice_id": _ID}, ["invoice_id"]),
    _tool("invoices_payments", "Show an invoice's payment statement with running original and GBP payable balances.", {"invoice_id": _ID}, ["invoice_id"]),
    # Payment queries.
    _tool("payments_list", "List payments, settlement amounts, rates and bank fees."),
    _tool("payments_show", "Show a payment and its linked journal, including realised FX gain/loss lines.", {"payment_id": _ID}, ["payment_id"]),
    # Suppliers and FX.
    _tool("list_suppliers", "List supplier names and IDs."),
    _tool("get_fx_rates", "Get GBP-per-unit BoE reference rates for GBP, EUR and USD for a date; may cache the published set. This is not the actual bank settlement rate.",
          {"requested_date": {"type": "string", "description": "Date in YYYY-MM-DD format."}}, ["requested_date"]),
]


def _positive_id(arguments: dict, key: str) -> int:
    value = arguments[key]
    if type(value) is not int or value <= 0:
        raise ValueError(f"{key} must be a positive integer.")
    return value


def run_tool(name: str, arguments: dict) -> str:
    """Execute one allowed tool in its own session; return JSON to the model."""
    if not isinstance(arguments, dict) or name not in {tool["name"] for tool in TOOLS}:
        raise ValueError("Unknown assistant tool or arguments.")

    with SessionLocal() as db:
        if name == "create_supplier":
            result = suppliers.create_supplier(db, SupplierCreate.model_validate(arguments))
        elif name == "create_invoice":
            result = invoices.create_invoice(db, InvoiceCreate.model_validate(arguments))
        elif name == "create_payment":
            result = payments.create_payment(db, PaymentCreate.model_validate(arguments))
        elif name == "list_accounts":
            result = accounts.list_accounts(db)
        elif name == "show_account":
            result = accounts.get_account_activity(db, arguments["code"])
        elif name == "show_journal":
            result = journals.get_journal(db, _positive_id(arguments, "journal_id"))
        elif name == "invoices_list":
            result = invoices.list_invoices(db)
        elif name == "invoices_outstanding":
            result = invoices.get_outstanding_invoices(db)
        elif name == "invoices_show":
            result = invoices.get_invoice(db, _positive_id(arguments, "invoice_id"))
        elif name == "invoices_payments":
            result = invoices.get_invoice_payments(db, _positive_id(arguments, "invoice_id"))
        elif name == "payments_list":
            result = payments.list_payments(db)
        elif name == "payments_show":
            result = payments.get_payment(db, _positive_id(arguments, "payment_id"))
        elif name == "list_suppliers":
            result = suppliers.list_suppliers(db)
        else:
            result = fx_rates.get_rates(db, date.fromisoformat(arguments["requested_date"]))

    return json.dumps(result, default=lambda value: value.model_dump(mode="json") if isinstance(value, BaseModel) else str(value))


def reference_context() -> str:
    """Give the model current IDs and valid account codes at the start of a query."""
    with SessionLocal() as db:
        supplier_rows = suppliers.list_suppliers(db)
        account_rows = accounts.list_accounts(db)
    supplier_names = ", ".join(f"#{row.id} {row.name}" for row in supplier_rows) or "none"
    account_names = ", ".join(
        f"{row['code']} {row['name']} ({row['account_type']}), "
        f"GBP {abs(row['balance']):,.2f} "
        f"{('Dr' if row['balance'] > 0 else 'Cr') if row['balance'] != 0 else ''}".rstrip()
        for row in account_rows
    ) or "none"
    return f"Current suppliers: {supplier_names}.\nCurrent accounts: {account_names}."
