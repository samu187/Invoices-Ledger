"""Fetch and cache complete daily GBP, EUR and USD reference-rate sets."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import FxRate


MAX_RATE_AGE_DAYS = 7


def fetch_rates(requested_date: date) -> dict:
    """Fetch GBP-based BoE quotes and invert to GBP per currency unit."""
    if requested_date > date.today():
        raise ValueError("Cannot request future FX rates.")
    lookup_date = requested_date - timedelta(days=1) if requested_date == date.today() else requested_date
    query = urlencode(dict(base="GBP", quotes="EUR,USD", providers="boe", date=lookup_date.isoformat()))
    request = Request(f"https://api.frankfurter.dev/v2/rates?{query}",
                      headers={"User-Agent": "InvoiceLedger/0.1", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            rows = json.loads(response.read(), parse_float=Decimal)
    except HTTPError as exc:
        raise ValueError(f"Frankfurter FX request failed (HTTP {exc.code}). Please try again later.") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("Could not fetch Frankfurter FX rates. Please try again later.") from None
    except (ValueError, UnicodeError):
        raise ValueError("Frankfurter returned invalid FX rate data.") from None

    try:
        if not isinstance(rows, list) or len(rows) != 2:
            raise ValueError
        quotes = {}
        dates = set()
        for row in rows:
            if row["base"] != "GBP" or row["quote"] not in {"EUR", "USD"}:
                raise ValueError
            rate = Decimal(str(row["rate"]))
            if not rate.is_finite() or rate <= 0:
                raise ValueError
            quotes[row["quote"]] = rate
            dates.add(date.fromisoformat(row["date"]))
        if set(quotes) != {"EUR", "USD"} or len(dates) != 1:
            raise ValueError
        rate_date = dates.pop()
        if rate_date > lookup_date or not 0 <= (requested_date - rate_date).days <= MAX_RATE_AGE_DAYS:
            raise ValueError
        with localcontext() as context:
            context.prec = 40
            rates = {"GBP": Decimal("1"), "EUR": Decimal("1") / quotes["EUR"], "USD": Decimal("1") / quotes["USD"]}
            rates = {currency: rate.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
                     for currency, rate in rates.items()}
        if any(rate <= 0 or rate >= Decimal("10000000000") for rate in rates.values()):
            raise ValueError
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        raise ValueError("Frankfurter must return positive EUR and USD quotes for the same date, no more than 7 days before the requested date.") from None
    return {"requested_date": requested_date, "rate_date": rate_date, "base_currency": "GBP", "rates": rates}


def get_rates(db: Session, requested_date: date) -> dict:
    """Return all three rates, fetching a missing set and saving it atomically."""
    if requested_date > date.today():
        raise ValueError("Cannot request future FX rates.")
    lookup_date = requested_date - timedelta(days=1) if requested_date == date.today() else requested_date
    # A savepoint lets invoice posting include the cache writes in its transaction.
    with db.begin_nested() if db.in_transaction() else db.begin():
        query = select(FxRate).where(FxRate.base_currency == "GBP")
        cached = db.scalars(query.where(FxRate.rate_date == lookup_date)).all()
        if {row.currency for row in cached} == {"GBP", "EUR", "USD"}:
            return {"requested_date": requested_date, "rate_date": lookup_date,
                    "base_currency": "GBP", "rates": {row.currency: row.rate for row in cached}}

        result = fetch_rates(requested_date)
        # One insert for all three; never overwrite cached rates on a repeated fetch.
        db.execute(insert(FxRate).values([
            dict(currency=currency, base_currency="GBP", rate_date=result["rate_date"], rate=rate)
            for currency, rate in result["rates"].items()
        ]).on_conflict_do_nothing(index_elements=["currency", "base_currency", "rate_date"]))
        stored = db.scalars(query.where(FxRate.rate_date == result["rate_date"])).all()
        result["rates"] = {row.currency: row.rate for row in stored}
    return result
