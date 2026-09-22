# Invoice Ledger

Multi-currency supplier invoices, payments, and accounting reports for one fictional
company. PostgreSQL models and explicit initialization are implemented. Supplier creation/listing and company-only seeding are implemented.
Accounting entries, reports, API, and frontend are subsequent stages.

- [Requirements and development sequence](AGENTS.md)
- [Accounting conventions](docs/conventions.md)
- [Project structure and planned layers](docs/structure.md)

## Backend

Use Python 3.12+ and uv. From the repository root:

```bash
cd backend
uv sync
uv run app --help
```

`app init-db` creates missing tables without deleting data or seeding. `app web` remains a placeholder; `app seed` creates only the company. `invoice-ledger` is an alias for `app`.
Module invocation also works: `uv run python -m app.cli --help`.

The backend is an installable package with a flat `app/` directory (no `src/`).
Only backend contains pyproject.toml, a fresh uv.lock, and the ignored .venv.
There is no .python-version file; the Python requirement is in pyproject.toml.

## Local PostgreSQL

Docker Desktop includes the engine, CLI, and Compose; no native PostgreSQL install
is required. Run these commands from **backend/**.

For a fresh checkout, copy `.env.example` to `.env`, choose a password, and update
POSTGRES_PASSWORD and DATABASE_URL together. Preserve an existing `.env`.
`app` reads backend/.env regardless of working directory; explicit environment
variables take precedence. Never commit credentials.

```bash
docker compose up -d --wait db
docker compose ps
uv run app init-db
docker compose exec db psql -U invoice_ledger -d invoice_ledger
```

In psql, `\dt` lists tables and `\q` exits. Initialization creates nine application
tables. Repeating it preserves existing data but does not modify existing schemas.
`app seed` currently creates only the fictional company.

Compose exposes PostgreSQL 17 on localhost:5432. Its explicit project name remains
`invoice-ledger`; moving the file does not change the configured named volume.

```bash
docker compose stop db    # Stop for the day; data stays
docker compose start db   # Resume after opening Docker Desktop
```

`docker compose down` preserves the volume; `down -v` deletes database data.
Credentials initialize a new volume only: editing `.env` does not change an
existing database user's password. If port 5432 is occupied, change POSTGRES_PORT
and the DATABASE_URL port together.

## Verification

From backend/:

```bash
uv run python -m unittest discover -s tests -v
```

These checks do not connect to PostgreSQL. They compile schema definitions and
check configuration and CLI behaviour. Database commands are run by the user.

## Supplier example

From backend/, with PostgreSQL running and tables initialized:

```bash
uv run app seed
uv run app suppliers add --name "Acme Office Supplies"
uv run app suppliers list
```

Omit `--name` to be prompted. Names are trimmed and must contain 1–200 characters.
The seed creates company id 1 (Northbridge Demo Ltd, GBP) without overwriting an
existing company; it does not yet seed accounts, opening funding, or transactions.
Supplier creation fails clearly if the company has not been seeded.

Follow the code in order: `app/cli.py` → `app/schemas.py` →
`app/services/suppliers.py` → `app/models.py`. Schemas validate input; services
own database transactions and return response schemas usable by a future API.
No schema changes or automatic initialization are required for this feature.
Supplier names need not be unique; use IDs to distinguish suppliers. Editing,
archiving, and deletion are not implemented in this first example.

Offline tests use mocks for database interactions; persistence and PostgreSQL
transaction behaviour still need a user-run check with the commands above.
