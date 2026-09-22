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

`app init-db` creates missing tables without deleting data or seeding. `invoice-ledger web` starts the minimal web shell; `app seed` adds reference data and opening bank funding. `invoice-ledger` is an alias for `app`.
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

## Web shell

From backend/ with Docker PostgreSQL running:

```bash
uv run invoice-ledger web
```

Open http://127.0.0.1:8888. Optional flags: `--host 0.0.0.0 --port 8888`.
The command follows the current `invoice-ledger` script entry in pyproject.toml.

FastAPI lives in app/main.py. Startup creates missing tables and calls the seed
without reset. The seed completion marker prevents duplicate data on later starts;
it is not based on whether every table has rows (empty invoices/payments are normal).
Existing schemas are not migrated. Startup fails if database setup fails.

`/` shows a placeholder until app/static/index.html exists, then serves that file.
`/static` serves frontend assets; configure the future Vite build base as `/static/`.
An empty router in app/api/routes.py is included under `/api`. There are no business
API routes or React frontend yet. This is one web server; no SPA fallback yet.

Web binding defaults to 127.0.0.1:8888 locally. PORT overrides the default port;
HOST overrides the address. On Railway (RAILWAY_ENVIRONMENT_ID is present), the
default address becomes 0.0.0.0 and PORT supplies the listening port. Explicit
--host/--port flags override environment variables. These are process environment
variables; they do not depend on loading database settings from .env. Railway
provides the public URL separately; it is not the address Uvicorn binds to.

## Record an invoice (base currency only for now)

From backend/, use a supplier ID from `invoice-ledger suppliers list`:

```bash
uv run invoice-ledger invoices add --supplier 1 --number INV-001 --currency GBP --total 120 --expense-account 5400
```

Required inputs are prompted if omitted. Total includes VAT. Optional flags:
`--company-id 1`, `--vat-rate 20`, `--date YYYY-MM-DD` (defaults to today).
The supplier and accounts must belong to the selected company. Currency must
match the company's base currency; otherwise the command reports "Foreign ccy
not yet supported." and saves nothing. Matching currency uses rate 1 and the
invoice date as rate date; no FX API or cache is used yet.

The service saves invoice and journal in one transaction. Net/VAT/total base
amounts are posted to the selected expense account, input VAT (1100), and payables
(2000); zero VAT creates no VAT line. A total of GBP 120 at 20% posts 100 expense,
20 VAT, and 120 payables. The command prints the invoice and journal IDs; inspect
both sides with `uv run invoice-ledger journals show JOURNAL_ID`.

No database schema change is required for company_id input: the invoice belongs
to its supplier's company. Existing schema must already include the recent
invoice vat_rate change. Offline tests cover calculations/validation and mock
transaction boundaries; live PostgreSQL verification is performed by the user.

## Invoice reports

```bash
uv run invoice-ledger invoices list
uv run invoice-ledger invoices show 8
```

Replace 8 with an invoice ID. List defaults to company 1; use `--company-id` to
select another company. Each invoice summary is one line showing supplier, date, number, original
currency/total/paid/outstanding, expense account, and base net/VAT only. Base total
and remaining base payable are omitted from the summary. Original paid amounts are summed from linked payments;
base original amounts come from invoice recognition lines only. Remaining base
payables include all linked payable postings, including payment journals. Payment
FX expenses do not change the invoice's original cost. No unlike currencies are
summed together. Missing invoice journals are flagged explicitly.

Show adds VAT rate, FX rate/date, and every invoice-linked journal with all debit/
credit lines and totals. Reports are read-only, all-time, and reuse the journal
formatter. These demo reports favour simple queries over bulk-query optimization.

## Invoice payment statement

```bash
uv run invoice-ledger invoices payments 8
```

Replace 8 with an invoice ID. This read-only table starts with the invoice, then
shows each payment ordered by payment date and ID. Columns: date, invoice/payment,
currency, amount, running balance, base currency, payable movement, base balance.
Payments appear as negative movements. Original amounts come from invoice/payment
records; base movements come only from account 2000 journal lines, linked by
invoice ID for recognition and payment ID for settlement. Base cash amounts and
FX expense do not substitute for liability released. Missing payable postings
produce an error instead of a misleading zero. The footer shows both final balances.
No payments yet means the statement contains only the original invoice row.

### Record a payment

From `backend/`, pay GBP 40 of invoice 1, plus a GBP 2 bank fee:

```sh
uv run invoice-ledger payments add --invoice 1 --currency GBP --amount 40 --bank-account 1000 --bank-fees 2
uv run invoice-ledger invoices payments 1
uv run invoice-ledger invoices show 1
```

HSBC GBP (`1000`) is the only bank option. Fees default to zero, date to today,
and GBP exchange rate to 1. For a foreign invoice, supply `--exchange-rate`
as GBP per one unit of invoice currency (e.g. USD rate `0.85`). Payment currency
must match the invoice. Foreign invoices now look up daily BoE rates through Frankfurter using the
invoice date (yesterday for invoices dated today). The applied rate and actual
publication date are shown by `invoice-ledger invoices show ID`.

Fetch/cache all three daily FX rates (run from `backend/`):

```sh
uv run invoice-ledger get-rates
uv run invoice-ledger get-rates --days 10
```

`--days` defaults to 1 and covers previous calendar days starting yesterday.
Output shows each requested date and actual publication date, with GBP per unit
of GBP, EUR and USD. Rate lookup failures are reported and skipped; database
errors stop the command. Each successful day is saved independently.

### Payment and reconciliation reports

```sh
uv run invoice-ledger payments list
uv run invoice-ledger payments show 1
uv run invoice-ledger invoices outstanding
uv run invoice-ledger accounts trial-balance
```

Payment detail includes its full journal. Outstanding invoices show separate
original-currency totals, their combined GBP carrying balance, and a comparison
against the payables control account. Trial balance shows debit/credit account
balances and checks their totals. These reports cover company 1, all time.

For a local end-to-end check, create an invoice, record a partial payment, then
pay its remaining invoice-currency amount. After each payment run
`invoices payments ID`, `invoices outstanding`, and `accounts trial-balance`.
After final settlement both invoice balances should be zero, payables should
reconcile, and the trial balance should remain balanced. Use `payments show ID`
to inspect fee and FX postings. Automated tests use mocked sessions; this live
PostgreSQL check is run by the developer separately.

Small P&L report (inclusive posting dates, GBP; income positive, expenses negative):

```sh
invoice-ledger accounts pnl --from 2026-09-01 --to 2026-09-30
```
