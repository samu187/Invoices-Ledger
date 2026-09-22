"""CLI input and output; business logic lives in services."""

import os
import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.schemas import SupplierCreate, InvoiceCreate
from app.services.suppliers import create_supplier, list_suppliers
from app.services.accounts import list_accounts, get_account_activity
from app.services.journals import list_journals, get_journal
from app.services.invoices import create_invoice, list_invoices, get_invoice


app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)

suppliers = typer.Typer(help="Create and list suppliers.", no_args_is_help=True)
app.add_typer(suppliers, name="suppliers")

accounts = typer.Typer(help="View account balances and transactions in GBP.", no_args_is_help=True)
app.add_typer(accounts, name="accounts")

journals = typer.Typer(help="Browse journals and inspect full entries.", no_args_is_help=True)
app.add_typer(journals, name="journals")

invoices = typer.Typer(help="Record supplier invoices.", no_args_is_help=True)
app.add_typer(invoices, name="invoices")



@invoices.command("add")
def invoice_add(
    supplier_id: int = typer.Option(..., "--supplier", prompt="Supplier ID"),
    invoice_number: str = typer.Option(..., "--number", prompt="Invoice number"),
    currency: str = typer.Option(..., "--currency", prompt="Currency (GBP/EUR/USD)"),
    total: str = typer.Option(..., "--total", prompt="Total including VAT"),
    expense_account: str = typer.Option(..., "--expense-account", prompt="Expense account code"),
    company_id: int = typer.Option(1, "--company-id"),
    vat_rate: str = typer.Option("20", "--vat-rate"),
    invoice_date: str | None = typer.Option(None, "--date", help="YYYY-MM-DD; defaults to today."),
):
    """Save a base-currency invoice and its balanced journal."""
    values = dict(company_id=company_id, supplier_id=supplier_id, invoice_number=invoice_number,
                  currency=currency.upper(), total_amount=total, vat_rate=vat_rate,
                  expense_account_code=expense_account)
    if invoice_date is not None:
        values["invoice_date"] = invoice_date
    data = InvoiceCreate(**values)
    from app.db import SessionLocal

    with SessionLocal() as db:
        result = create_invoice(db, data)
    typer.echo(f"Created invoice #{result['invoice_id']} and journal #{result['journal_id']}.")


def print_invoice_summary(row):
    typer.echo(f"Invoice #{row['id']} | {row['number']} | {row['date']} | {row['supplier']}")
    typer.echo(f"  {row['currency']}: total {row['total']:,.2f} | paid {row['paid']:,.2f} | balance {row['balance']:,.2f}")
    typer.echo(f"  Expense: {', '.join(row['expense_accounts']) or '-'}")
    if row['has_invoice_posting']:
        typer.echo(f"  {row['base_currency']}: net {row['base_net']:,.2f} | VAT {row['base_vat']:,.2f} | total {row['base_total']:,.2f} | payable balance {row['base_balance']:,.2f}")
    else:
        typer.echo("  No invoice journal posting found.")


@invoices.command("list")
def invoice_list(company_id: int = typer.Option(1, "--company-id", min=1)):
    """List invoice amounts and outstanding balances; no journal detail."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = list_invoices(db, company_id)
    if not rows:
        typer.echo("No invoices found.")
    for row in rows:
        print_invoice_summary(row)
        typer.echo()


@invoices.command("show")
def invoice_show(invoice_id: int = typer.Argument(..., min=1)):
    """Show one invoice and every linked journal, including payment postings."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        report = get_invoice(db, invoice_id)
    print_invoice_summary(report)
    typer.echo(f"  Company #{report['company_id']} | VAT rate {report['vat_rate']}% | FX {report['exchange_rate']} {report['base_currency']}/{report['currency']} | Rate date {report['rate_date']}")
    for journal in report['journals']:
        typer.echo()
        print_journal(journal, report['base_currency'])


@journals.command("list")
def journal_list():
    """List journal headers only, without posting lines."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = list_journals(db)
    if not rows:
        typer.echo("No journal entries yet.")
        return
    typer.echo(f"{'ID':<7} {'Date':<12} {'Type':<10} {'Invoice':<9} {'Payment':<9} Description")
    for row in rows:
        invoice = row['invoice_id'] if row['invoice_id'] is not None else '-'
        payment = row['payment_id'] if row['payment_id'] is not None else '-'
        typer.echo(f"{row['id']:<7} {row['posting_date'].isoformat():<12} {row['kind']:<10} {invoice:<9} {payment:<9} {row['description']}")


@journals.command("show")
def journal_show(entry_id: int = typer.Argument(..., min=1)):
    """Show all debit and credit lines for one journal entry."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        report = get_journal(db, entry_id)
    print_journal(report)


