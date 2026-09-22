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
with its [Bank of England provider](https://frankfurter.dev/providers/boe/) explicitly selected.
These are reference rates, not executable bank quotes or necessarily closing rates.

Cache normalized rates in `fx_rates`: foreign currency, base currency, rate,
rate date and created_at timestamp. The currency pair and rate date form the unique
key. Copy the applied rate and rate date onto invoices so cache changes never
rewrite their accounting. No source/provider fields are stored; Frankfurter/BoE
is the fixed application policy.

If the requested date has no published rate, use the most recent available earlier
rate and display its actual date, as a documented approximation. Do not silently
accept arbitrarily stale rates: the maximum age is seven calendar days;
unavailable/unacceptable rates must produce a clear error. Future-dated invoices
are excluded initially. No daily scheduler is required; historical lookups support
backdated invoices. No manual invoice-rate override initially.

The service in `app/services/fx_rates.py` requests GBP as the API base, with
EUR and USD quotes and `providers=boe`, using the [Frankfurter v2 API](https://frankfurter.dev/).
For each returned publication date it saves all three rows together:

| Currency | Stored base currency | Stored rate (GBP per currency unit) |
| --- | --- | --- |
| GBP | GBP | 1 |
| EUR | GBP | 1 / API EUR quote (EUR per GBP) |
| USD | GBP | 1 / API USD quote (USD per GBP) |

For example, USD per GBP = 1.50 gives GBP per USD = 0.6666666667.
Each quote is inverted independently; no cross rate is calculated. JSON numbers are parsed as Decimal; rates are rounded to ten decimal
places only after conversion. Both API quotes must have the same publication date. The requested date must
be the invoice date, not the day the invoice is entered.

`fetch_rates(date)` fetches and validates without database access.
`get_rates(db, date)` owns a transaction, reuses a complete exact-date cache, or
fetches and inserts all three rates atomically. Existing rows are preserved on
conflict. Both return requested date, actual rate date, base currency and a rates
dictionary. Weekend/holiday lookups may call the API again: we do not assume an
earlier cached date proves that newer rates are unavailable. No fake weekend rows
are created. Invoice creation now calls this service with the invoice date for foreign
currencies. Inside an invoice transaction it uses a savepoint, so cached rates,
the invoice and its journal roll back together if posting fails. Standalone calls
create their own transaction. GBP invoices use rate 1 without a lookup.

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


## Shared journal balance safeguard

Every application workflow that creates a journal (invoice, payment, and opening
funding) calls `add_journal()` in `app/services/journals.py`. Future posting
workflows must use the same function instead of adding journals directly.
It rejects an empty journal and checks that total GBP debits equal total GBP
credits exactly using Decimal, before adding the complete entry to the session.
There is no rounding tolerance: posting services must resolve rounding first.

The helper does not commit. It runs inside the business event's transaction, so
an unbalanced journal raises ValueError and rolls back the invoice/payment or
seed operation as well. Never change posting lines after this validation.


### Today's invoices: previous-day rate

The daily source is **Bank of England data through the Frankfurter API**,
not an ECB API. For an invoice dated today, this demo requests yesterday's
rate to avoid depending on today's publication time. For a historical invoice,
request its invoice date. If that target date has no published rate (for example,
a weekend or holiday), use the latest available earlier publication, within the
seven-calendar-day limit measured from the invoice date. Save and display the
actual publication date; never label a Friday rate as a Sunday rate.

The FX service applies this policy to both API requests and cache lookups.
The caller supplies the invoice date. Once an invoice is posted, its saved rate
and rate date stay fixed even if entered-day or reference rates later change.

## CLI reconciliation reports

`payments list` lists all company-1 payments with original amount, bank rate,
GBP settlement excluding fees, separate fees and total GBP withdrawn.
`payments show ID` adds the reference and complete payment journal.

`invoices outstanding` includes any invoice with a nonzero original or base
balance, so a residual GBP liability cannot disappear merely because the foreign
amount is settled. Sum original balances separately by currency; compare the
sum of GBP carrying balances with the credit balance of payables account 2000.
A mismatch is explicitly reported, including when there are no open invoices.

`accounts trial-balance` splits each account's net balance into a debit or credit
column and checks equality of the column totals. These are closing balances,
not cumulative transaction turnover. All reports currently cover company 1 and
all dates. A balanced trial balance checks arithmetic, not correct classification;
the invoice-to-payables reconciliation is a separate check.

`accounts pnl --from YYYY-MM-DD --to YYYY-MM-DD` includes company-1 income and
expense postings within inclusive journal dates. Credit minus debit is the
profit contribution: expenses normally display negative, income positive.
The sum is net profit/loss in GBP. Bank, payables, equity and input VAT are
excluded. Invoice expenses use invoice dates; payment fees and realised FX use
payment dates. An empty period has zero profit/loss.
