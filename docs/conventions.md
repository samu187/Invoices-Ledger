# Demo accounting and implementation conventions

This document describes intended behaviour. SQLAlchemy models and explicit table initialization are implemented.
Supplier services and reference/opening-balance seeding are implemented. Accounting services,
remaining seeds, reports, API, and frontend are not implemented yet.

## Company, currencies, and rates

Use one fictional company, GBP functional/base currency, and an HSBC GBP bank
account. GBP, EUR, and USD are supported. HSBC is only an account label: there is
no bank integration. Base currency cannot change after posting begins.

Rates always mean **GBP per one unit of foreign currency**. GBP uses rate 1.
Invoice date is assumed to be the accounting recognition date in this demo.
Fetch historical reference rates on demand using [Frankfurter](https://frankfurter.dev/)
with its [ECB provider](https://frankfurter.dev/providers/ecb/) explicitly selected.
These are reference rates, not executable bank quotes or necessarily closing rates.

Cache normalized rates in `fx_rates`: foreign currency, base currency, rate,
rate date and created_at timestamp. The currency pair and rate date form the unique
key. Copy the applied rate and rate date onto invoices so cache changes never
rewrite their accounting. No source/provider fields are stored; Frankfurter/ECB
is the fixed application policy.

If the requested date has no published rate, use the most recent available earlier
rate and display its actual date, as a documented approximation. Do not silently
accept arbitrarily stale rates. Define a freshness limit when implementing lookup;
unavailable/unacceptable rates must produce a clear error. Future-dated invoices
are excluded initially. No daily scheduler is required; historical lookups support
backdated invoices. No manual invoice-rate override initially.

IAS 21 uses the recognition-date spot rate and permits reasonable approximations;
our daily reference-rate policy is a demo simplification, not a claim that any
previous-day rate is always appropriate. See [IAS 21, paragraphs 21–22](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2024/issued/part-a/ias-21-the-effects-of-changes-in-foreign-exchange-rates.pdf?bypass=on).

## Stored records and calculated balances

| Table | Purpose |
| --- | --- |
| companies | Fictional company and fixed base currency |
| suppliers | Supplier identity |
| invoices | Supplier reference/date, currency, VAT-inclusive total, VAT rate, FX rate/date |
| payments | Invoice reference, date, foreign amount settled, actual GBP cost/rate |
| accounts | Account code/name/type, including HSBC, payables, expense, VAT, FX |
| journal_entries | Dated posting event and source invoice/payment |
| journal_lines | Account, GBP debit/credit, and invoice traceability |
| fx_rates | Cached reference rates, dates, and creation timestamps |
| seed_runs | Completion markers for future transactional seeds |

Payments must be stored, not inferred from a current balance. Each payment belongs
to one invoice initially. There is no separate outstanding-balance or status table.
Derive unpaid/part-paid/paid status and balances from stored transactions.

Invoice foreign outstanding = original total − sum of linked foreign payments.
Invoice GBP payable = linked payable credits − linked payable debits.
The second figure is historical carrying value, not today's market valuation.
Posted records are not silently edited or deleted; correction workflow can be
added explicitly later. No period-end unrealised FX revaluation initially.

## Invoice recognition and VAT

Invoice input requires the VAT-inclusive total and currency. VAT rate is optional
and defaults to 20 (percent); 0 is allowed. The invoice date defaults to today.
Using ROUND_HALF_UP, the service will calculate:

```text
base total = round(original total × FX rate, 2)
base net = round(base total / (1 + vat_rate / 100), 2)
base VAT = base total - base net
```

These GBP amounts are stored only in journal lines. Original-currency net and VAT
can be derived for display from the original total and VAT rate.
This is a demo default, not a rule that every foreign invoice carries UK VAT.
Invoice stores total_amount and vat_rate, but no net_amount, vat_amount, or base
amount columns. The original base liability is the payables credit in the invoice
recognition journal, not its remaining balance after payments.

Assume the net invoice amount is an expense and calculated VAT is fully recoverable
input VAT, translated at the invoice rate. This deliberately omits jurisdictional
VAT rules, reverse charge, VAT returns, and HMRC integration.

For a USD 100 invoice with no VAT at 0.85 GBP/USD, store original total 100 USD,
rate 0.85, and VAT rate 0 on the invoice. Post GBP debit expense 85, credit
payables 85 in its linked journal.
With VAT, debit expense for base net and input VAT for base VAT; credit payables
for base total. Round components consistently and ensure their sum equals the
posted total; never produce an unbalanced journal from independent rounding.

## Payments, partial settlement, and FX P&L

Record the invoice-currency amount settled and actual GBP spent from HSBC.
Effective payment rate = actual GBP settlement amount / foreign amount settled.
Separately identified fees are bank expenses, not FX loss. Initially payment
currency equals invoice currency, with funding from the GBP bank account.

For invoice foreign total F, original base liability B, prior cumulative foreign
settlements P, and new foreign payment p:

```text
target cumulative liability release = round(B × (P + p) / F, 2)
current liability release = target cumulative release − prior actual releases
FX loss = actual GBP settlement cost − current liability release
```

At final settlement, target cumulative release is exactly B. A negative FX loss
is an FX gain. This is the proportional method with cumulative rounding, avoiding
accumulated penny discrepancies across many partial payments.

Example: settle USD 50 of the USD 100 / GBP 85 invoice for GBP 43:

| Account | Debit GBP | Credit GBP |
| --- | ---: | ---: |
| Payables | 42.50 | |
| FX loss | 0.50 | |
| HSBC GBP | | 43.00 |

Remaining invoice: USD 50; remaining payable: GBP 42.50. Paying the final USD 50
for GBP 42 releases the remaining GBP 42.50 and creates a GBP 0.50 FX gain.
The payable becomes zero; cumulative cash paid is GBP 85 and net FX result zero.

Use Decimal/NUMERIC (never binary floats) for financial calculations. Proposed
rounding: ROUND_HALF_UP, amounts at two decimals, stored rates at sufficient
precision (e.g. ten decimal places). Actual GBP cash is authoritative; do not
reconstruct it from a rounded displayed effective rate.

Save invoice/payment and all journal lines in one database transaction. Positive
amounts/rates, valid currencies, supplier/invoice-number uniqueness, no overpayments,
and balanced postings require validation. Serialize settlement of the same invoice
to prevent concurrent overpayments; prevent duplicate event submission.

## Reports and reconciliation

1. Account balances: assets/liabilities including HSBC, input VAT, and payables.
2. P&L: expenses and realised FX gains/losses for a selected date range.
3. Account activity: opening balance, dated source-linked debits/credits, running
   balance and closing balance. Show debit/credit direction explicitly.
4. Invoice statement: original payable, payments and applied rates, GBP liability
   released, FX result, running foreign outstanding and GBP payable balance.
5. Outstanding invoices: original currency groups and combined GBP carrying value.
6. Trial balance: every account, debit/credit balances and equality check.

Invoice-level balances must sum to the payables control account at the same cutoff.
All reports must use consistent posting dates for as-of/date-range queries.
Never sum USD/EUR/GBP amounts together without conversion.

The bank may show a credit/negative balance if we seed payments without starting
funds. Seed explicit opening GBP funding (debit HSBC, credit opening equity) so
the demo starts with a realistic bank balance; label it separately from P&L.

## Initialization and delivery

PostgreSQL only, selected through DATABASE_URL. Use Docker Compose and a named
volume locally so data survives shutdowns and container recreation. Secrets stay
outside Git. SQLAlchemy models precede database initialization and feature work.

No migrations initially: create_all creates missing tables only. Initial seeds
are transactional and tracked so restarting never duplicates/reset data. Reference
seed and demo seed may be separate phases under one seed command. Demo invoice
and payment seeds call the normal accounting services when those are implemented.

Expose setup explicitly through Typer commands: `app init-db` creates missing
tables and `app seed` populates initial data. Normal business CLI commands do not initialize automatically. The minimal web
app explicitly creates missing tables and calls the repeat-safe seed at startup,
without reset; it stops startup if setup fails. Command help requires no connection.
On Railway, setup can be a separate deployment step before `app web` starts.
`backend/app/models.py` contains the SQLAlchemy classes; `backend/app/db.py` handles connection/session
creation and explicit initialization. Payment currency is obtained from its linked
invoice. Journal lines inherit invoice traceability through their entry. A composite
foreign key ensures payment journal entries reference the same invoice as their
payment; a partial unique index prevents duplicate invoice recognition journals.

Database constraints validate individual amounts, currencies, source links, and
posting sides. Cross-row rules (balanced journals, no overpayments, correct account
types, posting-date order, and immutable posted events) still require the future
accounting services; models alone do not implement these rules. The single company
has id 1 and a GBP base currency. Seed completion markers are reserved for later;
initialization inserts no rows.

Develop CLI entries/reports first. Add web API/frontend only after CLI review.
Deploy to a new Railway database later. Authentication and learning migrations
are optional final stages; no users/sessions are needed now.

The reference_data_v1 seed creates/reuses company id 1, twelve accounts, and three
sample suppliers. It posts GBP 50,000 debit HSBC / credit opening equity dated
1 January 2026. A seed_runs marker is reserved with ON CONFLICT DO NOTHING in the
same transaction; any failure rolls back both marker and data. Repeating the seed
does not add funding again or overwrite records. No invoice/payment or FX-rate
seeding is implemented yet.
