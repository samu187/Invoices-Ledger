# Invoice Ledger

Multi-currency supplier invoices, payments, and accounting reports for a fictional
company. Currently a minimal CLI scaffold; no database/features are implemented.

Requirements and sequence: [AGENTS.MD](AGENTS.MD).
Accounting decisions: [docs/conventions.md](docs/conventions.md).

## Run the scaffold

With Python 3.12+ and uv:

```bash
uv sync
uv run app --help
uv run app web
uv run app init-db
uv run app seed
```

All three commands are Typer placeholders: no server starts and no database is
changed. `invoice-ledger` is an alias for `app`. After installing dependencies,
you can also invoke the module directly:

```bash
PYTHONPATH=src python3 -m invoice_ledger.cli --help
```

## Local database setup

Use Docker Desktop (includes Docker CLI and Compose) to run PostgreSQL; no native
PostgreSQL installation is needed. Open Docker Desktop and wait for its engine,
then check in your terminal:

```bash
docker version
docker compose version
docker info
```

`compose.yaml` runs PostgreSQL 17 on localhost port 5432 with a persistent named
volume. For a fresh checkout, copy `.env.example` to `.env`, choose a password,
and update both POSTGRES_PASSWORD and DATABASE_URL to match. Do not overwrite an
existing `.env`. The current CLI placeholders do not load `.env` yet.

```bash
docker compose up -d --wait db
docker compose ps
docker compose exec db psql -U invoice_ledger -d invoice_ledger
```

The first start downloads PostgreSQL and creates an empty `invoice_ledger`
database. Inside psql, `\dt` lists tables (none yet), and `\q` exits.
This creates the database itself, not our future application tables.

```bash
docker compose stop db    # Stop for the day; data stays
docker compose start db   # Resume next time, after opening Docker Desktop
```

`docker compose down` also preserves the named volume. Adding `-v` deletes it
and its database data, so do not use that for normal shutdown. Initial database
credentials are applied only when the volume is first initialized; changing
`.env` later does not change an existing database user's password. If port 5432
is already occupied, change POSTGRES_PORT and the DATABASE_URL port together.

After connectivity: SQLAlchemy models, safe initialization, reference seed,
accounting services/demo seed, CLI reports, then API/frontend and Railway.

Database setup will be explicit: run `app init-db`, then `app seed`. Normal CLI
commands and `app web` will only check readiness and explain missing setup.
They will not silently populate the database. `src/invoice_ledger/models.py` is
an empty placeholder for the SQLAlchemy models; connection/session setup will
be separate. On Railway, these setup commands can run as a deployment step.