def print_journal(report, currency="GBP"):
    typer.echo(f"Journal #{report['id']} | {report['posting_date']} | {report['kind']} | {currency}")
    typer.echo(report['description'])
    if report['invoice_id'] is not None:
        typer.echo(f"Invoice #{report['invoice_id']}")
    if report['payment_id'] is not None:
        typer.echo(f"Payment #{report['payment_id']}")
    typer.echo(f"{'Code':<8} {'Account':<26} {('Debit ' + currency):>14} {('Credit ' + currency):>14}")
    for line in report['lines']:
        typer.echo(f"{line['code']:<8} {line['name']:<26} {line['debit']:>14,.2f} {line['credit']:>14,.2f}")
    typer.echo(f"{'TOTAL':<35} {report['total_debit']:>14,.2f} {report['total_credit']:>14,.2f}")
    if not report['lines']:
        typer.echo("No posting lines recorded.")
    elif report['total_debit'] == report['total_credit']:
        typer.echo("Balanced.")
    else:
        typer.echo("Unbalanced: debit and credit totals differ.")


def format_balance(balance):
    if balance == 0:
        return "0.00"
    return f"{abs(balance):,.2f} {'Dr' if balance > 0 else 'Cr'}"


@accounts.command("list")
def account_list():
    """Show every account and its all-time GBP balance."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = list_accounts(db)
    if not rows:
        typer.echo("No accounts yet. Run 'app seed' first.")
        return
    typer.echo(f"{'Code':<8} {'Name':<26} {'Type':<12} Balance (GBP)")
    for row in rows:
        typer.echo(f"{row['code']:<8} {row['name']:<26} {row['account_type']:<12} {format_balance(row['balance'])}")


@accounts.command("show")
def account_show(code: str):
    """Show an account's transactions and running GBP balance by account code."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        report = get_account_activity(db, code)
    typer.echo(f"{report['code']} - {report['name']} ({report['account_type']}) | GBP | All time")
    typer.echo("Opening balance: 0.00 GBP")
    if not report["transactions"]:
        typer.echo("No transactions.")
    else:
        typer.echo(f"{'Date':<12} {'Entry':<7} {'Debit':>12} {'Credit':>12} {'Balance':>18}  Description")
        for row in report["transactions"]:
            typer.echo(f"{row['posting_date'].isoformat():<12} {row['entry_id']:<7} {row['debit']:>12,.2f} {row['credit']:>12,.2f} {format_balance(row['balance']):>18}  {row['description']}")
            if row['invoice_id'] is not None:
                typer.echo(f"  Invoice #{row['invoice_id']}" + (f" / Payment #{row['payment_id']}" if row['payment_id'] is not None else ""))
    typer.echo(f"Closing balance: {format_balance(report['balance'])} GBP")


@suppliers.command("add")
def supplier_add(name: str = typer.Option(..., "--name", prompt="Supplier name")):
    """Create a supplier, prompting for its name if omitted."""
    data = SupplierCreate(name=name)
    from app.db import SessionLocal

    with SessionLocal() as db:
        supplier = create_supplier(db, data)
    typer.echo(f"Created supplier #{supplier.id}: {supplier.name}")


@suppliers.command("list")
def supplier_list():
    """List saved suppliers with their IDs."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = list_suppliers(db)
    if not rows:
        typer.echo("No suppliers yet. Use 'app suppliers add' to create one.")
    for supplier in rows:
        typer.echo(f"{supplier.id}\t{supplier.name}")


@app.command()
def web(
    host: str | None = typer.Option(None, envvar="HOST", help="Interface to listen on."),
    port: int = typer.Option(8888, min=1, max=65535, envvar="PORT"),
):
    """Start the web app, creating missing tables and seeding once."""
    import uvicorn

    host = host or ("0.0.0.0" if os.getenv("RAILWAY_ENVIRONMENT_ID") else "127.0.0.1")
    uvicorn.run("app.main:app", host=host, port=port)


@app.command()
def init_db():
    """Create missing tables without changing existing data or seeding."""
    from app.db import initialize_database

    initialize_database()
    typer.echo("Database tables are ready. Existing data preserved; no seed data added.")


@app.command()
def seed(reset: bool = typer.Option(False, "--reset", help="Delete all application data and reseed.")):
    """Add company, accounts, suppliers, and opening funding once."""
    if reset:
        typer.confirm("Delete ALL application data in the configured database and reseed?", abort=True)
    from app.db import SessionLocal, seed_database

    with SessionLocal() as db:
        created = seed_database(db, reset=reset)
    typer.echo("Seed complete: company, 12 accounts, 3 sample suppliers, and £50,000 opening funding. Existing reference records were reused." if created else "Seed already completed; no data changed.")


def main():
    # Handle expected errors once. Never print database errors containing secrets.
    try:
        app()
    except ValidationError as exc:
        for error in exc.errors():
            field = error["loc"][0] if error["loc"] else "Input"
            typer.echo(f"{field}: {error['msg']}", err=True)
        raise SystemExit(2) from None
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise SystemExit(1) from None
    except SQLAlchemyError:
        typer.echo("Database operation failed. Check PostgreSQL, DATABASE_URL, and that 'app init-db' has been run.", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
