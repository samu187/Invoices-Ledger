"""Command-line entry point; business features will be added in later stages."""

from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import ProgrammingError
from rich.console import Console
from rich.table import Table

from app.schemas import SupplierCreate
from app.seed import seed_company
from app.services.suppliers import CompanyNotConfiguredError, create_supplier, list_suppliers
from sqlalchemy.exc import SQLAlchemyError
from app.db import DatabaseConfigurationError, get_engine, initialize_database

app = typer.Typer(
    help="Invoice Ledger: multi-currency supplier accounting.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


suppliers = typer.Typer(help="Create and list suppliers.", no_args_is_help=True)
app.add_typer(suppliers, name="suppliers")


@contextmanager
def database_command() -> Iterator[Engine]:
    """Translate infrastructure errors for CLI users; never initialize silently."""
    engine = None
    try:
        engine = get_engine()
        yield engine
    except (DatabaseConfigurationError, CompanyNotConfiguredError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    except ProgrammingError:
        typer.echo("Database schema is unavailable or incompatible. Run 'app init-db' if tables are missing; existing schema changes need a separate fix.", err=True)
        raise typer.Exit(1) from None
    except SQLAlchemyError:
        typer.echo("Database operation failed. Check PostgreSQL and DATABASE_URL. No success was confirmed; check existing records before retrying.", err=True)
        raise typer.Exit(1) from None
    finally:
        if engine is not None:
            engine.dispose()


@suppliers.command("add")
def supplier_add(name: str = typer.Option(..., "--name", prompt="Supplier name")) -> None:
    """Create a supplier, prompting for its name if omitted."""
    try:
        data = SupplierCreate(name=name)
    except ValidationError as exc:
        for error in exc.errors():
            typer.echo(f"{' / '.join(str(part) for part in error['loc'])}: {error['msg']}", err=True)
        raise typer.Exit(2) from None
    with database_command() as engine:
        supplier = create_supplier(engine, data)
    typer.echo(f"Created supplier #{supplier.id}: {supplier.name}")


@suppliers.command("list")
def supplier_list() -> None:
    """List saved suppliers with their IDs."""
    with database_command() as engine:
        rows = list_suppliers(engine)
    if not rows:
        typer.echo("No suppliers yet. Use 'app suppliers add' to create one.")
        return
    table = Table("ID", "Name")
    for supplier in rows:
        table.add_row(str(supplier.id), supplier.name)
    Console().print(table)


@app.command()
def web() -> None:
    """Start the web service (placeholder)."""
    typer.echo("Web service is not implemented yet. CLI accounting comes first.")


@app.command()
def init_db() -> None:
    """Create missing tables without changing existing data or seeding."""

    engine = None
    try:
        engine = get_engine()
        initialize_database(engine)
    except DatabaseConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    except SQLAlchemyError:
        # Raw driver exceptions can contain connection details; do not print them.
        typer.echo(
            "Database initialization failed. Check that PostgreSQL is running, "
            "DATABASE_URL is correct, and the user can create tables.", err=True,
        )
        raise typer.Exit(1) from None
    finally:
        if engine is not None:
            engine.dispose()
    typer.echo("Database tables are ready. Existing data preserved; no seed data added.")


@app.command()
def seed() -> None:
    """Create the fictional company only; remaining seed data comes later."""
    with database_command() as engine:
        created = seed_company(engine)
    typer.echo("Demo company created." if created else "Company already exists; left unchanged.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
