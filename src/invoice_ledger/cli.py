"""Command-line entry point; business features will be added in later stages."""

import typer


app = typer.Typer(
    help="Invoice Ledger: multi-currency supplier accounting.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.command()
def web() -> None:
    """Start the web service (placeholder)."""
    typer.echo("Web service is not implemented yet. CLI accounting comes first.")


@app.command()
def init_db() -> None:
    """Create missing database tables (placeholder)."""
    typer.echo("Database initialization is not implemented yet. No tables created.")


@app.command()
def seed() -> None:
    """Populate reference and demo data once (placeholder)."""
    typer.echo("Database seeding is not implemented yet. No data added.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
