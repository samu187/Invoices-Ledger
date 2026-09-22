# Invoice Ledger

Multi-currency supplier invoices, payments, and accounting reports for one fictional
company. PostgreSQL models and explicit initialization are implemented. Supplier creation/listing and reference seeding are implemented.
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

`app init-db` creates missing tables without deleting data or seeding. `app web` remains a placeholder; `app seed` adds reference data and opening bank funding. `invoice-ledger` is an alias for `app`.
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
`app seed` adds the company, chart of accounts, sample suppliers, and opening funding.

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
The seed creates company id 1 (Northbridge Demo Ltd, GBP), twelve accounts, three
sample suppliers, and £50,000 opening bank funding dated 1 January 2026. Existing
reference records are reused. A seed_runs marker makes repeat runs a no-op; all
seed changes commit together. It does not yet create invoices or payments.
Supplier creation fails clearly if the company has not been seeded.

Follow the code in order: `app/cli.py` → `app/schemas.py` →
`app/services/suppliers.py` → `app/models.py`. Schemas validate input; services
own database transactions and return response schemas usable by a future API.
No schema changes or automatic initialization are required for this feature.
Supplier names need not be unique; use IDs to distinguish suppliers. Editing,
archiving, and deletion are not implemented in this first example.

Offline tests use mocks for database interactions; persistence and PostgreSQL
transaction behaviour still need a user-run check with the commands above.

## Seed contents

| Code | Account | Type |
| --- | --- | --- |
| 1000 | HSBC GBP | Asset |
| 1100 | Input VAT | Asset |
| 2000 | Accounts payable | Liability |
| 3000 | Opening equity | Equity |
| 4900 | Realised FX gains | Income |
| 5000 | General expenses | Expense |
| 5100 | Cost of goods sold | Expense |
| 5200 | Bank fees | Expense |
| 5300 | Office supplies | Expense |
| 5400 | Software licenses | Expense |
| 5500 | Services | Expense |
| 5900 | Realised FX losses | Expense |

Sample suppliers: Acme Office Supplies, Alpine Design Studio, Hudson Software.
Opening funding debits HSBC £50,000 and credits opening equity £50,000; it has
no P&L effect. Foreign exchange rates are not invented or seeded. Invoices and
payments will be seeded through their accounting services when implemented.

After running `uv run app seed`, run it again to confirm it reports no changes.
You can inspect the live schema without modifying it, from backend/:

```bash
docker compose exec db pg_dump -U invoice_ledger -d invoice_ledger --schema-only --no-owner --no-privileges > /tmp/invoice-ledger-schema.sql
```

This writes a schema-only snapshot for review. It does not change the database or
prove historical equality without a previous snapshot for comparison.

To delete **all application rows** (including invoices, payments, journals, and
cached rates) and restore the seed data:

```bash
uv run app seed --reset
```

The command asks for confirmation. It targets the database in DATABASE_URL.
Tables and their definitions remain unchanged, and generated ID sequences are not
reset. Deletion and seeding run in one transaction: a failure restores the previous
rows. Normal `app seed` still skips if its completion marker exists.

## Account reports

From backend/:

```bash
uv run app accounts list
uv run app accounts show 1000
uv run app accounts show 3000
```

`list` includes every account, even accounts with no postings. `show` takes an
account **code**, not its database ID, and lists journal lines ordered by posting
date, entry ID, and line ID. It includes descriptions, debit/credit amounts,
running balance, and invoice/payment references when available.

Both reports are read-only, all-time, and in GBP. Balance = debits minus credits;
positive amounts display Dr, negative amounts display Cr, and zero displays 0.00.
The all-time opening balance is zero before the first recorded journal line.
After a fresh seed, HSBC (1000) closes at £50,000 Dr, opening equity (3000) at
£50,000 Cr, and other accounts at zero. No date filters are implemented yet.

## Journal reports

```bash
uv run app journals list
uv run app journals show 7
```

Run from backend/. Replace 7 with an ID from the list or account report. `list`
shows only entry headers: ID, posting date, type, source IDs, and description.
`show` displays every account line with GBP debits/credits, totals, and whether
they balance. Both commands are read-only. An entry with no lines is explicitly
labelled empty rather than balanced. Resetting the seed does not restart IDs.
