# Accounting conventions

Invoice Ledger is a focused demonstration for one fictional company. These conventions explain how the demo translates invoices and payments into GBP accounting entries. They are simplified product assumptions, not tax advice or a complete accounting policy.

## Company and currencies

- GBP is the fixed company base currency.
- Supplier invoices may be recorded in GBP, EUR, or USD.
- HSBC GBP is the only settlement account; the name is illustrative and there is no bank integration.
- Payments use the invoice currency. Cross-currency settlement and period-end revaluation are outside the current scope.
- Original currency amounts, applied rates, and GBP journal amounts are preserved after posting.

## Exchange rates

Rates are expressed as **GBP per one unit of invoice currency**. GBP therefore uses a rate of 1.

Foreign invoice rates come from Bank of England data through the [Frankfurter API](https://frankfurter.dev/), with the BoE provider selected explicitly. Historical invoices request the invoice-date rate. For invoices dated today, the application requests yesterday’s rate because today’s publication may not yet be available.

If the target date is a weekend or holiday, the latest earlier published rate may be used when it is no more than seven calendar days old. The application displays and stores the actual publication date. Missing, future, mismatched, or stale quotes are rejected rather than replaced with an invented rate.

The applied rate and publication date are copied onto the invoice. A posted invoice is never recalculated when newer reference rates become available.

## Invoice recognition and VAT

The invoice date is also the recognition date. The entered total is VAT inclusive, and the VAT rate defaults to 20% but may be changed or set to zero.

```text
GBP total = round(original total × invoice FX rate, 2)
GBP net   = round(GBP total / (1 + VAT rate / 100), 2)
GBP VAT   = GBP total − GBP net
```

The recognition journal is:

| Account | Debit | Credit |
| --- | ---: | ---: |
| Selected expense | GBP net | |
| Input VAT | GBP VAT | |
| Accounts payable | | GBP total |

The demo assumes the net amount is an expense and VAT is fully recoverable input VAT. It does not model reverse charge, jurisdiction-specific VAT rules, VAT return submission, or HMRC integration. The VAT screen is an account activity report rather than a VAT return.

## Payments and realised FX

A payment records the invoice-currency amount settled and the actual GBP settlement cost. Bank fees are recorded separately as a bank fee expense and do not form part of the FX difference.

Partial payments release the original GBP liability proportionally. Cumulative rounding ensures the final payment clears the liability exactly:

```text
target cumulative release = round(original GBP liability × cumulative foreign payments / invoice total, 2)
current liability release = target cumulative release − liability released by earlier payments
FX loss = actual GBP settlement cost − current liability release
```

A positive result is an FX loss; a negative result is an FX gain.

For example, a USD 100 invoice recognised at GBP 85 has an original GBP liability of 85. Settling USD 50 for GBP 43 releases GBP 42.50 of payables and records a GBP 0.50 realised FX loss:

| Account | Debit GBP | Credit GBP |
| --- | ---: | ---: |
| Accounts payable | 42.50 | |
| Realised FX loss | 0.50 | |
| HSBC GBP | | 43.00 |

## Balances and controls

- Invoice-currency outstanding equals the original total minus linked payments.
- GBP carrying value comes from invoice-linked accounts payable journal lines. Actual GBP cash paid is not subtracted directly from the original liability.
- Original currency totals are grouped by currency and are never added across GBP, EUR, and USD.
- Realised FX gains and losses appear in P&L on the payment date.
- There is no unrealised FX revaluation in the current demo.
- Financial calculations use `Decimal` and PostgreSQL `NUMERIC`, with monetary amounts rounded to two decimals using `ROUND_HALF_UP`.
- Every invoice, payment, and its complete balanced journal commit in one database transaction.
- Overpayments, duplicate payment requests, out-of-order payment dates, and unbalanced journals are rejected.
